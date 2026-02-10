# ==============================================================================
# Search Result Model - Vendor Listings for Predictions
# ==============================================================================
# This model stores web search results (vendor listings) for each prediction.
# One or many search results link to one prediction.
#
# These results come from the Web Agent Service and represent actual
# vendor/shop listings where the predicted part can be purchased.
# ==============================================================================

from sqlmodel import SQLModel, Field
from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from typing import Optional
from datetime import datetime, timezone
import uuid


class SearchResult(SQLModel, table=True):
    """
    Stores a single vendor/shop listing for a predicted part.
    
    Each search result represents a product listing from a vendor,
    found by the Web Agent Service (Serper + Gemini).
    
    Table name: 'search_results'
    """
    
    __tablename__ = "search_results"
    
    # Primary key (UUID)
    id: Optional[str] = Field(
        default_factory=lambda: str(uuid.uuid4()),
        sa_column=Column(
            PgUUID(as_uuid=False),
            primary_key=True,
            default=lambda: str(uuid.uuid4()),
        ),
        description="Unique identifier for the search result"
    )
    
    # Foreign key to predictions table (UUID)
    prediction_id: str = Field(
        sa_column=Column(
            PgUUID(as_uuid=False),
            ForeignKey("predictions.id"),
            nullable=False,
            index=True,
        ),
        description="ID of the prediction this result belongs to"
    )
    
    # Vendor info
    vendor_name: str = Field(
        ...,
        description="Name of the vendor/seller"
    )
    
    # Product info
    product_title: str = Field(
        ...,
        description="Title/name of the product listing"
    )
    
    description: Optional[str] = Field(
        default=None,
        description="Short description of the product"
    )
    
    # Pricing
    price: Optional[float] = Field(
        default=None,
        description="Price of the product"
    )
    
    currency: str = Field(
        default="LKR",
        max_length=10,
        description="Currency code (e.g., LKR, USD)"
    )
    
    # Availability
    availability: str = Field(
        default="Unknown",
        description="Availability status: 'In Stock', 'Out of Stock', 'Unknown'"
    )
    
    # URLs
    product_url: str = Field(
        ...,
        description="URL to the product page on the vendor's website"
    )
    
    image_url: Optional[str] = Field(
        default=None,
        description="URL to the product image"
    )
    
    # Location
    location: Optional[str] = Field(
        default=None,
        description="Vendor location / shipping origin"
    )
    
    # Source tracking
    source_type: str = Field(
        default="serper_snippet",
        description="How this result was obtained: 'serper_snippet' or 'page_scrape'"
    )
    
    confidence_score: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Confidence score for this result"
    )
    
    # Timestamps
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the search result was created"
    )
