# ==============================================================================
# Core Package
# ==============================================================================
# This package contains core application components:
#   - config.py: Application settings and environment configuration
#   - database.py: Database connection, session management, and utilities
#   - security.py: Authentication, authorization, and security utilities
#
# These modules are foundational and should be imported by other packages.
# ==============================================================================

from app.core.config import settings
from app.core.database import get_session, create_db_and_tables

__all__ = ["settings", "get_session", "create_db_and_tables"]
