# ==============================================================================
# User Controller - Request/Response Orchestration
# ==============================================================================
# Controllers sit between routes and services. They:
#   - Coordinate service calls
#   - Handle error responses
#   - Format data for the client
#
# Architecture Flow:
#   Route → Controller → Service(s) → Database
# ==============================================================================

from sqlmodel import Session
from fastapi import HTTPException, status
from typing import Optional
import logging

from app.models.user import User
from app.schemas.user import (
    UserCreate,
    UserUpdate,
    UserRead,
    UserList,
    UserSearchResponse,
    UserLogin,
    PasswordChange
)
from app.services import user_service
from app.core.security import create_access_token, Token

# Configure logging
logger = logging.getLogger(__name__)


# ==============================================================================
# CRUD CONTROLLERS
# ==============================================================================

def create_user_controller(session: Session, user_data: UserCreate) -> UserRead:
    """
    Handle user registration request.
    
    Args:
        session: Database session
        user_data: Validated registration data
    
    Returns:
        Created user as UserRead schema (no password)
    
    Raises:
        HTTPException 400: If email already exists
        HTTPException 500: If database error occurs
    """
    try:
        user = user_service.create_user(session, user_data)
        logger.info(f"Controller: Created user {user.id}")
        return UserRead.model_validate(user)
    except ValueError as e:
        logger.warning(f"Registration failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error creating user: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create user: {str(e)}"
        )


def get_user_controller(session: Session, user_id: str) -> UserRead:
    """
    Handle get single user request.
    
    Args:
        session: Database session
        user_id: User UUID from path parameter
    
    Returns:
        User as UserRead schema
    
    Raises:
        HTTPException 404: If user not found
    """
    user = user_service.get_user(session, user_id)
    
    if not user:
        logger.warning(f"User not found: {user_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with id '{user_id}' not found"
        )
    
    return UserRead.model_validate(user)


def list_users_controller(
    session: Session,
    page: int = 1,
    per_page: int = 20,
    is_active: Optional[bool] = None
) -> UserSearchResponse:
    """
    Handle paginated user list request.
    
    Args:
        session: Database session
        page: Page number (1-indexed)
        per_page: Users per page
        is_active: Optional active status filter
    
    Returns:
        Paginated response with users and metadata
    """
    skip = (page - 1) * per_page
    
    users, total = user_service.get_users(
        session,
        skip=skip,
        limit=per_page,
        is_active=is_active
    )
    
    users_list = [UserList.model_validate(user) for user in users]
    
    return UserSearchResponse(
        users=users_list,
        total=total,
        page=page,
        per_page=per_page
    )


def update_user_controller(
    session: Session,
    user_id: str,
    user_update: UserUpdate
) -> UserRead:
    """
    Handle user update request.
    
    Args:
        session: Database session
        user_id: User UUID from path parameter
        user_update: Partial update data
    
    Returns:
        Updated user as UserRead schema
    
    Raises:
        HTTPException 404: If user not found
    """
    user = user_service.update_user(session, user_id, user_update)
    
    if not user:
        logger.warning(f"User not found for update: {user_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with id '{user_id}' not found"
        )
    
    logger.info(f"Controller: Updated user {user_id}")
    return UserRead.model_validate(user)


def delete_user_controller(
    session: Session,
    user_id: str,
    hard_delete: bool = False
) -> dict:
    """
    Handle user deletion request.
    
    Args:
        session: Database session
        user_id: User UUID from path parameter
        hard_delete: If True, permanently delete
    
    Returns:
        Success message
    
    Raises:
        HTTPException 404: If user not found
    """
    deleted = user_service.delete_user(session, user_id, hard_delete)
    
    if not deleted:
        logger.warning(f"User not found for deletion: {user_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with id '{user_id}' not found"
        )
    
    action = "permanently deleted" if hard_delete else "deactivated"
    logger.info(f"Controller: User {user_id} {action}")
    
    return {"message": f"User {user_id} {action} successfully"}


# ==============================================================================
# AUTHENTICATION CONTROLLERS
# ==============================================================================

def login_controller(session: Session, login_data: UserLogin) -> Token:
    """
    Handle login request.
    
    Args:
        session: Database session
        login_data: Email and password
    
    Returns:
        JWT access token
    
    Raises:
        HTTPException 401: If credentials are invalid
    """
    user = user_service.authenticate_user(
        session,
        login_data.email,
        login_data.password
    )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # Create access token
    access_token = create_access_token(data={"sub": user.id, "email": user.email})
    
    from app.core.config import settings
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


def change_password_controller(
    session: Session,
    user_id: str,
    password_data: PasswordChange
) -> dict:
    """
    Handle password change request.
    
    Args:
        session: Database session
        user_id: Current user's ID (from auth token)
        password_data: Current and new passwords
    
    Returns:
        Success message
    
    Raises:
        HTTPException 400: If current password is wrong
    """
    success = user_service.change_password(
        session,
        user_id,
        password_data.current_password,
        password_data.new_password
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    return {"message": "Password changed successfully"}


# ==============================================================================
# HOW TO ADD NEW CONTROLLERS:
# ==============================================================================
# 1. Accept session and validated request data as parameters
# 2. Call service function(s) to perform business logic
# 3. Handle errors and convert to HTTPException
# 4. Convert service results to response schemas
# 5. Log important operations
#
# Common HTTP Status Codes:
#   - 200: Success (GET, PUT, PATCH)
#   - 201: Created (POST)
#   - 400: Bad Request (validation error, business rule violation)
#   - 401: Unauthorized (invalid credentials)
#   - 403: Forbidden (insufficient permissions)
#   - 404: Not Found
#   - 500: Internal Server Error
# ==============================================================================
