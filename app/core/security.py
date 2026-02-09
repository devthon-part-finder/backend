# ==============================================================================
# Security and Authentication Module
# ==============================================================================
# This module provides authentication and authorization utilities.
# It includes JWT token handling, password hashing, and dependency
# functions for protecting routes.
#
# IMPORTANT: This is a template/placeholder. Customize based on your
# authentication requirements (JWT, API keys, OAuth, etc.)
#
# Current Implementation:
#   - JWT token creation and verification
#   - Password hashing with bcrypt (placeholder)
#   - API key authentication (placeholder)
#   - FastAPI dependencies for protected routes
# ==============================================================================

from datetime import datetime, timedelta, timezone
from typing import Optional, Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
from jose import JWTError, jwt
from pydantic import BaseModel
from passlib.context import CryptContext
import logging

from app.core.config import settings

# Configure logging
logger = logging.getLogger(__name__)

# ==============================================================================
# SECURITY SCHEMES
# ==============================================================================
# Define how authentication credentials are extracted from requests.
# HTTPBearer: Extract JWT from "Authorization: Bearer <token>" header
# APIKeyHeader: Extract API key from a custom header

# JWT Bearer token authentication
bearer_scheme = HTTPBearer(
    scheme_name="JWT",
    description="Enter your JWT token",
    auto_error=False,  # Don't auto-raise error; we'll handle it
)

# API Key authentication (alternative to JWT)
api_key_header = APIKeyHeader(
    name="X-API-Key",
    scheme_name="API Key",
    description="Enter your API key",
    auto_error=False,
)


# ==============================================================================
# TOKEN MODELS
# ==============================================================================

class TokenData(BaseModel):
    """Data extracted from a validated JWT token."""
    user_id: Optional[str] = None
    email: Optional[str] = None
    scopes: list[str] = []


class Token(BaseModel):
    """Response model for token endpoints."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # Seconds until expiration
    refresh_token: Optional[str] = None
    refresh_expires_in: Optional[int] = None


# ==============================================================================
# JWT TOKEN FUNCTIONS
# ==============================================================================

def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create a JWT access token.
    
    Args:
        data: Dictionary of claims to encode in the token.
              Should include 'sub' (subject, typically user_id).
        expires_delta: Optional custom expiration time.
                      Defaults to ACCESS_TOKEN_EXPIRE_MINUTES from config.
    
    Returns:
        Encoded JWT token string.
    
    Example:
        token = create_access_token(
            data={"sub": user.id, "email": user.email}
        )
    """
    to_encode = data.copy()
    if "sub" in to_encode:
        to_encode["sub"] = str(to_encode["sub"])
    
    # Set expiration time
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),  # Issued at
        "type": "access",
    })
    
    # Encode the token
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )
    
    logger.debug(f"Created access token, expires at {expire}")
    return encoded_jwt


def create_refresh_token(
    data: dict,
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create a JWT refresh token.
    """
    to_encode = data.copy()
    if "sub" in to_encode:
        to_encode["sub"] = str(to_encode["sub"])

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )

    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "refresh",
    })

    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )

    logger.debug(f"Created refresh token, expires at {expire}")
    return encoded_jwt


def verify_token(token: str, token_type: Optional[str] = "access") -> Optional[TokenData]:
    """
    Verify and decode a JWT token.
    
    Args:
        token: The JWT token string to verify.
    
    Returns:
        TokenData if valid, None if invalid.
    
    Raises:
        JWTError: If token is malformed or signature invalid.
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        
        token_kind: Optional[str] = payload.get("type")
        if token_type == "access" and token_kind is not None and token_kind != "access":
            logger.warning("Token type mismatch (expected access)")
            return None
        if token_type == "refresh" and token_kind != "refresh":
            logger.warning("Token type mismatch (expected refresh)")
            return None

        user_id: str = payload.get("sub")
        email: str = payload.get("email")
        scopes: list = payload.get("scopes", [])
        
        if user_id is None:
            logger.warning("Token missing 'sub' claim")
            return None
        
        return TokenData(user_id=user_id, email=email, scopes=scopes)
        
    except JWTError as e:
        logger.warning(f"Token verification failed: {e}")
        return None


def verify_refresh_token(token: str) -> Optional[TokenData]:
    """
    Verify and decode a refresh token.
    """
    return verify_token(token, token_type="refresh")


# ============================================================================== 
# PASSWORD HASHING
# ============================================================================== 

# Passlib context for bcrypt hashing with SHA-256 pre-hash
# Avoids bcrypt 72-byte password limit while retaining bcrypt verification.
pwd_context = CryptContext(schemes=["bcrypt_sha256"], deprecated="auto")

def hash_password(password: str) -> str:
    """
    Hash a password for storage.
    
    Uses passlib[bcrypt].
    
    Usage:
        hashed = hash_password("user_password")
        # Store hashed in database
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash.
    
    Uses passlib[bcrypt].
    """
    return pwd_context.verify(plain_password, hashed_password)


# ==============================================================================
# FASTAPI DEPENDENCIES
# ==============================================================================
# These functions are used with Depends() to protect routes.

async def get_current_user(
    credentials: Annotated[
        Optional[HTTPAuthorizationCredentials],
        Depends(bearer_scheme)
    ]
) -> TokenData:
    """
    Dependency to get the current authenticated user from JWT token.
    
    Usage:
        @router.get("/protected")
        def protected_route(current_user: TokenData = Depends(get_current_user)):
            return {"user_id": current_user.user_id}
    
    Raises:
        HTTPException 401: If token is missing or invalid.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    if credentials is None:
        logger.warning("No credentials provided")
        raise credentials_exception
    
    token_data = verify_token(credentials.credentials)
    
    if token_data is None:
        logger.warning("Invalid token provided")
        raise credentials_exception
    
    return token_data


async def get_current_user_optional(
    credentials: Annotated[
        Optional[HTTPAuthorizationCredentials],
        Depends(bearer_scheme)
    ]
) -> Optional[TokenData]:
    """
    Dependency to optionally get the current user.
    Returns None if no valid token provided (instead of raising exception).
    
    Useful for routes that work for both authenticated and anonymous users.
    
    Usage:
        @router.get("/items")
        def get_items(current_user: Optional[TokenData] = Depends(get_current_user_optional)):
            if current_user:
                # Show personalized results
            else:
                # Show public results
    """
    if credentials is None:
        return None
    
    return verify_token(credentials.credentials)


async def verify_api_key(
    api_key: Annotated[Optional[str], Depends(api_key_header)]
) -> str:
    """
    Dependency to verify API key authentication.
    
    Usage:
        @router.get("/api-protected")
        def api_protected_route(api_key: str = Depends(verify_api_key)):
            return {"message": "Authenticated via API key"}
    
    TODO: Implement actual API key validation against database or config.
    """
    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key is required",
        )
    
    # TODO: Validate API key against stored keys
    # Example: Check against database or list in settings
    # valid_keys = settings.API_KEYS.split(",")
    # if api_key not in valid_keys:
    #     raise HTTPException(status_code=401, detail="Invalid API key")
    
    logger.warning("API key validation not fully implemented!")
    return api_key


# ==============================================================================
# ROLE-BASED ACCESS CONTROL (RBAC) - PLACEHOLDER
# ==============================================================================
# Example of how to implement role-based permissions:
#
# def require_role(required_role: str):
#     """
#     Dependency factory for role-based access control.
#     
#     Usage:
#         @router.delete("/items/{id}")
#         def delete_item(
#             id: int,
#             current_user: TokenData = Depends(require_role("admin"))
#         ):
#             ...
#     """
#     async def role_checker(
#         current_user: TokenData = Depends(get_current_user)
#     ) -> TokenData:
#         if required_role not in current_user.scopes:
#             raise HTTPException(
#                 status_code=status.HTTP_403_FORBIDDEN,
#                 detail=f"Role '{required_role}' required"
#             )
#         return current_user
#     return role_checker


# ==============================================================================
# HOW TO USE AUTHENTICATION IN ROUTES:
# ==============================================================================
# 
# 1. REQUIRE AUTHENTICATION (JWT):
#    @router.get("/protected")
#    def protected(user: TokenData = Depends(get_current_user)):
#        return {"user_id": user.user_id}
#
# 2. OPTIONAL AUTHENTICATION:
#    @router.get("/public")
#    def public(user: Optional[TokenData] = Depends(get_current_user_optional)):
#        if user:
#            return {"message": f"Hello {user.email}"}
#        return {"message": "Hello anonymous"}
#
# 3. API KEY AUTHENTICATION:
#    @router.get("/api-endpoint")
#    def api_endpoint(key: str = Depends(verify_api_key)):
#        return {"authenticated": True}
#
# 4. CREATE LOGIN ENDPOINT:
#    @router.post("/login")
#    def login(username: str, password: str):
#        # Verify credentials against database
#        # If valid, create and return token
#        token = create_access_token({"sub": user.id, "email": user.email})
#        return {"access_token": token, "token_type": "bearer"}
# ==============================================================================
