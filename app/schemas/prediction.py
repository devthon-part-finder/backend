# ==============================================================================
# Prediction Schemas - Request/Response Validation
# ==============================================================================

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime


class PredictionRead(BaseModel):
    """Schema for returning a prediction in API responses."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    chat_id: str
    prediction_type: str
    part_name: str
    part_number: Optional[str] = None
    manufacturer: Optional[str] = None
    description: Optional[str] = None
    confidence_score: float
    image_url: Optional[str] = None
    matched_chunk_text: Optional[str] = None
    rank: int
    web_search_completed: bool
    created_at: datetime


class PredictionWithResults(PredictionRead):
    """Prediction with its associated search results."""
    search_results: list["SearchResultRead"] = Field(default_factory=list)


# Import here to avoid circular dependency
from app.schemas.search_result import SearchResultRead  # noqa: E402

# Rebuild model after import
PredictionWithResults.model_rebuild()
