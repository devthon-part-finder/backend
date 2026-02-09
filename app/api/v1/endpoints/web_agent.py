# ==============================================================================
# Web Agent API Endpoints
# ==============================================================================
# This module defines the API endpoints for the Web Agent Service ("The Shopper").
#
# Endpoints:
#   POST /search     - Full search with all options
#   GET  /quick      - Quick search with minimal params
#
# The Web Agent is used by:
#   - Catalog Search (after identifying parts from PDF)
#   - Camera Search (after identifying parts from images)
#   - Text Search (direct user queries)
#
# All endpoints are async for optimal performance with external API calls.
# ==============================================================================

from fastapi import APIRouter, Query, status

from app.schemas.web_agent import PartSearchRequest, PartSearchResponse
from app.controllers import web_agent_controller

router = APIRouter()


@router.post(
    "/search",
    response_model=PartSearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Search for parts online",
    description="""
Search for industrial parts across online vendors.

**Strategy:**
- **Fast Path**: Extracts pricing directly from Google Shopping results (Serper API)
- **Slow Path**: Scrapes product pages and uses AI (Gemini) to extract structured data

**Use Cases:**
- Finding replacement parts after PDF catalog analysis
- Locating parts identified by camera/image search
- Direct text-based part searches

**Response Fields:**
- `results`: List of vendor results with prices and availability
- `fast_path_count`: Results from direct API extraction (faster, ~500ms)
- `slow_path_count`: Results from AI page scraping (slower, ~2-5s each)
- `search_time_ms`: Total search duration in milliseconds
""",
    responses={
        200: {
            "description": "Search completed successfully",
            "content": {
                "application/json": {
                    "example": {
                        "results": [
                            {
                                "vendor_name": "SKF Official Store",
                                "product_title": "SKF 6205-2RS Deep Groove Ball Bearing",
                                "price": 1250.0,
                                "currency": "LKR",
                                "availability": "In Stock",
                                "product_url": "https://example.com/skf-6205",
                                "source_type": "serper_snippet",
                                "confidence_score": 0.85
                            }
                        ],
                        "search_query": "buy SKF 6205-2RS bearing Sri Lanka",
                        "total_results": 1,
                        "fast_path_count": 1,
                        "slow_path_count": 0,
                        "search_time_ms": 523
                    }
                }
            }
        },
        503: {"description": "Service configuration error (missing API keys)"},
        500: {"description": "Internal server error"}
    }
)
async def search_parts(request: PartSearchRequest) -> PartSearchResponse:
    """
    Search for parts online using dual-path strategy.
    
    The search combines fast API extraction with optional AI-powered
    page scraping for comprehensive results.
    """
    return await web_agent_controller.search_parts_controller(request)


@router.get(
    "/quick",
    response_model=PartSearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Quick part search",
    description="""
Simplified search endpoint for quick queries.

Uses only the **Fast Path** (no AI scraping) for faster response times.
Returns up to 5 results.

Ideal for:
- Autocomplete suggestions
- Quick availability checks
- Preview searches before full search
"""
)
async def quick_search(
    part_name: str = Query(
        ...,
        min_length=1,
        max_length=200,
        description="Name or description of the part to search",
        examples=["SKF 6205-2RS bearing"]
    ),
    location: str = Query(
        default="Sri Lanka",
        description="Target location for search",
        examples=["Sri Lanka"]
    )
) -> PartSearchResponse:
    """
    Quick search for parts (fast path only).
    
    Uses simplified parameters and skips AI scraping for speed.
    """
    return await web_agent_controller.quick_search_controller(part_name, location)
