# ==============================================================================
# Prediction Model - Identified Part from Search
# ==============================================================================
# This model represents a predicted/identified part from any search type.
# Shared by camera search, reverse catalog search, and text search.
#
# Each prediction:
#   - Belongs to one Chat
#   - Has a name, description, and confidence score
#   - Links to zero or more SearchResults (vendor listings)
#   - May have an image URL (top web result image)
# ==============================================================================

from sqlmodel import SQLModel, Field
from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from typing import Optional
from datetime import datetime, timezone
from enum import Enum
import uuid


class PredictionType(str, Enum):
    """How this prediction was generated."""
    CAMERA = "camera"                # From image/camera detection
    REVERSE_CATALOG = "reverse_catalog"  # From PDF + description RAG
    TEXT = "text"                     # From text description only


class Prediction(SQLModel, table=True):
    """
    Represents an identified/predicted part from a search session.
    
    After a search is performed (camera, catalog, or text), the system
    generates one or more predictions - each being a candidate part
    the user might be looking for, ranked by confidence score.
    
    Table name: 'predictions'
    """
    
    __tablename__ = "predictions"
    
    # Primary key (UUID)
    id: Optional[str] = Field(
        default_factory=lambda: str(uuid.uuid4()),
        sa_column=Column(
            PgUUID(as_uuid=False),
            primary_key=True,
            default=lambda: str(uuid.uuid4()),
        ),
        description="Unique identifier for the prediction"
    )
    
    # Foreign key to chats table (UUID)
    chat_id: str = Field(
        sa_column=Column(
            PgUUID(as_uuid=False),
            ForeignKey("chats.id"),
            nullable=False,
            index=True,
        ),
        description="ID of the chat this prediction belongs to"
    )
    
    # Prediction type discriminator
    prediction_type: str = Field(
        ...,
        index=True,
        description="How this prediction was generated: 'camera', 'reverse_catalog', 'text'"
    )
    
    # Predicted part info
    part_name: str = Field(
        ...,
        description="Name of the predicted/identified part"
    )
    
    part_number: Optional[str] = Field(
        default=None,
        description="Part number if identified (e.g., 'SKF 6205-2RS')"
    )
    
    manufacturer: Optional[str] = Field(
        default=None,
        description="Manufacturer name if identified"
    )
    
    description: Optional[str] = Field(
        default=None,
        description="Description of the predicted part"
    )
    
    # Confidence score (0.0 - 1.0)
    confidence_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Confidence score of the prediction (0.0 - 1.0)"
    )
    
    # Image URL from top web result
    image_url: Optional[str] = Field(
        default=None,
        description="URL to an image of the predicted part (from web search)"
    )
    
    # Which chunk matched (for reverse catalog)
    matched_chunk_text: Optional[str] = Field(
        default=None,
        description="The PDF chunk text that matched (for reverse catalog search)"
    )
    
    # Rank in the results
    rank: int = Field(
        default=0,
        description="Rank/position of this prediction in the results"
    )
    
    # Web search completed?
    web_search_completed: bool = Field(
        default=False,
        description="Whether web search for vendors has been completed"
    )
    
    # Timestamps
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the prediction was created"
    )
