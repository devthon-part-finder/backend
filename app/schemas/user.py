# ==============================================================================
# User Schemas - Request/Response Validation
# ==============================================================================
# This module defines Pydantic models for API request/response validation.
#
# WHY SEPARATE FROM SQLMODEL DATABASE MODELS?
# ===========================================
# While SQLModel CAN serve as both database model and Pydantic schema,
# we separate them for security and flexibility:
#
# 1. NEVER expose hashed_password in API responses
# 2. Accept plain password in registration, but store hashed
# 3. Different validation rules for create vs update
# 4. Control exactly what fields are visible to API consumers
#
# SCHEMA NAMING CONVENTION:
#   - UserBase: Common fields shared across schemas
#   - UserCreate: For POST /register (includes plain password)
#   - UserRead: For GET responses (excludes password entirely)
#   - UserUpdate: For PATCH requests (all fields optional)
#
# FLOW EXAMPLE:
#   1. Client sends: {"email": "a@b.com", "username": "ab", "password": "secret"}
#   2. UserCreate validates the request (password field)
#   3. Service hashes password → User model (hashed_password field)
#   4. User saved to database
#   5. UserRead returned to client (no password field at all)
# ==============================================================================

from uuid import UUID
from pydantic import BaseModel, Field, EmailStr, ConfigDict
from typing import Optional
from datetime import datetime


class UserBase(BaseModel):
    """
    Base schema with fields common to multiple User operations.
    
    Note: password is NOT here because:
    - Create needs plain password (to hash)
    - Read should NEVER include password
    - Update may or may not change password
    """
    email: EmailStr = Field(
        ...,
        description="User's email address",
        json_schema_extra={"example": "john@example.com"}
    )
    
    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        description="User's display name",
        json_schema_extra={"example": "johndoe"}
    )


class UserCreate(UserBase):
    """
    Schema for user registration.
    
    Includes plain-text password that will be hashed before storage.
    NEVER store this password directly - always hash it first!
    
    Usage:
        @router.post("/register")
        def register(user: UserCreate):
            hashed = hash_password(user.password)
            db_user = User(
                email=user.email,
                username=user.username,
                hashed_password=hashed
            )
            ...
    """
    password: str = Field(
        ...,
        min_length=8,
        max_length=100,
        description="Plain-text password (will be hashed)",
        json_schema_extra={"example": "securepassword123"}
    )


class UserUpdate(BaseModel):
    """
    Schema for updating an existing user.
    
    All fields are optional - only provided fields will be updated.
    This allows partial updates (PATCH semantics).
    
    Note: password update should go through a separate endpoint
    that requires current password verification.
    """
    email: Optional[EmailStr] = Field(
        default=None,
        description="New email address"
    )
    
    username: Optional[str] = Field(
        default=None,
        min_length=3,
        max_length=50,
        description="New username"
    )
    
    is_active: Optional[bool] = Field(
        default=None,
        description="Account active status"
    )


class UserRead(UserBase):
    """
    Schema for returning user data in API responses.
    
    IMPORTANT: This schema intentionally EXCLUDES password fields.
    Never return hashed_password to clients!
    
    Usage:
        @router.get("/users/{user_id}", response_model=UserRead)
        def get_user(user_id: str):
            ...
    """
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID = Field(
        ...,
        description="Unique identifier"
    )
    
    is_active: bool = Field(
        default=True,
        description="Whether the account is active"
    )
    
    created_at: datetime = Field(
        ...,
        description="When the user registered"
    )
    
    updated_at: datetime = Field(
        ...,
        description="When the user was last updated"
    )


class UserList(BaseModel):
    """
    Simplified schema for list views.
    
    Contains only essential fields for displaying user lists.
    """
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    email: str
    username: str
    is_active: bool = True


class UserSearchResponse(BaseModel):
    """
    Paginated response for user list endpoints.
    """
    users: list[UserList] = Field(
        ...,
        description="List of users"
    )
    
    total: int = Field(
        ...,
        ge=0,
        description="Total number of users"
    )
    
    page: int = Field(
        default=1,
        ge=1,
        description="Current page number"
    )
    
    per_page: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Users per page"
    )


# ==============================================================================
# AUTHENTICATION SCHEMAS
# ==============================================================================

class UserLogin(BaseModel):
    """
    Schema for login requests.
    """
    email: EmailStr = Field(
        ...,
        description="User's email address",
        json_schema_extra={"example": "john@example.com"}
    )
    
    password: str = Field(
        ...,
        description="User's password",
        json_schema_extra={"example": "securepassword123"}
    )


class PasswordChange(BaseModel):
    """
    Schema for password change requests.
    
    Requires current password for verification.
    """
    current_password: str = Field(
        ...,
        description="Current password for verification"
    )
    
    new_password: str = Field(
        ...,
        min_length=8,
        max_length=100,
        description="New password"
    )


# ==============================================================================
# HOW TO ADD NEW SCHEMAS:
# ==============================================================================
# 1. Identify what data shape you need (create, read, update, auth)
# 2. Create a new class inheriting from BaseModel
# 3. Define fields with type annotations and Field() for validation
# 4. Use EmailStr for email validation (from pydantic import EmailStr)
# 5. Use model_config = ConfigDict(from_attributes=True) for ORM conversion
#
# SECURITY REMINDERS:
#   - NEVER include password/hashed_password in Read schemas
#   - ALWAYS validate password strength in Create schemas
#   - Use separate endpoints for password changes with verification
# ==============================================================================
