# ==============================================================================
# Models Package
# ==============================================================================
# This package contains SQLModel definitions for database tables.
# SQLModel combines SQLAlchemy ORM with Pydantic validation.
#
# Key Concepts:
#   - Each model class represents a database table
#   - Use `table=True` in class definition for database tables
#   - Models without `table=True` are Pydantic-only (for validation)
#
# Import all models here for easy access and to ensure they're registered
# with SQLModel metadata before create_db_and_tables() is called.
# ==============================================================================

from app.models.user import User
from app.models.password_reset_code import PasswordResetCode
from app.models.chat import Chat, ChatType, ChatStatus
from app.models.prediction import Prediction, PredictionType
from app.models.document_chunk import DocumentChunk
from app.models.search_result import SearchResult

__all__ = [
    "User",
    "PasswordResetCode",
    "Chat",
    "ChatType",
    "ChatStatus",
    "Prediction",
    "PredictionType",
    "DocumentChunk",
    "SearchResult",
]
