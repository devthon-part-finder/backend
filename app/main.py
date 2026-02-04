# ==============================================================================
# Devthon PartFinder API - Main Application Entry Point
# ==============================================================================
# This is the main FastAPI application file. It:
#   - Creates the FastAPI application instance
#   - Configures middleware (CORS, logging, etc.)
#   - Includes all API routers
#   - Defines startup/shutdown events
#
# To run the application:
#   uvicorn app.main:app --reload
#
# Or with specific host/port:
#   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
#
# API Documentation:
#   - Swagger UI: http://localhost:8000/docs
#   - ReDoc: http://localhost:8000/redoc
#   - OpenAPI JSON: http://localhost:8000/openapi.json
# ==============================================================================

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.core.config import settings
from app.core.database import create_db_and_tables
from app.api.v1 import api_v1_router

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# ==============================================================================
# APPLICATION LIFESPAN (Startup/Shutdown Events)
# ==============================================================================
# The lifespan context manager handles startup and shutdown logic.
# This is the modern replacement for @app.on_event("startup")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    
    Startup:
        - Create database tables
        - Initialize ML models (optional)
        - Establish connections to external services
    
    Shutdown:
        - Close connections
        - Cleanup resources
    """
    # -------------------------------------------------------------------------
    # STARTUP
    # -------------------------------------------------------------------------
    logger.info("=" * 60)
    logger.info("Starting Devthon PartFinder API...")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Debug mode: {settings.DEBUG}")
    logger.info("=" * 60)
    
    # Create database tables
    logger.info("Initializing database...")
    try:
        create_db_and_tables()
        logger.info("Database initialized successfully!")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        # Continue anyway - tables might already exist
    
    # Initialize ML models (optional - uncomment when ready)
    # logger.info("Loading ML models...")
    # try:
    #     from app.ml_engine.inference import init_ml_models
    #     init_ml_models()
    #     logger.info("ML models loaded successfully!")
    # except Exception as e:
    #     logger.warning(f"ML model initialization failed: {e}")
    #     logger.warning("Continuing without ML models...")
    
    logger.info("Startup complete! API is ready.")
    
    # -------------------------------------------------------------------------
    # APPLICATION RUNNING
    # -------------------------------------------------------------------------
    yield  # Application runs here
    
    # -------------------------------------------------------------------------
    # SHUTDOWN
    # -------------------------------------------------------------------------
    logger.info("Shutting down Devthon PartFinder API...")
    # Add cleanup logic here if needed:
    # - Close database connections
    # - Unload ML models
    # - Cancel background tasks
    logger.info("Shutdown complete!")


# ==============================================================================
# CREATE FASTAPI APPLICATION
# ==============================================================================

app = FastAPI(
    title=settings.API_TITLE,
    version=settings.API_VERSION,
    description=settings.API_DESCRIPTION,
    lifespan=lifespan,
    # OpenAPI documentation settings
    docs_url="/docs",           # Swagger UI
    redoc_url="/redoc",         # ReDoc
    openapi_url="/openapi.json",
)


# ==============================================================================
# MIDDLEWARE CONFIGURATION
# ==============================================================================

# CORS (Cross-Origin Resource Sharing)
# Required for frontend applications on different domains
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],      # Allow all HTTP methods
    allow_headers=["*"],      # Allow all headers
)

# Add more middleware as needed:
# - Request logging
# - Response compression (GZipMiddleware)
# - Rate limiting
# - Request ID tracking

# Example: Request timing middleware (uncomment to enable)
# @app.middleware("http")
# async def add_process_time_header(request, call_next):
#     import time
#     start_time = time.time()
#     response = await call_next(request)
#     process_time = time.time() - start_time
#     response.headers["X-Process-Time"] = str(process_time)
#     return response


# ==============================================================================
# INCLUDE ROUTERS
# ==============================================================================
# Routers are included with prefixes to organize API versions

# API v1 routes (all endpoints under /api/v1)
app.include_router(
    api_v1_router,
    prefix=settings.API_V1_PREFIX
)

# Future versions:
# app.include_router(api_v2_router, prefix="/api/v2")


# ==============================================================================
# ROOT ENDPOINTS
# ==============================================================================
# Health check and root endpoints (not versioned)

@app.get("/", tags=["Root"])
def root():
    """
    Root endpoint - API welcome message.
    
    Returns basic API information and links to documentation.
    """
    return {
        "message": f"Welcome to {settings.API_TITLE}",
        "version": settings.API_VERSION,
        "docs": "/docs",
        "redoc": "/redoc",
        "health": "/health"
    }


@app.get("/health", tags=["Health"])
def health_check():
    """
    Health check endpoint.
    
    Use this for:
    - Load balancer health checks
    - Kubernetes liveness/readiness probes
    - Monitoring systems
    
    Returns service health status.
    """
    return {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
        "version": settings.API_VERSION
    }


@app.get("/health/db", tags=["Health"])
def health_check_database():
    """
    Database health check.
    
    Verifies database connectivity by executing a simple query.
    """
    try:
        from sqlmodel import Session, text
        from app.core.database import engine
        
        with Session(engine) as session:
            session.exec(text("SELECT 1"))
        
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {"status": "unhealthy", "database": "disconnected", "error": str(e)}


# ==============================================================================
# ERROR HANDLERS (Optional - customize as needed)
# ==============================================================================

# from fastapi import Request
# from fastapi.responses import JSONResponse
#
# @app.exception_handler(Exception)
# async def global_exception_handler(request: Request, exc: Exception):
#     """Handle uncaught exceptions."""
#     logger.error(f"Unhandled exception: {exc}", exc_info=True)
#     return JSONResponse(
#         status_code=500,
#         content={"detail": "Internal server error"}
#     )


# ==============================================================================
# HOW TO EXTEND THIS APPLICATION:
# ==============================================================================
#
# ADDING NEW API ROUTES:
# 1. Create a new file in app/api/v1/endpoints/ (e.g., users.py)
# 2. Define router: router = APIRouter()
# 3. Add endpoints with @router.get(), .post(), etc.
# 4. Include in app/api/v1/__init__.py:
#    from app.api.v1.endpoints import users
#    api_v1_router.include_router(users.router, prefix="/users", tags=["Users"])
#
# ADDING MIDDLEWARE:
# - Import the middleware class
# - Call app.add_middleware(MiddlewareClass, **options)
#
# ADDING BACKGROUND TASKS:
# - Use FastAPI's BackgroundTasks dependency
# - Or integrate Celery for complex task queues
#
# ADDING WEBSOCKETS:
# @app.websocket("/ws")
# async def websocket_endpoint(websocket: WebSocket):
#     await websocket.accept()
#     ...
#
# ADDING SCHEDULED TASKS:
# - Integrate APScheduler or similar
# - Or use external cron jobs calling API endpoints
# ==============================================================================




