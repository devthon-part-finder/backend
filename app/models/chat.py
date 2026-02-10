# ==============================================================================
# Chat Model - Shared Search Session Table
# ==============================================================================
# This model represents a single search session (chat). It is shared by:
#   - Camera Search (image upload → part identification)
#   - Reverse Catalog Search (PDF upload + description → part identification)
#   - Text Search (description only → part identification)
#
# Each chat:
#   - Belongs to one user
#   - Has one media attachment (PDF or photo) or none (text search)
#   - Links to one or more Predictions
#   - Has a status indicating whether the search succeeded
# ==============================================================================

from sqlmodel import SQLModel, Field
from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from typing import Optional
from datetime import datetime, timezone
from enum import Enum
import uuid


class ChatType(str, Enum):
    """Type of search that initiated this chat."""
    CAMERA = "camera"
    REVERSE_CATALOG = "reverse_catalog"
    TEXT = "text"


class ChatStatus(str, Enum):
    """Status of the search session."""
    PENDING = "pending"          # Search initiated, processing
    PROCESSING = "processing"    # Actively running (PDF parsing, embedding, etc.)
    COMPLETED = "completed"      # Search finished successfully
    FAILED = "failed"            # Search failed


class Chat(SQLModel, table=True):
    """
    Represents a search session (chat) in the database.
    
    A chat is created when a user initiates any type of search.
    It holds the input (media + description) and links to predictions (output).
    
    Table name: 'chats'
    """
    
    __tablename__ = "chats"
    
    # Primary key (UUID to match users table)
    id: Optional[str] = Field(
        default_factory=lambda: str(uuid.uuid4()),
        sa_column=Column(
            PgUUID(as_uuid=False),
            primary_key=True,
            default=lambda: str(uuid.uuid4()),
        ),
        description="Unique identifier for the chat"
    )
    
    # Foreign key to users table (UUID to match users.id)
    user_id: str = Field(
        sa_column=Column(
            PgUUID(as_uuid=False),
            ForeignKey("users.id"),
            nullable=False,
            index=True,
        ),
        description="ID of the user who initiated this search"
    )
    
    # Search type discriminator
    chat_type: str = Field(
        ...,
        index=True,
        description="Type of search: 'camera', 'reverse_catalog', or 'text'"
    )
    
    # Status of the search
    status: str = Field(
        default=ChatStatus.PENDING.value,
        index=True,
        description="Status: 'pending', 'processing', 'completed', 'failed'"
    )
    
    # User's description of what they need
    description: Optional[str] = Field(
        default=None,
        description="User's description of the part they need"
    )
    
    # Media URL (PDF in Supabase storage, or photo URL)
    media_url: Optional[str] = Field(
        default=None,
        description="URL to the uploaded media (PDF or photo) in Supabase storage"
    )
    
    # Media type for quick filtering
    media_type: Optional[str] = Field(
        default=None,
        description="MIME type of the media: 'application/pdf', 'image/jpeg', etc."
    )
    
    # Original filename
    original_filename: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Original filename of the uploaded media"
    )
    
    # Error message if search failed
    error_message: Optional[str] = Field(
        default=None,
        description="Error message if the search failed"
    )
    
    # Timestamps
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the chat was created"
    )
    
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the chat was last updated"
    )
