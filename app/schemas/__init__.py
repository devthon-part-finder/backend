# ==============================================================================
# Schemas Package
# ==============================================================================
# This package contains Pydantic models for request/response validation.
# These are separate from SQLModel database models to allow flexibility.
#
# Naming Convention:
#   - {Model}Create: For POST requests (creating new records)
#   - {Model}Read: For GET responses (returning data)
#   - {Model}Update: For PUT/PATCH requests (updating records)
#   - {Model}Base: Shared fields between Create/Read/Update
#
# Example:
#   class ItemBase(BaseModel):
#       name: str
#       description: str | None = None
#
#   class ItemCreate(ItemBase):
#       pass  # Same as base for creation
#
#   class ItemRead(ItemBase):
#       id: int  # Include ID in responses
# ==============================================================================
