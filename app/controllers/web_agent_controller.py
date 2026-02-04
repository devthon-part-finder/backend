# ==============================================================================
# Web Agent Controller - Request/Response Orchestration
# ==============================================================================
# This controller handles HTTP concerns for the Web Agent Service:
#   - Validates inputs
#   - Calls service layer
#   - Handles exceptions and converts to HTTPException
#   - Formats responses
#
# Following the layered architecture pattern:
#   Endpoint -> Controller -> Service -> External APIs (Serper, Gemini)
# ==============================================================================

from fastapi import HTTPException, status
import logging

from app.services.web_agent_service import web_agent_service
from app.schemas.web_agent import PartSearchRequest, PartSearchResponse

logger = logging.getLogger(__name__)


async def search_parts_controller(request: PartSearchRequest) -> PartSearchResponse:
    """
    Controller for part search endpoint.
    
    Orchestrates the search process:
    1. Validates the request
    2. Calls the web agent service
    3. Handles errors and returns appropriate HTTP responses
    
    Args:
        request: PartSearchRequest with search parameters
    
    Returns:
        PartSearchResponse with search results
    
    Raises:
        HTTPException: On validation errors or service failures
    """
    logger.info(f"Search request: part_name='{request.part_name}', location='{request.location}'")
    
    try:
        # Call the web agent service
        response = await web_agent_service.find_parts(request)
        
        logger.info(
            f"Search completed: {response.total_results} results "
            f"(fast: {response.fast_path_count}, slow: {response.slow_path_count}) "
            f"in {response.search_time_ms}ms"
        )
        
        return response
        
    except ValueError as e:
        # Configuration errors (missing API keys, etc.)
        logger.error(f"Configuration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service configuration error: {str(e)}"
        )
        
    except Exception as e:
        # Unexpected errors
        logger.exception(f"Unexpected error in search_parts_controller: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while searching for parts. Please try again later."
        )


async def quick_search_controller(part_name: str, location: str = "Sri Lanka") -> PartSearchResponse:
    """
    Simplified controller for quick searches.
    
    Useful for simple queries without full request configuration.
    
    Args:
        part_name: Name of the part to search for
        location: Target location (default: Sri Lanka)
    
    Returns:
        PartSearchResponse with search results
    """
    request = PartSearchRequest(
        part_name=part_name,
        location=location,
        max_results=5,
        include_scraping=False  # Fast path only for quick searches
    )
    
    return await search_parts_controller(request)
