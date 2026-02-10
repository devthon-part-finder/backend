# ==============================================================================
# Embedding Service - Gemini Text Embeddings & PDF Parsing
# ==============================================================================
# This service handles:
#   1. PDF text extraction and chunking
#   2. Text embedding via Gemini's gemini-embedding-001 model
#   3. Storing chunks + vectors in the database
#   4. Cosine similarity matching between description and chunks
#
# Used by the Reverse Catalog Search ("The Librarian") to:
#   - Parse uploaded PDF manuals into chunks
#   - Embed chunks and user descriptions
#   - Find relevant parts via vector similarity
#
# Gemini embedding model produces 768-dimensional vectors (configurable).
# ==============================================================================

import asyncio
import logging
import io
from typing import Optional

import fitz  # PyMuPDF
from google import genai
from google.genai import types
from sqlmodel import Session

from app.core.config import settings
from app.models.document_chunk import DocumentChunk

logger = logging.getLogger(__name__)

# ==============================================================================
# CONSTANTS
# ==============================================================================
CHUNK_SIZE = 1000          # Characters per chunk
CHUNK_OVERLAP = 200        # Overlap between chunks for context continuity
EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIMENSION = 768


class EmbeddingService:
    """
    Service for PDF parsing, text embedding, and vector operations.
    
    Uses Gemini gemini-embedding-001 for generating embeddings and
    PyMuPDF (fitz) for PDF text extraction.
    """
    
    def __init__(self):
        """Initialize the Embedding Service."""
        if settings.GEMINI_API_KEY:
            self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
            logger.info("EmbeddingService: Gemini client initialized")
        else:
            self.client = None
            logger.warning("EmbeddingService: GEMINI_API_KEY not configured")
    
    # ==========================================================================
    # PDF PARSING
    # ==========================================================================
    
    def extract_text_from_pdf(self, pdf_bytes: bytes) -> list[dict]:
        """
        Extract text from a PDF file, returning text per page.
        
        Args:
            pdf_bytes: Raw PDF file bytes
        
        Returns:
            List of dicts with 'page_number' and 'text' keys
        """
        pages = []
        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text("text")
                if text.strip():
                    pages.append({
                        "page_number": page_num + 1,
                        "text": text.strip()
                    })
            doc.close()
            logger.info(f"Extracted text from {len(pages)} pages")
        except Exception as e:
            logger.error(f"PDF extraction failed: {e}")
            raise ValueError(f"Failed to parse PDF: {e}")
        
        if not pages:
            raise ValueError("PDF contains no extractable text")
        
        return pages
    
    def chunk_text(
        self,
        pages: list[dict],
        chunk_size: int = CHUNK_SIZE,
        chunk_overlap: int = CHUNK_OVERLAP
    ) -> list[dict]:
        """
        Split extracted page text into overlapping chunks.
        
        Args:
            pages: List of page dicts from extract_text_from_pdf
            chunk_size: Maximum characters per chunk
            chunk_overlap: Overlap between consecutive chunks
        
        Returns:
            List of dicts with 'chunk_text', 'chunk_index', and 'page_number'
        """
        chunks = []
        chunk_index = 0
        
        for page in pages:
            text = page["text"]
            page_number = page["page_number"]
            
            # Split into chunks with overlap
            start = 0
            while start < len(text):
                end = start + chunk_size
                chunk_text = text[start:end].strip()
                
                if chunk_text:
                    chunks.append({
                        "chunk_text": chunk_text,
                        "chunk_index": chunk_index,
                        "page_number": page_number,
                    })
                    chunk_index += 1
                
                start += chunk_size - chunk_overlap
        
        logger.info(f"Created {len(chunks)} chunks from {len(pages)} pages")
        return chunks
    
    # ==========================================================================
    # EMBEDDING
    # ==========================================================================
    
    async def embed_text(self, text: str) -> list[float]:
        """
        Generate an embedding vector for a single text string.
        
        Args:
            text: The text to embed
        
        Returns:
            768-dimensional embedding vector
        """
        if not self.client:
            raise ValueError("GEMINI_API_KEY not configured")
        
        result = await self.client.aio.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=text,
            config=types.EmbedContentConfig(
                task_type="RETRIEVAL_DOCUMENT",
                output_dimensionality=EMBEDDING_DIMENSION,
            )
        )
        return result.embeddings[0].values
    
    async def embed_query(self, query: str) -> list[float]:
        """
        Generate an embedding vector for a query/description.
        Uses RETRIEVAL_QUERY task type for better search performance.
        
        Args:
            query: The query/description text
        
        Returns:
            768-dimensional embedding vector
        """
        if not self.client:
            raise ValueError("GEMINI_API_KEY not configured")
        
        result = await self.client.aio.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=query,
            config=types.EmbedContentConfig(
                task_type="RETRIEVAL_QUERY",
                output_dimensionality=EMBEDDING_DIMENSION,
            )
        )
        return result.embeddings[0].values
    
    async def embed_texts_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for multiple texts in batch.
        
        Args:
            texts: List of texts to embed
        
        Returns:
            List of 768-dimensional embedding vectors
        """
        if not self.client:
            raise ValueError("GEMINI_API_KEY not configured")
        
        # Gemini supports batch embedding
        result = await self.client.aio.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=texts,
            config=types.EmbedContentConfig(
                task_type="RETRIEVAL_DOCUMENT",
                output_dimensionality=EMBEDDING_DIMENSION,
            )
        )
        return [emb.values for emb in result.embeddings]
    
    # ==========================================================================
    # CHUNK STORAGE
    # ==========================================================================
    
    async def process_and_store_pdf(
        self,
        session: Session,
        chat_id: str,
        pdf_bytes: bytes
    ) -> list[DocumentChunk]:
        """
        Full pipeline: extract text → chunk → embed → store in DB.
        
        Args:
            session: Database session
            chat_id: ID of the chat this PDF belongs to
            pdf_bytes: Raw PDF file bytes
        
        Returns:
            List of created DocumentChunk records
        """
        # Step 1: Extract text from PDF
        pages = self.extract_text_from_pdf(pdf_bytes)
        
        # Step 2: Chunk the text
        chunks_data = self.chunk_text(pages)
        
        if not chunks_data:
            raise ValueError("No text chunks could be created from the PDF")
        
        # Step 3: Embed all chunks in batch
        chunk_texts = [c["chunk_text"] for c in chunks_data]
        
        # UPDATED: Reduced batch size to 20 to prevent Rate Limiting (429) on Free Tier
        all_embeddings = []
        batch_size = 20
        
        logger.info(f"Embedding {len(chunk_texts)} chunks in batches of {batch_size}...")
        
        for i in range(0, len(chunk_texts), batch_size):
            batch = chunk_texts[i:i + batch_size]
            batch_num = i // batch_size + 1
            try:
                embeddings = await self.embed_texts_batch(batch)
                all_embeddings.extend(embeddings)
                logger.info(f"  Batch {batch_num} done ({len(batch)} chunks)")
            except Exception as e:
                logger.error(f"Batch embedding failed at index {i}: {e}")
                raise
            
            # Throttle between batches to stay under rate limits
            if i + batch_size < len(chunk_texts):
                await asyncio.sleep(1)
        
        # Step 4: Store chunks with embeddings
        db_chunks = []
        for chunk_data, embedding in zip(chunks_data, all_embeddings):
            chunk = DocumentChunk(
                chat_id=chat_id,
                chunk_text=chunk_data["chunk_text"],
                chunk_index=chunk_data["chunk_index"],
                page_number=chunk_data["page_number"],
                embedding=embedding,
            )
            session.add(chunk)
            db_chunks.append(chunk)
        
        session.commit()
        for chunk in db_chunks:
            session.refresh(chunk)
        
        logger.info(f"Stored {len(db_chunks)} chunks for chat {chat_id}")
        return db_chunks
    
    # ==========================================================================
    # SIMILARITY SEARCH
    # ==========================================================================
    
    async def find_similar_chunks(
        self,
        session: Session,
        chat_id: str,
        query_text: str,
        top_k: int = 5
    ) -> list[dict]:
        """
        Find the most similar chunks to a query within a specific chat's chunks.
        
        Uses pgvector's cosine distance operator for similarity search.
        
        Args:
            session: Database session
            chat_id: ID of the chat to search within
            query_text: The description/query to match against chunks
            top_k: Number of top results to return
        
        Returns:
            List of dicts with 'chunk', 'similarity' keys, sorted by similarity desc
        """
        # Embed the query
        query_embedding = await self.embed_query(query_text)
        
        # Use pgvector cosine distance search
        from sqlalchemy import text
        
        # NOTE: Use \:\: to escape Postgres cast (::vector) so SQLAlchemy
        # doesn't treat it as a named parameter.
        query = text("""
            SELECT id, chunk_text, chunk_index, page_number,
                   1 - (embedding <=> cast(:query_vector AS vector)) AS similarity
            FROM document_chunks
            WHERE chat_id = :chat_id
            ORDER BY embedding <=> cast(:query_vector AS vector)
            LIMIT :top_k
        """)
        
        result = session.execute(query, {
            "query_vector": str(query_embedding),
            "chat_id": chat_id,
            "top_k": top_k,
        })
        
        matches = []
        for row in result:
            matches.append({
                "chunk_id": row.id,
                "chunk_text": row.chunk_text,
                "chunk_index": row.chunk_index,
                "page_number": row.page_number,
                "similarity": float(row.similarity),
            })
        
        logger.info(f"Found {len(matches)} similar chunks for chat {chat_id}")
        return matches


# Singleton instance
embedding_service = EmbeddingService()
