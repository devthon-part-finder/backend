# ==============================================================================
# Web Agent Schemas - Request/Response Validation
# ==============================================================================
# This module defines Pydantic models for the Web Agent Service.
#
# The Web Agent ("The Shopper") is responsible for:
#   1. Searching the web for parts/products
#   2. Extracting structured pricing data
#   3. Returning standardized vendor results
#
# SCHEMA OVERVIEW:
#   - VendorResult: Single vendor/product result with price, availability, etc.
#   - PartSearchRequest: Input for searching parts by name/number
#   - PartSearchResponse: Paginated response with list of VendorResults
# ==============================================================================

from pydantic import BaseModel, Field, ConfigDict, HttpUrl
from typing import Optional
from enum import Enum


class SourceType(str, Enum):
    """Source of the vendor result data."""
    SERPER_SNIPPET = "serper_snippet"  # Fast path: data extracted from Serper JSON
    PAGE_SCRAPE = "page_scrape"        # Slow path: data scraped and AI-parsed


class Availability(str, Enum):
    """Product availability status."""
    IN_STOCK = "In Stock"
    OUT_OF_STOCK = "Out of Stock"
    LIMITED_STOCK = "Limited Stock"
    PRE_ORDER = "Pre-Order"
    UNKNOWN = "Unknown"


class VendorResult(BaseModel):
    """
    Single vendor/product result from web search.
    
    This is the standardized output format that the UI can rely on,
    regardless of whether data came from Serper snippets or page scraping.
    """
    model_config = ConfigDict(from_attributes=True)
    
    vendor_name: str = Field(
        ...,
        description="Name of the vendor/seller",
        json_schema_extra={"example": "SKF Official Store"}
    )
    
    product_title: str = Field(
        ...,
        description="Title/name of the product",
        json_schema_extra={"example": "SKF 6205-2RS Deep Groove Ball Bearing"}
    )
    
    price: Optional[float] = Field(
        default=None,
        description="Price of the product (None if not available)",
        json_schema_extra={"example": 1250.00}
    )
    
    currency: str = Field(
        default="LKR",
        description="Currency code for the price",
        json_schema_extra={"example": "LKR"}
    )
    
    availability: str = Field(
        default=Availability.UNKNOWN.value,
        description="Product availability status",
        json_schema_extra={"example": "In Stock"}
    )
    
    product_url: str = Field(
        ...,
        description="Direct URL to the product page",
        json_schema_extra={"example": "https://example.com/product/skf-6205"}
    )
    
    source_type: str = Field(
        default=SourceType.SERPER_SNIPPET.value,
        description="How this result was obtained: 'serper_snippet' (fast) or 'page_scrape' (AI-parsed)",
        json_schema_extra={"example": "serper_snippet"}
    )
    
    confidence_score: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Confidence score of the result (0.0 - 1.0)",
        json_schema_extra={"example": 0.85}
    )
    
    image_url: Optional[str] = Field(
        default=None,
        description="URL to product image (if available)",
        json_schema_extra={"example": "https://example.com/images/skf-6205.jpg"}
    )
    
    description: Optional[str] = Field(
        default=None,
        description="Short description or snippet about the product",
        json_schema_extra={"example": "High-quality sealed ball bearing for industrial applications"}
    )


class PartSearchRequest(BaseModel):
    """
    Request schema for searching parts.
    
    Used by:
    - Catalog Search (after identifying a part from PDF)
    - Camera Search (after identifying a part from image)
    - Text Search (direct user query)
    """
    part_name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Name or description of the part to search for",
        json_schema_extra={"example": "SKF 6205-2RS bearing"}
    )
    
    part_number: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Specific part number if known",
        json_schema_extra={"example": "6205-2RS"}
    )
    
    manufacturer: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Manufacturer name if known",
        json_schema_extra={"example": "SKF"}
    )
    
    location: str = Field(
        default="Sri Lanka",
        description="Target location for search (affects pricing and availability)",
        json_schema_extra={"example": "Sri Lanka"}
    )
    
    max_results: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of results to return",
        json_schema_extra={"example": 10}
    )
    
    include_scraping: bool = Field(
        default=True,
        description="Whether to use AI scraping for results without direct pricing (slower but more accurate)",
        json_schema_extra={"example": True}
    )


class PartSearchResponse(BaseModel):
    """
    Response schema for part search results.
    
    Contains a list of vendor results along with metadata about the search.
    """
    model_config = ConfigDict(from_attributes=True)
    
    results: list[VendorResult] = Field(
        default_factory=list,
        description="List of vendor results"
    )
    
    search_query: str = Field(
        ...,
        description="The actual query string used for searching",
        json_schema_extra={"example": "buy SKF 6205-2RS bearing Sri Lanka"}
    )
    
    total_results: int = Field(
        default=0,
        ge=0,
        description="Total number of results found"
    )
    
    fast_path_count: int = Field(
        default=0,
        ge=0,
        description="Number of results from Serper snippets (fast path)"
    )
    
    slow_path_count: int = Field(
        default=0,
        ge=0,
        description="Number of results from AI scraping (slow path)"
    )
    
    search_time_ms: Optional[int] = Field(
        default=None,
        description="Total search time in milliseconds"
    )
