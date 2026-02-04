# ==============================================================================
# Application Configuration
# ==============================================================================
# This module uses Pydantic Settings to manage environment configuration.
# All settings are loaded from environment variables or .env file.
#
# Usage:
#   from app.core.config import settings
#   print(settings.DATABASE_URL)
#
# To add new settings:
#   1. Add the field with type annotation below
#   2. Add the corresponding environment variable to .env
#   3. Use `settings.YOUR_SETTING` anywhere in the app
# ==============================================================================

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    Pydantic Settings automatically:
    - Loads values from environment variables
    - Reads from .env file (via python-dotenv)
    - Validates types and provides defaults
    """
    
    # ==========================================================================
    # DATABASE CONFIGURATION
    # ==========================================================================
    # Connection string for Supabase PostgreSQL
    # Format: postgresql://user:password@host:port/database
    DATABASE_URL: str
    
    # Echo SQL queries to console (useful for debugging, disable in production)
    DATABASE_ECHO: bool = False
    
    # ==========================================================================
    # API CONFIGURATION
    # ==========================================================================
    # API metadata for OpenAPI docs
    API_TITLE: str = "Devthon PartFinder API"
    API_VERSION: str = "1.0.0"
    API_DESCRIPTION: str = "AI-powered visual search engine for industrial hardware"
    
    # API prefix for all versioned endpoints
    API_V1_PREFIX: str = "/api/v1"
    
    # ==========================================================================
    # SECURITY CONFIGURATION
    # ==========================================================================
    # Secret key for JWT token signing (generate with: openssl rand -hex 32)
    # IMPORTANT: Change this in production!
    SECRET_KEY: str = "your-super-secret-key-change-in-production"
    
    # JWT token expiration time in minutes
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Algorithm for JWT encoding
    JWT_ALGORITHM: str = "HS256"
    
    # ==========================================================================
    # ML MODEL CONFIGURATION
    # ==========================================================================
    # Path to YOLOv8 model weights file
    # Example: "models/yolov8n.pt" or absolute path
    YOLO_MODEL_PATH: Optional[str] = None
    
    # Confidence threshold for YOLO detections (0.0 - 1.0)
    YOLO_CONFIDENCE_THRESHOLD: float = 0.5
    
    # Device for model inference: "cpu", "cuda", "cuda:0", etc.
    ML_DEVICE: str = "cpu"
    
    # ==========================================================================
    # VECTOR SEARCH CONFIGURATION (pgvector)
    # ==========================================================================
    # Dimension of embedding vectors (depends on your embedding model)
    # Common values: 384 (MiniLM), 512, 768 (BERT), 1536 (OpenAI)
    EMBEDDING_DIMENSION: int = 512
    
    # Number of results to return for similarity search
    VECTOR_SEARCH_LIMIT: int = 10
    
    # ==========================================================================
    # ENVIRONMENT
    # ==========================================================================
    # Environment mode: "development", "staging", "production"
    ENVIRONMENT: str = "development"
    
    # Enable debug mode (more verbose logging, detailed errors)
    DEBUG: bool = True
    
    # ==========================================================================
    # CORS CONFIGURATION (if needed for frontend)
    # ==========================================================================
    # Allowed origins for CORS (comma-separated in env, parsed as list)
    # Example: "http://localhost:3000,https://yourfrontend.com"
    CORS_ORIGINS: str = "http://localhost:3000"
    
    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS_ORIGINS string into a list."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
    
    # ==========================================================================
    # PYDANTIC SETTINGS CONFIGURATION
    # ==========================================================================
    model_config = SettingsConfigDict(
        # Load from .env file in project root
        env_file=".env",
        # .env file encoding
        env_file_encoding="utf-8",
        # Case-insensitive environment variable matching
        case_sensitive=False,
        # Allow extra fields (useful for future additions)
        extra="ignore",
    )


# Create a global settings instance
# This is imported throughout the application
settings = Settings()


# ==============================================================================
# HOW TO ADD NEW CONFIGURATION:
# ==============================================================================
# 1. Add a new field above with type annotation:
#    MY_NEW_SETTING: str = "default_value"
#
# 2. Add the environment variable to your .env file:
#    MY_NEW_SETTING="actual_value"
#
# 3. Use it in your code:
#    from app.core.config import settings
#    print(settings.MY_NEW_SETTING)
#
# For sensitive values (API keys, passwords), NEVER commit defaults.
# Instead, set them to Optional[str] = None and validate at runtime.
# ==============================================================================
