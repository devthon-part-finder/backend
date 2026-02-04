# ==============================================================================
# Controllers Package
# ==============================================================================
# Controllers orchestrate the request/response flow between routes and services.
# They handle:
#   - Request validation (via Pydantic schemas)
#   - Calling appropriate service methods
#   - Error handling and response formatting
#   - Coordinating multiple service calls when needed
#
# Controller Pattern:
#   1. Receive validated request data from route
#   2. Call one or more service methods
#   3. Format and return response
#
# Keep controllers thin - complex business logic belongs in services.
# ==============================================================================
