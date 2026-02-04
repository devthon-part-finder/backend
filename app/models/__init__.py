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

# Add new model imports here as you create them:
# from app.models.product import Product
# from app.models.category import Category

__all__ = ["User"]
