# ==============================================================================
# Catalog Service - "The Librarian"
# ==============================================================================
# This service orchestrates the Reverse Catalog Search feature.
# It is responsible for understanding *what* the user needs by analyzing
# uploaded PDF manuals using RAG (Retrieval Augmented Generation).
#
# FULL PIPELINE:
#   1. User uploads PDF + description
#   2. Create a Chat record (status: processing)
#   3. Parse PDF → chunk → embed → store in document_chunks
#   4. Embed user description
#   5. Cosine similarity search: description vs chunks
#   6. Send top matching chunks + description to Gemini for prediction
#   7. Gemini identifies part names, numbers, manufacturers
#   8. Create Prediction records
#   9. (Optional) Trigger Web Agent for vendor search per prediction
#  10. Create SearchResult records
#  11. Update Chat status to completed
#
# Uses:
#   - EmbeddingService for PDF parsing and vector operations
#   - WebAgentService for finding vendors/prices
#   - Gemini for intelligent part identification
# ==============================================================================

import asyncio
import logging
import json
import re
import time
from typing import Optional

from google import genai
from google.genai import types
from sqlmodel import Session, select

from app.core.config import settings
from app.models.chat import Chat, ChatType, ChatStatus
from app.models.prediction import Prediction, PredictionType
from app.models.search_result import SearchResult
from app.services.embedding_service import embedding_service
from app.services.web_agent_service import web_agent_service
from app.schemas.web_agent import PartSearchRequest

logger = logging.getLogger(__name__)


# Gemini prompt for analyzing PDF chunks and identifying parts
PART_IDENTIFICATION_PROMPT = """You are an expert industrial parts analyst. You are given:
1. A user's DESCRIPTION of what part they need
2. RELEVANT EXCERPTS from a product catalog/manual PDF

Your task: Identify the specific replacement parts the user is looking for.

DESCRIPTION:
{description}

RELEVANT CATALOG EXCERPTS:
{chunks}

Based on the above, identify the parts that match the user's description.
For each part found, provide:
- part_name: The FULL specific name including model/series numbers as they appear in the catalog (e.g. "Servo Motor SC-920C/M92" NOT just "Motor")
- part_number: Part/model number exactly as shown in the catalog (null if not found)
- manufacturer: Manufacturer/brand name exactly as shown (null if not found)
- description: Brief description including the application context (e.g. "Servo motor for industrial sewing machine, 550W, direct drive")
- confidence_score: How confident you are this is what the user needs (0.0-1.0)

Return a JSON array of parts, ordered by confidence (highest first).
Return at most 5 parts. If no parts match, return an empty array [].

CRITICAL RULES:
- part_name MUST be specific and include model numbers, series codes, or identifying suffixes from the catalog. NEVER return generic names like "Motor" or "Bearing" alone.
- Include the product category in the name (e.g. "Servo Motor" not "Motor", "Ball Bearing 6205-2RS" not "Bearing")
- Extract ONLY parts that are mentioned in the catalog excerpts
- The confidence score should reflect how well the part matches the user's description
- Include part numbers exactly as they appear in the catalog
- Return ONLY valid JSON, no markdown or explanations

JSON Response:"""


class CatalogService:
    """
    The Librarian - Reverse Catalog Search Service.
    
    Orchestrates the full RAG pipeline for identifying parts
    from uploaded PDF catalogs.
    """
    
    def __init__(self):
        """Initialize the Catalog Service."""
        if settings.GEMINI_API_KEY:
            self.gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)
            self.gemini_model = "gemini-2.5-flash"
            logger.info("CatalogService: Gemini client initialized (gemini-2.5-flash)")
        else:
            self.gemini_client = None
            self.gemini_model = None
            logger.warning("CatalogService: GEMINI_API_KEY not configured")
    
    # ==========================================================================
    # CHAT MANAGEMENT
    # ==========================================================================
    
    def create_chat(
        self,
        session: Session,
        user_id: str,
        description: str,
        chat_type: str = ChatType.REVERSE_CATALOG.value,
        media_url: Optional[str] = None,
        media_type: Optional[str] = None,
        original_filename: Optional[str] = None,
    ) -> Chat:
        """Create a new Chat record for a search session."""
        chat = Chat(
            user_id=user_id,
            chat_type=chat_type,
            status=ChatStatus.PENDING.value,
            description=description,
            media_url=media_url,
            media_type=media_type,
            original_filename=original_filename,
        )
        session.add(chat)
        session.commit()
        session.refresh(chat)
        logger.info(f"Created chat {chat.id} for user {user_id}")
        return chat
    
    def update_chat_status(
        self,
        session: Session,
        chat_id: str,
        status: str,
        error_message: Optional[str] = None,
        media_url: Optional[str] = None,
    ) -> Chat:
        """Update the status of a Chat."""
        chat = session.get(Chat, chat_id)
        if not chat:
            raise ValueError(f"Chat {chat_id} not found")
        
        chat.status = status
        if error_message is not None:
            chat.error_message = error_message
        if media_url is not None:
            chat.media_url = media_url
        
        from datetime import datetime, timezone
        chat.updated_at = datetime.now(timezone.utc)
        
        session.add(chat)
        session.commit()
        session.refresh(chat)
        return chat
    
    def get_chat(self, session: Session, chat_id: str) -> Optional[Chat]:
        """Get a Chat by ID."""
        return session.get(Chat, chat_id)
    
    def get_user_chats(
        self,
        session: Session,
        user_id: str,
        chat_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 20
    ) -> list[Chat]:
        """Get all chats for a user, optionally filtered by type."""
        query = select(Chat).where(Chat.user_id == user_id)
        if chat_type:
            query = query.where(Chat.chat_type == chat_type)
        query = query.order_by(Chat.created_at.desc()).offset(skip).limit(limit)
        return list(session.exec(query).all())
    
    # ==========================================================================
    # PREDICTION MANAGEMENT
    # ==========================================================================
    
    def get_predictions(self, session: Session, chat_id: str) -> list[Prediction]:
        """Get all predictions for a chat."""
        query = select(Prediction).where(
            Prediction.chat_id == chat_id
        ).order_by(Prediction.rank)
        return list(session.exec(query).all())
    
    def get_prediction(self, session: Session, prediction_id: str) -> Optional[Prediction]:
        """Get a single prediction by ID."""
        return session.get(Prediction, prediction_id)
    
    def get_search_results(self, session: Session, prediction_id: str) -> list[SearchResult]:
        """Get all search results for a prediction."""
        query = select(SearchResult).where(
            SearchResult.prediction_id == prediction_id
        ).order_by(SearchResult.confidence_score.desc())
        return list(session.exec(query).all())
    
    # ==========================================================================
    # CORE RAG PIPELINE
    # ==========================================================================
    
    async def identify_parts(
        self,
        description: str,
        chunks: list[dict]
    ) -> list[dict]:
        """
        Use Gemini to identify parts from description + relevant chunks.
        
        Args:
            description: User's description of what they need
            chunks: List of chunk dicts with 'chunk_text' and 'similarity'
        
        Returns:
            List of identified part dicts
        """
        if not self.gemini_client:
            raise ValueError("GEMINI_API_KEY not configured")
        
        # Format chunks for prompt — use all available chunks with reasonable trim
        MAX_CHUNKS = 5
        MAX_CHUNK_CHARS = 900
        chunks_text = ""
        for i, chunk in enumerate(chunks[:MAX_CHUNKS]):
            similarity_pct = int(chunk["similarity"] * 100)
            trimmed = chunk["chunk_text"][:MAX_CHUNK_CHARS]
            chunks_text += f"\n--- Excerpt {i+1} (Relevance: {similarity_pct}%) ---\n"
            chunks_text += trimmed
            chunks_text += "\n"
        
        prompt = PART_IDENTIFICATION_PROMPT.format(
            description=description,
            chunks=chunks_text
        )
        
        logger.info(f"Prompt length: {len(prompt)} chars, {MAX_CHUNKS} chunks")
        
        # Retry with exponential backoff on rate-limit (429) errors
        max_retries = 5
        for attempt in range(max_retries):
            try:
                response = await self.gemini_client.aio.models.generate_content(
                    model=self.gemini_model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.3,
                        max_output_tokens=2048,
                        response_mime_type="application/json",
                    )
                )
                break
            except Exception as api_err:
                err_str = str(api_err)
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    # Parse retryDelay from error if available, otherwise use 30s base
                    retry_match = re.search(r'retryDelay["\']?\s*[:=]\s*["\']?(\d+)', err_str)
                    base_wait = int(retry_match.group(1)) if retry_match else 30
                    wait = base_wait + (attempt * 10)  # 30s, 40s, 50s, 60s, 70s
                    logger.warning(f"Rate limited on identify_parts (attempt {attempt+1}/{max_retries}), waiting {wait}s...")
                    await asyncio.sleep(wait)
                    if attempt == max_retries - 1:
                        raise
                else:
                    raise
        
        response_text = response.text.strip()
        logger.info(f"Gemini raw response ({len(response_text)} chars): {response_text[:500]}")
        
        # Handle markdown code blocks
        if response_text.startswith("```"):
            response_text = re.sub(r'^```json?\n?', '', response_text)
            response_text = re.sub(r'\n?```$', '', response_text)
        
        try:
            parts = json.loads(response_text)
            if not isinstance(parts, list):
                parts = [parts]
            logger.info(f"Gemini identified {len(parts)} parts")
            return parts
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Gemini response: {e}")
            logger.error(f"Response text: {response_text[:500]}")
            return []
    
    # ==========================================================================
    # FULL SEARCH PIPELINE
    # ==========================================================================
    
    async def run_catalog_search(
        self,
        session: Session,
        chat_id: str,
        pdf_bytes: bytes,
        description: str,
        run_web_search: bool = True,
        max_web_results: int = 5,
        location: str = "Sri Lanka",
    ) -> dict:
        """
        Full Reverse Catalog Search pipeline.
        
        Args:
            session: Database session
            chat_id: ID of the chat
            pdf_bytes: Raw PDF file bytes
            description: User's description of what they need
            run_web_search: Whether to search for vendors after identification
            max_web_results: Max vendor results per prediction
            location: Target location for web search
        
        Returns:
            Dict with 'chat', 'predictions', and 'processing_time_ms'
        """
        start_time = time.time()
        
        try:
            # Step 1: Update chat status to processing
            self.update_chat_status(session, chat_id, ChatStatus.PROCESSING.value)
            
            # Step 2: Parse PDF → chunk → embed → store
            logger.info(f"[{chat_id}] Step 1: Processing PDF...")
            chunks = await embedding_service.process_and_store_pdf(
                session, chat_id, pdf_bytes
            )
            logger.info(f"[{chat_id}] Stored {len(chunks)} chunks")
            
            # Step 3: Find similar chunks to description
            logger.info(f"[{chat_id}] Step 2: Finding similar chunks...")
            similar_chunks = await embedding_service.find_similar_chunks(
                session, chat_id, description, top_k=5
            )
            
            if not similar_chunks:
                self.update_chat_status(
                    session, chat_id, ChatStatus.FAILED.value,
                    error_message="No relevant content found in the PDF for the given description"
                )
                return {
                    "chat": self.get_chat(session, chat_id),
                    "predictions": [],
                    "processing_time_ms": int((time.time() - start_time) * 1000)
                }
            
            logger.info(f"[{chat_id}] Found {len(similar_chunks)} similar chunks "
                        f"(top similarity: {similar_chunks[0]['similarity']:.3f})")
            
            # Step 4: Use Gemini to identify parts
            logger.info(f"[{chat_id}] Step 3: Identifying parts with Gemini...")
            identified_parts = await self.identify_parts(description, similar_chunks)
            
            if not identified_parts:
                self.update_chat_status(
                    session, chat_id, ChatStatus.COMPLETED.value,
                    error_message="No matching parts could be identified from the catalog"
                )
                return {
                    "chat": self.get_chat(session, chat_id),
                    "predictions": [],
                    "processing_time_ms": int((time.time() - start_time) * 1000)
                }
            
            # Step 5: Create Prediction records
            logger.info(f"[{chat_id}] Step 4: Creating {len(identified_parts)} predictions...")
            predictions = []
            for rank, part in enumerate(identified_parts):
                # Find which chunk matched this part best
                matched_chunk = similar_chunks[0]["chunk_text"] if similar_chunks else None
                
                prediction = Prediction(
                    chat_id=chat_id,
                    prediction_type=PredictionType.REVERSE_CATALOG.value,
                    part_name=part.get("part_name", "Unknown Part"),
                    part_number=part.get("part_number"),
                    manufacturer=part.get("manufacturer"),
                    description=part.get("description"),
                    confidence_score=min(float(part.get("confidence_score", 0.5)), 1.0),
                    matched_chunk_text=matched_chunk,
                    rank=rank,
                )
                session.add(prediction)
                predictions.append(prediction)
            
            session.commit()
            for p in predictions:
                session.refresh(p)
            
            # Step 6: Optional - Run web search for each prediction
            if run_web_search:
                logger.info(f"[{chat_id}] Step 5: Running web search for predictions...")
                for idx, prediction in enumerate(predictions):
                    try:
                        await self._search_for_prediction(
                            session, prediction, max_web_results, location
                        )
                    except Exception as e:
                        logger.error(f"Web search failed for prediction {prediction.id}: {e}")
                        # Continue with other predictions
                    
                    # Throttle: wait between web searches to stay under rate limits
                    if idx < len(predictions) - 1:
                        logger.info(f"[{chat_id}] Throttling: waiting 3s before next web search...")
                        await asyncio.sleep(3)
            
            # Step 7: Update chat status to completed
            self.update_chat_status(session, chat_id, ChatStatus.COMPLETED.value)
            
            processing_time_ms = int((time.time() - start_time) * 1000)
            logger.info(f"[{chat_id}] Catalog search completed in {processing_time_ms}ms")
            
            return {
                "chat": self.get_chat(session, chat_id),
                "predictions": predictions,
                "processing_time_ms": processing_time_ms,
            }
            
        except Exception as e:
            logger.exception(f"[{chat_id}] Catalog search failed: {e}")
            # Rollback the failed transaction before updating status
            session.rollback()
            try:
                self.update_chat_status(
                    session, chat_id, ChatStatus.FAILED.value,
                    error_message=str(e)
                )
            except Exception as status_err:
                logger.error(f"[{chat_id}] Failed to update chat status: {status_err}")
            raise
    
    async def _search_for_prediction(
        self,
        session: Session,
        prediction: Prediction,
        max_results: int = 5,
        location: str = "Sri Lanka",
    ) -> list[SearchResult]:
        """
        Run Web Agent search for a single prediction and store results.
        
        Args:
            session: Database session
            prediction: The prediction to search for
            max_results: Maximum vendor results
            location: Target location
        
        Returns:
            List of created SearchResult records
        """
        # Build search request with description context for relevance filtering
        search_request = PartSearchRequest(
            part_name=prediction.part_name,
            part_number=prediction.part_number,
            manufacturer=prediction.manufacturer,
            context_description=prediction.description,
            location=location,
            max_results=max_results,
            include_scraping=False,  # Fast path only for speed
        )
        
        # Run web search
        web_response = await web_agent_service.find_parts(search_request)
        
        logger.info(f"Web search for '{prediction.part_name}' returned {len(web_response.results)} results")
        
        # Store results
        search_results = []
        first_image_url = None
        for vendor_result in web_response.results:
            logger.info(f"  Storing: {vendor_result.product_title[:50]} | "
                        f"price={vendor_result.price} {vendor_result.currency} | "
                        f"image_url={vendor_result.image_url[:60] if vendor_result.image_url else 'None'}")
            sr = SearchResult(
                prediction_id=prediction.id,
                vendor_name=vendor_result.vendor_name,
                product_title=vendor_result.product_title,
                description=vendor_result.description,
                price=vendor_result.price,
                currency=vendor_result.currency,
                availability=vendor_result.availability,
                product_url=vendor_result.product_url,
                image_url=vendor_result.image_url,
                source_type=vendor_result.source_type,
                confidence_score=vendor_result.confidence_score,
                location=location,
            )
            session.add(sr)
            search_results.append(sr)
            # Track first available image
            if not first_image_url and vendor_result.image_url:
                first_image_url = vendor_result.image_url
        
        # Update prediction
        prediction.web_search_completed = True
        # Set prediction image from first vendor that has one
        if first_image_url:
            prediction.image_url = first_image_url
        
        session.add(prediction)
        session.commit()
        
        for sr in search_results:
            session.refresh(sr)
        session.refresh(prediction)
        
        logger.info(f"Stored {len(search_results)} search results for prediction {prediction.id}")
        return search_results
    
    async def search_for_prediction_by_id(
        self,
        session: Session,
        prediction_id: str,
        location: str = "Sri Lanka",
        max_results: int = 5,
    ) -> list[SearchResult]:
        """
        Trigger web search for a specific prediction by ID.
        Called when user selects a prediction and wants vendor results.
        """
        prediction = self.get_prediction(session, prediction_id)
        if not prediction:
            raise ValueError(f"Prediction {prediction_id} not found")
        
        return await self._search_for_prediction(
            session, prediction, max_results, location
        )


# Singleton instance
catalog_service = CatalogService()
