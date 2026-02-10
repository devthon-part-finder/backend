# ==============================================================================
# Chat Schemas - Request/Response Validation
# ==============================================================================

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime


class ChatBase(BaseModel):
    """Common chat fields."""
    chat_type: str = Field(
        ...,
        description="Type of search: 'camera', 'reverse_catalog', or 'text'"
    )
    description: Optional[str] = Field(
        default=None,
        description="User's description of the part they need"
    )


class ChatCreate(ChatBase):
    """Schema for creating a chat (used internally, not directly by API)."""
    user_id: str = Field(..., description="ID of the user")
    media_url: Optional[str] = None
    media_type: Optional[str] = None
    original_filename: Optional[str] = None


class ChatRead(ChatBase):
    """Schema for returning a chat in API responses."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    status: str
    media_url: Optional[str] = None
    media_type: Optional[str] = None
    original_filename: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ChatUpdate(BaseModel):
    """Schema for updating a chat."""
    status: Optional[str] = None
    error_message: Optional[str] = None
    media_url: Optional[str] = None
