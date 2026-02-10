# ==============================================================================
# Catalog Search API Endpoints
# ==============================================================================
# Endpoints for the Reverse Catalog Search feature ("The Librarian").
#
# Endpoints:
#   POST /upload-and-search  - Upload PDF + description → full RAG pipeline
#   GET  /{chat_id}/status   - Check search status
#   GET  /{chat_id}/results  - Get full results with predictions & vendors
#   GET  /history            - Get user's search history
#   POST /predictions/{id}/search - Trigger web search for a specific prediction
# ==============================================================================

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlmodel import Session
from typing import Optional

from app.core.database import get_session
from app.core.security import get_current_user, TokenData
from app.schemas.catalog_search import (
    CatalogSearchResponse,
    CatalogSearchStatus,
    PredictionSearchRequest,
)
from app.schemas.chat import ChatRead
from app.schemas.prediction import PredictionWithResults
from app.controllers import catalog_controller

router = APIRouter()


@router.post(
    "/upload-and-search",
    response_model=CatalogSearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Upload PDF catalog and search for parts",
    description="""
Upload a product catalog/manual PDF along with a description of the part
you're looking for. The system will:

1. **Parse** the PDF and extract text
2. **Chunk** the text into segments
3. **Embed** chunks using Gemini gemini-embedding-001
4. **Match** your description against chunks using cosine similarity
5. **Identify** specific parts using Gemini AI
6. **Search** the web for vendor listings (optional)

**Supported file types:** PDF only, max 20 MB

**Response includes:**
- Predicted parts with confidence scores
- Vendor listings with prices and links (if web search enabled)
- Processing time

**Tip:** Be specific in your description. Instead of "I need a bearing",
say "I need the main shaft bearing from page 15 of the pump assembly".
""",
)
async def upload_and_search(
    file: UploadFile = File(
        ...,
        description="PDF catalog/manual file (max 20 MB)"
    ),
    description: str = Form(
        ...,
        min_length=1,
        max_length=2000,
        description="Description of the part you need from the catalog"
    ),
    run_web_search: bool = Form(
        default=True,
        description="Whether to search the web for vendors after identification"
    ),
    max_web_results: int = Form(
        default=5,
        ge=1,
        le=20,
        description="Maximum vendor results per predicted part"
    ),
    location: str = Form(
        default="Sri Lanka",
        description="Target location for vendor search"
    ),
    session: Session = Depends(get_session),
    current_user: TokenData = Depends(get_current_user),
) -> CatalogSearchResponse:
    """Upload a PDF catalog and search for replacement parts."""
    return await catalog_controller.upload_and_search_controller(
        session=session,
        user_id=current_user.user_id,
        file=file,
        description=description,
        run_web_search=run_web_search,
        max_web_results=max_web_results,
        location=location,
    )


@router.get(
    "/{chat_id}/status",
    response_model=CatalogSearchStatus,
    summary="Check search status",
    description="Check the current status of a catalog search session.",
)
async def get_search_status(
    chat_id: str,
    session: Session = Depends(get_session),
    current_user: TokenData = Depends(get_current_user),
) -> CatalogSearchStatus:
    """Get the status of a search session."""
    return await catalog_controller.get_chat_status_controller(
        session=session,
        chat_id=chat_id,
        user_id=current_user.user_id,
    )


@router.get(
    "/{chat_id}/results",
    response_model=CatalogSearchResponse,
    summary="Get search results",
    description="Get the full results of a completed catalog search, including predictions and vendor listings.",
)
async def get_search_results(
    chat_id: str,
    session: Session = Depends(get_session),
    current_user: TokenData = Depends(get_current_user),
) -> CatalogSearchResponse:
    """Get full results of a search session."""
    return await catalog_controller.get_chat_results_controller(
        session=session,
        chat_id=chat_id,
        user_id=current_user.user_id,
    )


@router.get(
    "/history",
    response_model=list[ChatRead],
    summary="Get search history",
    description="Get the user's catalog search history.",
)
async def get_search_history(
    chat_type: Optional[str] = Query(
        default=None,
        description="Filter by chat type: 'camera', 'reverse_catalog', 'text'"
    ),
    skip: int = Query(default=0, ge=0, description="Number of records to skip"),
    limit: int = Query(default=20, ge=1, le=100, description="Max records to return"),
    session: Session = Depends(get_session),
    current_user: TokenData = Depends(get_current_user),
) -> list[ChatRead]:
    """Get user's search history."""
    return await catalog_controller.get_user_chats_controller(
        session=session,
        user_id=current_user.user_id,
        chat_type=chat_type,
        skip=skip,
        limit=limit,
    )


@router.post(
    "/predictions/{prediction_id}/search",
    response_model=PredictionWithResults,
    summary="Search vendors for a prediction",
    description="""
Trigger a web search for a specific predicted part. Use this when:
- The initial search was done without web search enabled
- You want to refresh vendor results
- The user selected a specific prediction and wants to buy it

Returns the prediction with updated vendor listings.
""",
)
async def search_prediction_vendors(
    prediction_id: str,
    location: str = Query(default="Sri Lanka", description="Target location"),
    max_results: int = Query(default=5, ge=1, le=20, description="Max vendor results"),
    session: Session = Depends(get_session),
    current_user: TokenData = Depends(get_current_user),
) -> PredictionWithResults:
    """Search for vendors for a specific predicted part."""
    return await catalog_controller.search_prediction_controller(
        session=session,
        user_id=current_user.user_id,
        prediction_id=prediction_id,
        location=location,
        max_results=max_results,
    )
