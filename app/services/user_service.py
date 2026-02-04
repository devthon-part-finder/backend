# ==============================================================================
# User Service - Business Logic Layer
# ==============================================================================
# This service contains all business logic for User operations.
# Services handle database operations and business rules.
#
# Architecture Pattern:
#   Route → Controller → Service → Database
#
# Services should be:
#   - Stateless (no instance variables)
#   - Testable (accept session as parameter)
#   - Focused on one domain (Users in this case)
# ==============================================================================

from sqlmodel import Session, select
from sqlalchemy import func
from typing import Optional
import logging

from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate
from app.core.security import hash_password, verify_password

# Configure logging
logger = logging.getLogger(__name__)


# ==============================================================================
# CRUD OPERATIONS
# ==============================================================================

def create_user(session: Session, user_data: UserCreate) -> User:
    """
    Create a new user in the database.
    
    Args:
        session: Database session
        user_data: Validated user creation data (includes plain password)
    
    Returns:
        The created User with generated ID
    
    Raises:
        ValueError: If email already exists
    
    Example:
        user_data = UserCreate(
            email="john@example.com",
            username="johndoe",
            password="securepassword"
        )
        new_user = create_user(session, user_data)
    """
    # Check if email already exists
    existing_user = get_user_by_email(session, user_data.email)
    if existing_user:
        raise ValueError(f"User with email '{user_data.email}' already exists")
    
    # Hash the password before storing
    hashed = hash_password(user_data.password)
    
    # Create User model (note: we use hashed_password, not password)
    user = User(
        email=user_data.email,
        username=user_data.username,
        hashed_password=hashed
    )
    
    session.add(user)
    session.commit()
    session.refresh(user)
    
    logger.info(f"Created user: {user.id} - {user.email}")
    return user


def get_user(session: Session, user_id: str) -> Optional[User]:
    """
    Retrieve a single user by ID.
    
    Args:
        session: Database session
        user_id: The user's unique identifier
    
    Returns:
        The User if found, None otherwise
    """
    statement = select(User).where(User.id == user_id)
    user = session.exec(statement).first()
    
    if user:
        logger.debug(f"Retrieved user: {user_id}")
    else:
        logger.debug(f"User not found: {user_id}")
    
    return user


def get_user_by_email(session: Session, email: str) -> Optional[User]:
    """
    Retrieve a user by email address.
    
    Useful for:
    - Login authentication
    - Checking if email exists during registration
    
    Args:
        session: Database session
        email: User's email address
    
    Returns:
        The User if found, None otherwise
    """
    statement = select(User).where(User.email == email)
    return session.exec(statement).first()


def get_users(
    session: Session,
    skip: int = 0,
    limit: int = 20,
    is_active: Optional[bool] = None
) -> tuple[list[User], int]:
    """
    Retrieve a paginated list of users.
    
    Args:
        session: Database session
        skip: Number of users to skip (for pagination)
        limit: Maximum users to return
        is_active: Optional filter by active status
    
    Returns:
        Tuple of (users list, total count)
    """
    # Build base query
    statement = select(User)
    count_statement = select(func.count()).select_from(User)
    
    # Apply active filter if provided
    if is_active is not None:
        statement = statement.where(User.is_active == is_active)
        count_statement = count_statement.where(User.is_active == is_active)
    
    # Get total count
    total = session.exec(count_statement).one()
    
    # Apply pagination
    statement = statement.offset(skip).limit(limit)
    
    # Execute query
    users = session.exec(statement).all()
    
    logger.debug(f"Retrieved {len(users)} users (total: {total})")
    return list(users), total


def update_user(
    session: Session,
    user_id: str,
    user_update: UserUpdate
) -> Optional[User]:
    """
    Update an existing user.
    
    Only fields provided in user_update will be modified.
    
    Args:
        session: Database session
        user_id: The user's unique identifier
        user_update: Fields to update
    
    Returns:
        The updated User, or None if not found
    """
    user = get_user(session, user_id)
    if not user:
        return None
    
    # Update only provided fields
    update_data = user_update.model_dump(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(user, field, value)
    
    session.add(user)
    session.commit()
    session.refresh(user)
    
    logger.info(f"Updated user: {user_id}")
    return user


def delete_user(session: Session, user_id: str, hard_delete: bool = False) -> bool:
    """
    Delete a user.
    
    Args:
        session: Database session
        user_id: The user's unique identifier
        hard_delete: If True, permanently remove. If False, soft delete.
    
    Returns:
        True if deleted, False if user not found
    """
    user = get_user(session, user_id)
    if not user:
        return False
    
    if hard_delete:
        session.delete(user)
        logger.info(f"Hard deleted user: {user_id}")
    else:
        user.is_active = False
        session.add(user)
        logger.info(f"Soft deleted user: {user_id}")
    
    session.commit()
    return True


# ==============================================================================
# AUTHENTICATION HELPERS
# ==============================================================================

def authenticate_user(session: Session, email: str, password: str) -> Optional[User]:
    """
    Authenticate a user by email and password.
    
    Args:
        session: Database session
        email: User's email
        password: Plain-text password to verify
    
    Returns:
        The User if authentication succeeds, None otherwise
    
    Example:
        user = authenticate_user(session, "john@example.com", "password123")
        if user:
            token = create_access_token({"sub": user.id})
            return {"access_token": token}
        else:
            raise HTTPException(401, "Invalid credentials")
    """
    user = get_user_by_email(session, email)
    
    if not user:
        logger.debug(f"Authentication failed: user not found - {email}")
        return None
    
    if not user.is_active:
        logger.debug(f"Authentication failed: user inactive - {email}")
        return None
    
    if not verify_password(password, user.hashed_password):
        logger.debug(f"Authentication failed: invalid password - {email}")
        return None
    
    logger.info(f"User authenticated: {email}")
    return user


def change_password(
    session: Session,
    user_id: str,
    current_password: str,
    new_password: str
) -> bool:
    """
    Change a user's password.
    
    Requires verification of current password for security.
    
    Args:
        session: Database session
        user_id: The user's ID
        current_password: Current password for verification
        new_password: New password to set
    
    Returns:
        True if password changed, False if verification failed
    """
    user = get_user(session, user_id)
    if not user:
        return False
    
    # Verify current password
    if not verify_password(current_password, user.hashed_password):
        logger.warning(f"Password change failed: invalid current password - {user_id}")
        return False
    
    # Update to new password
    user.hashed_password = hash_password(new_password)
    session.add(user)
    session.commit()
    
    logger.info(f"Password changed for user: {user_id}")
    return True


# ==============================================================================
# HOW TO ADD NEW SERVICE FUNCTIONS:
# ==============================================================================
# 1. Define function with session as first parameter
# 2. Use SQLModel select() for queries
# 3. Log important operations
# 4. Return typed results (use Optional[] if may not exist)
# 5. Handle errors gracefully (or let them bubble up to controller)
#
# Example - Find users by username pattern:
#
# def search_users_by_username(
#     session: Session,
#     pattern: str,
#     limit: int = 10
# ) -> list[User]:
#     """Search users whose username contains the pattern."""
#     statement = select(User).where(
#         User.username.ilike(f"%{pattern}%"),
#         User.is_active == True
#     ).limit(limit)
#     return list(session.exec(statement).all())
# ==============================================================================
