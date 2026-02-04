# ==============================================================================
# User Model - Database Table Definition
# ==============================================================================
# This model represents a user in the system using SQLModel.
# SQLModel combines SQLAlchemy ORM with Pydantic validation.
#
# WHY SEPARATE MODELS AND SCHEMAS?
# ================================
# SQLModel CAN be used for both database models AND API schemas, but we
# recommend separating them for these reasons:
#
# 1. SECURITY: You don't want to expose hashed_password in API responses.
#    With separate schemas, you control exactly what's returned.
#
# 2. FLEXIBILITY: API request/response shapes often differ from DB schema.
#    - Create: email + password (plain text, to be hashed)
#    - Read: email + username (no password ever)
#    - Update: partial fields only
#    - DB: email + username + hashed_password + timestamps
#
# 3. VALIDATION DIFFERENCES: API validation (min length, regex) differs
#    from DB constraints (max length, not null).
#
# 4. TEAM CLARITY: Backend team owns models/, frontend-facing team owns schemas/
#
# WHEN TO USE SINGLE MODEL (SQLModel for both):
# - Simple internal tools
# - Prototypes/MVPs
# - When DB schema exactly matches API schema
#
# For production apps with sensitive data (like passwords), ALWAYS separate.
# ==============================================================================

from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime, timezone
import uuid


class User(SQLModel, table=True):
    """
    Represents a user in the database.
    
    This is the core User model with authentication fields.
    
    Table name: 'users' (explicit via __tablename__)
    
    Attributes:
        id: Unique identifier (UUID)
        email: User's email address (unique, used for login)
        username: Display name
        hashed_password: Bcrypt-hashed password (NEVER store plain text!)
        is_active: Whether the user can log in
        created_at: When the user registered
        updated_at: When the user was last modified
    """
    
    __tablename__ = "users"
    
    # ==========================================================================
    # PRIMARY KEY
    # ==========================================================================
    id: Optional[str] = Field(
        default_factory=lambda: str(uuid.uuid4()),
        primary_key=True,
        description="Unique identifier for the user"
    )
    
    # ==========================================================================
    # AUTHENTICATION FIELDS
    # ==========================================================================
    email: str = Field(
        ...,
        max_length=255,
        description="User's email address (unique)",
        index=True,
        unique=True,  # Enforced at database level
    )
    
    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        description="User's display name",
        index=True,
    )
    
    hashed_password: str = Field(
        ...,
        max_length=255,
        description="Bcrypt-hashed password (never store plain text!)"
    )
    
    # ==========================================================================
    # STATUS
    # ==========================================================================
    is_active: bool = Field(
        default=True,
        description="Whether the user account is active",
        index=True,
    )
    
    # ==========================================================================
    # TIMESTAMPS
    # ==========================================================================
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the user was created"
    )
    
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the user was last updated"
    )


# ==============================================================================
# PGVECTOR NOTE (For Future Reference)
# ==============================================================================
# This User model does NOT need vector embeddings. However, if you create
# models that need similarity search (e.g., Product, Image), here's how:
#
# 1. Enable pgvector extension in Supabase SQL Editor:
#    CREATE EXTENSION IF NOT EXISTS vector;
#
# 2. Import Vector type:
#    from pgvector.sqlalchemy import Vector
#    from sqlalchemy import Column
#
# 3. Add embedding field to your model:
#    embedding: Optional[list[float]] = Field(
#        default=None,
#        sa_column=Column(Vector(512))  # 512 = embedding dimension
#    )
#
# 4. Create an index for faster searches:
#    CREATE INDEX ON your_table 
#    USING ivfflat (embedding vector_cosine_ops)
#    WITH (lists = 100);
#
# 5. Query similar items:
#    SELECT * FROM your_table
#    ORDER BY embedding <=> '[0.1, 0.2, ...]'::vector
#    LIMIT 10;
#
# Operators:
#   <->  : L2 (Euclidean) distance
#   <=>  : Cosine distance (recommended for normalized embeddings)
#   <#>  : Inner product
# ==============================================================================


# ==============================================================================
# HOW TO USE THIS MODEL:
# ==============================================================================
#
# CREATING A USER:
#   from app.models.user import User
#   from app.core.security import hash_password
#   
#   user = User(
#       email="john@example.com",
#       username="johndoe",
#       hashed_password=hash_password("plain_password")
#   )
#   
#   session.add(user)
#   session.commit()
#   session.refresh(user)
#
# QUERYING USERS:
#   from sqlmodel import select
#   
#   # Get user by email
#   statement = select(User).where(User.email == "john@example.com")
#   user = session.exec(statement).first()
#   
#   # Get all active users
#   statement = select(User).where(User.is_active == True)
#   users = session.exec(statement).all()
#
# UPDATING A USER:
#   user.username = "new_username"
#   session.add(user)
#   session.commit()
# ==============================================================================
