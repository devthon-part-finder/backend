# ==============================================================================
# Catalog Search Schemas - Reverse Catalog Search API
# ==============================================================================
# Schemas specific to the Reverse Catalog Search feature.
# The upload endpoint accepts a PDF file + description via multipart form.
# ==============================================================================

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime

from app.schemas.chat import ChatRead
from app.schemas.prediction import PredictionRead, PredictionWithResults


class CatalogSearchResponse(BaseModel):
    """
    Full response for a reverse catalog search.
    Includes the chat, predictions, and optionally search results.
    """
    model_config = ConfigDict(from_attributes=True)

    chat: ChatRead = Field(..., description="The search session")
    predictions: list[PredictionWithResults] = Field(
        default_factory=list,
        description="Predicted parts with confidence scores and vendor results"
    )
    processing_time_ms: Optional[int] = Field(
        default=None,
        description="Total processing time in milliseconds"
    )


class CatalogSearchStatus(BaseModel):
    """Status response for polling a search session."""
    chat_id: str
    status: str
    predictions_count: int = 0
    error_message: Optional[str] = None


class PredictionSearchRequest(BaseModel):
    """Request to trigger web search for a specific prediction."""
    prediction_id: str = Field(..., description="ID of the prediction to search for")
    location: str = Field(default="Sri Lanka", description="Target location for search")
    max_results: int = Field(default=5, ge=1, le=20, description="Max vendor results")
