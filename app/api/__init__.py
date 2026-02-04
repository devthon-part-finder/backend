# ==============================================================================
# API Package
# ==============================================================================
# This package contains all API versioning and endpoint definitions.
# 
# Structure:
#   - v1/: Version 1 of the API
#     - endpoints/: Individual endpoint modules (items.py, users.py, etc.)
#
# To add a new API version:
#   1. Create a new folder (e.g., v2/)
#   2. Add __init__.py with router aggregation
#   3. Include the new version router in main.py
# ==============================================================================
