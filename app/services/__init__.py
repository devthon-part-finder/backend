# ==============================================================================
# Services Package
# ==============================================================================
# Services contain the core business logic of the application.
# They handle:
#   - Database operations (CRUD)
#   - External API integrations
#   - ML model inference calls
#   - Complex data transformations
#   - Vector embedding generation and similarity search
#
# Service Pattern:
#   - Each service focuses on a single domain (items, users, search, etc.)
#   - Services receive a database session as a parameter
#   - Services are stateless - no instance variables
#   - Return domain objects or raise exceptions
#
# Keep services decoupled from HTTP concerns (no Request/Response objects).
# ==============================================================================
