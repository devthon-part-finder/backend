# ==============================================================================
# API v1 Package
# ==============================================================================
# This module aggregates all v1 endpoint routers into a single router.
# Include this router in main.py to mount all v1 endpoints under /api/v1
# ==============================================================================

from fastapi import APIRouter
from app.api.v1.endpoints import users

# Create the main v1 router that will include all endpoint routers
api_v1_router = APIRouter()

# Include endpoint routers here
# Pattern: api_v1_router.include_router(module.router, prefix="/resource", tags=["Resource"])
api_v1_router.include_router(users.router, prefix="/users", tags=["Users"])

# ==============================================================================
# HOW TO ADD NEW ENDPOINTS:
# ==============================================================================
# 1. Create a new file in app/api/v1/endpoints/ (e.g., products.py)
# 2. Define a router in that file: router = APIRouter()
# 3. Import and include it here:
#    from app.api.v1.endpoints import products
#    api_v1_router.include_router(products.router, prefix="/products", tags=["Products"])
# ==============================================================================
