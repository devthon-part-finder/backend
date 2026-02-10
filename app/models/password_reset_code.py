# ============================================================================== 
# Password Reset Code Model - Database Table Definition
# ==============================================================================

from __future__ import annotations

from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime, timezone
from uuid import UUID
import uuid


class PasswordResetCode(SQLModel, table=True):
    __tablename__ = "password_reset_codes"

    id: Optional[UUID] = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        description="Unique identifier for the reset code"
    )

    user_id: UUID = Field(
        ...,
        foreign_key="users.id",
        index=True,
        description="User ID associated with this reset code"
    )

    email: str = Field(
        ...,
        max_length=255,
        index=True,
        description="Email address the reset code was sent to"
    )

    code_hash: str = Field(
        ...,
        max_length=255,
        description="Hashed 6-digit verification code"
    )

    expires_at: datetime = Field(
        ...,
        index=True,
        description="When the reset code expires"
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the reset code was created"
    )

    used_at: Optional[datetime] = Field(
        default=None,
        index=True,
        description="When the reset code was used (null if unused)"
    )
