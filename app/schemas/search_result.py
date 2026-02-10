# ==============================================================================
# Search Result Schemas - Request/Response Validation
# ==============================================================================

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime


class SearchResultRead(BaseModel):
    """Schema for returning a search result in API responses."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    prediction_id: str
    vendor_name: str
    product_title: str
    description: Optional[str] = None
    price: Optional[float] = None
    currency: str = "LKR"
    availability: str = "Unknown"
    product_url: str
    image_url: Optional[str] = None
    location: Optional[str] = None
    source_type: str
    confidence_score: float
    created_at: datetime
