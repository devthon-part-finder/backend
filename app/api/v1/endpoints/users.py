# ==============================================================================
# Users API Endpoints - v1
# ==============================================================================
# This module defines REST API endpoints for User operations.
# All endpoints are prefixed with /api/v1/users
#
# Endpoint Summary:
#   POST   /users/register     - Register a new user
#   POST   /users/login        - Authenticate and get token
#   GET    /users              - List all users (admin)
#   GET    /users/me           - Get current user profile
#   GET    /users/{id}         - Get a single user
#   PATCH  /users/{id}         - Update a user
#   DELETE /users/{id}         - Delete a user
#   POST   /users/me/password  - Change password
#
# Architecture Flow:
#   Route (this file) → Controller → Service → Database
# ==============================================================================

from fastapi import APIRouter, Depends, Query, Path, status
from sqlmodel import Session
from typing import Optional

from app.core.database import get_session
from app.core.security import get_current_user, get_current_user_optional, TokenData, Token
from app.schemas.user import (
    UserCreate,
    UserUpdate,
    UserRead,
    UserList,
    UserSearchResponse,
    UserLogin,
    PasswordChange,
    RefreshTokenRequest
)
from app.controllers import user_controller

# Create the router instance
router = APIRouter()


# ==============================================================================
# AUTHENTICATION ENDPOINTS
# ==============================================================================

@router.post(
    "/register",
    response_model=Token,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Create a new user account. Returns access and refresh tokens."
)
def register(
    user_data: UserCreate,
    session: Session = Depends(get_session)
):
    """
    Register a new user.
    
    - **email**: Valid email address (must be unique)
    - **username**: Display name (3-50 characters)
    - **password**: Password (min 8 characters, will be hashed)
    
    Returns access and refresh tokens.
    """
    return user_controller.register_with_tokens_controller(session, user_data)


@router.post(
    "/login",
    response_model=Token,
    summary="Login",
    description="Authenticate with email and password to receive a JWT token."
)
def login(
    login_data: UserLogin,
    session: Session = Depends(get_session)
):
    """
    Authenticate and get access token.
    
    - **email**: User's email address
    - **password**: User's password
    
    Returns JWT access token for authenticated requests.
    """
    return user_controller.login_controller(session, login_data)


@router.post(
    "/refresh",
    response_model=Token,
    summary="Refresh access token",
    description="Exchange a refresh token for a new access token."
)
def refresh_token(
    refresh_data: RefreshTokenRequest,
    session: Session = Depends(get_session)
):
    """
    Refresh access token using a valid refresh token.
    """
    return user_controller.refresh_token_controller(session, refresh_data)


# ==============================================================================
# CURRENT USER ENDPOINTS
# ==============================================================================

@router.get(
    "/me",
    response_model=UserRead,
    summary="Get current user",
    description="Get the currently authenticated user's profile."
)
def get_current_user_profile(
    current_user: TokenData = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    Get current user's profile.
    
    Requires authentication (Bearer token).
    """
    return user_controller.get_user_controller(session, current_user.user_id)


@router.post(
    "/me/password",
    summary="Change password",
    description="Change the current user's password."
)
def change_password(
    password_data: PasswordChange,
    current_user: TokenData = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    Change current user's password.
    
    - **current_password**: Current password for verification
    - **new_password**: New password (min 8 characters)
    
    Requires authentication.
    """
    return user_controller.change_password_controller(
        session,
        current_user.user_id,
        password_data
    )


# ==============================================================================
# USER CRUD ENDPOINTS
# ==============================================================================

@router.get(
    "/",
    response_model=UserSearchResponse,
    summary="List all users",
    description="Get a paginated list of all users. May require admin privileges."
)
def list_users(
    page: int = Query(default=1, ge=1, description="Page number"),
    per_page: int = Query(default=20, ge=1, le=100, description="Users per page"),
    is_active: Optional[bool] = Query(default=None, description="Filter by active status"),
    session: Session = Depends(get_session),
    # Uncomment to require authentication:
    # current_user: TokenData = Depends(get_current_user)
):
    """
    List all users with pagination.
    
    - **page**: Page number (starting from 1)
    - **per_page**: Number of users per page (max 100)
    - **is_active**: Optional filter for active/inactive users
    """
    return user_controller.list_users_controller(
        session=session,
        page=page,
        per_page=per_page,
        is_active=is_active
    )


@router.get(
    "/{user_id}",
    response_model=UserRead,
    summary="Get user by ID",
    description="Retrieve a single user by their unique identifier."
)
def get_user(
    user_id: str = Path(..., description="The user's unique identifier (UUID)"),
    session: Session = Depends(get_session)
):
    """
    Get a single user by ID.
    
    Returns 404 if user not found.
    """
    return user_controller.get_user_controller(session, user_id)


@router.patch(
    "/{user_id}",
    response_model=UserRead,
    summary="Update a user",
    description="Update an existing user. Only provided fields will be modified."
)
def update_user(
    user_id: str = Path(..., description="The user's unique identifier"),
    user_update: UserUpdate = ...,
    session: Session = Depends(get_session),
    # Uncomment to require authentication:
    # current_user: TokenData = Depends(get_current_user)
):
    """
    Partially update a user.
    
    Only fields included in the request body will be updated.
    """
    return user_controller.update_user_controller(session, user_id, user_update)


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete a user",
    description="Delete a user (soft delete by default)."
)
def delete_user(
    user_id: str = Path(..., description="The user's unique identifier"),
    hard_delete: bool = Query(default=False, description="Permanently delete if true"),
    session: Session = Depends(get_session),
    # Uncomment to require authentication:
    # current_user: TokenData = Depends(get_current_user)
):
    """
    Delete a user.
    
    - **hard_delete=false** (default): Marks user as inactive
    - **hard_delete=true**: Permanently removes the user
    """
    return user_controller.delete_user_controller(session, user_id, hard_delete)


# ==============================================================================
# HOW TO ADD NEW ENDPOINTS:
# ==============================================================================
# 1. Add decorator: @router.get(), .post(), .patch(), .delete()
# 2. Define path parameters: "/{user_id}"
# 3. Define query parameters: Query(default=..., description=...)
# 4. Add request body with Pydantic schema
# 5. Add session dependency: session: Session = Depends(get_session)
# 6. Add auth if needed: user: TokenData = Depends(get_current_user)
# 7. Call the appropriate controller function
# 8. Document with docstring (shows in OpenAPI docs)
# ==============================================================================
