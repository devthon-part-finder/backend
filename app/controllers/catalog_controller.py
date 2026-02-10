# ==============================================================================
# Catalog Search Controller - Request/Response Orchestration
# ==============================================================================
# This controller handles HTTP concerns for the Reverse Catalog Search:
#   - File upload handling
#   - Exception → HTTPException conversion
#   - Response formatting with Pydantic schemas
#
# Flow:
#   Endpoint → Controller → CatalogService → EmbeddingService + WebAgent
# ==============================================================================

from fastapi import HTTPException, UploadFile, status
import logging
from typing import Optional
from sqlmodel import Session

from app.services.catalog_service import catalog_service
from app.schemas.catalog_search import (
    CatalogSearchResponse,
    CatalogSearchStatus,
)
from app.schemas.chat import ChatRead
from app.schemas.prediction import PredictionRead, PredictionWithResults
from app.schemas.search_result import SearchResultRead

logger = logging.getLogger(__name__)

# Max PDF size: 20 MB
MAX_PDF_SIZE = 20 * 1024 * 1024


async def upload_and_search_controller(
    session: Session,
    user_id: str,
    file: UploadFile,
    description: str,
    run_web_search: bool = True,
    max_web_results: int = 5,
    location: str = "Sri Lanka",
) -> CatalogSearchResponse:
    """
    Controller for the full reverse catalog search pipeline.
    
    1. Validate PDF file
    2. Create chat
    3. Run full RAG pipeline
    4. Return structured response
    """
    # Validate file type
    if not file.content_type or not file.content_type.startswith("application/pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only PDF files are accepted. Got: {file.content_type}"
        )
    
    # Validate description
    if not description or not description.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Description is required. Describe what part you need from the catalog."
        )
    
    # Read file
    try:
        pdf_bytes = await file.read()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read uploaded file: {e}"
        )
    
    # Validate file size
    if len(pdf_bytes) > MAX_PDF_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size is {MAX_PDF_SIZE // (1024*1024)} MB"
        )
    
    if len(pdf_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty"
        )
    
    try:
        # Create chat record
        chat = catalog_service.create_chat(
            session=session,
            user_id=user_id,
            description=description.strip(),
            chat_type="reverse_catalog",
            media_type=file.content_type,
            original_filename=file.filename,
        )
        
        # Run full pipeline
        result = await catalog_service.run_catalog_search(
            session=session,
            chat_id=chat.id,
            pdf_bytes=pdf_bytes,
            description=description.strip(),
            run_web_search=run_web_search,
            max_web_results=max_web_results,
            location=location,
        )
        
        # Build response with search results
        predictions_with_results = []
        for prediction in result["predictions"]:
            search_results = catalog_service.get_search_results(session, prediction.id)
            pred_read = PredictionWithResults(
                **PredictionRead.model_validate(prediction).model_dump(),
                search_results=[SearchResultRead.model_validate(sr) for sr in search_results],
            )
            predictions_with_results.append(pred_read)
        
        return CatalogSearchResponse(
            chat=ChatRead.model_validate(result["chat"]),
            predictions=predictions_with_results,
            processing_time_ms=result.get("processing_time_ms"),
        )
        
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.exception(f"Catalog search failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during catalog search. Please try again."
        )


async def get_chat_status_controller(
    session: Session,
    chat_id: str,
    user_id: str,
) -> CatalogSearchStatus:
    """Get the status of a search session."""
    chat = catalog_service.get_chat(session, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    if chat.user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    predictions = catalog_service.get_predictions(session, chat_id)
    
    return CatalogSearchStatus(
        chat_id=chat.id,
        status=chat.status,
        predictions_count=len(predictions),
        error_message=chat.error_message,
    )


async def get_chat_results_controller(
    session: Session,
    chat_id: str,
    user_id: str,
) -> CatalogSearchResponse:
    """Get the full results of a completed search."""
    chat = catalog_service.get_chat(session, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    if chat.user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    predictions = catalog_service.get_predictions(session, chat_id)
    
    predictions_with_results = []
    for prediction in predictions:
        search_results = catalog_service.get_search_results(session, prediction.id)
        pred_read = PredictionWithResults(
            **PredictionRead.model_validate(prediction).model_dump(),
            search_results=[SearchResultRead.model_validate(sr) for sr in search_results],
        )
        predictions_with_results.append(pred_read)
    
    return CatalogSearchResponse(
        chat=ChatRead.model_validate(chat),
        predictions=predictions_with_results,
    )


async def get_user_chats_controller(
    session: Session,
    user_id: str,
    chat_type: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
) -> list[ChatRead]:
    """Get all chats for a user."""
    chats = catalog_service.get_user_chats(
        session, user_id, chat_type=chat_type, skip=skip, limit=limit
    )
    return [ChatRead.model_validate(c) for c in chats]


async def search_prediction_controller(
    session: Session,
    user_id: str,
    prediction_id: str,
    location: str = "Sri Lanka",
    max_results: int = 5,
) -> PredictionWithResults:
    """Trigger web search for a specific prediction."""
    prediction = catalog_service.get_prediction(session, prediction_id)
    if not prediction:
        raise HTTPException(status_code=404, detail="Prediction not found")
    
    # Verify ownership
    chat = catalog_service.get_chat(session, prediction.chat_id)
    if not chat or chat.user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    try:
        await catalog_service.search_for_prediction_by_id(
            session, prediction_id, location=location, max_results=max_results
        )
    except Exception as e:
        logger.error(f"Web search failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Web search failed. Please try again."
        )
    
    # Reload and return
    prediction = catalog_service.get_prediction(session, prediction_id)
    search_results = catalog_service.get_search_results(session, prediction_id)
    
    return PredictionWithResults(
        **PredictionRead.model_validate(prediction).model_dump(),
        search_results=[SearchResultRead.model_validate(sr) for sr in search_results],
    )
