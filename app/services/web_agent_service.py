# ==============================================================================
# Web Agent Service - "The Shopper"
# ==============================================================================
# This service is responsible for finding where to buy industrial parts.
# It's a shared service used by:
#   - Catalog Search (after identifying parts from PDF)
#   - Camera Search (after identifying parts from images)
#   - Text Search (direct user queries)
#
# ARCHITECTURE:
# The service uses a dual-path strategy for efficiency:
#
# 1. FAST PATH (Serper Snippets):
#    - Query Serper.dev API for Google search results
#    - Extract price/stock directly from JSON if available (Google Shopping data)
#    - Returns results in ~500ms
#
# 2. SLOW PATH (AI Scraping):
#    - For results without direct pricing data
#    - Fetch page HTML with httpx
#    - Use Gemini Flash to parse and extract structured data
#    - Returns results in ~2-5 seconds per page
#
# USAGE:
#   from app.services.web_agent_service import web_agent_service
#   results = await web_agent_service.find_parts("SKF 6205-2RS bearing")
# ==============================================================================

import httpx
import logging
import time
import json
import re
from typing import Optional

from google import genai
from google.genai import types

from app.core.config import settings
from app.schemas.web_agent import (
    VendorResult,
    PartSearchRequest,
    PartSearchResponse,
    SourceType,
    Availability,
)

logger = logging.getLogger(__name__)


class WebAgentService:
    """
    Web Agent Service for finding parts online.
    
    Implements a dual-path search strategy:
    - Fast Path: Extract data from Serper JSON (Google Shopping)
    - Slow Path: Scrape and AI-parse product pages
    """
    
    SERPER_API_URL = "https://google.serper.dev/search"
    SERPER_SHOPPING_URL = "https://google.serper.dev/shopping"
    
    # User agent for web scraping
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    
    # Gemini prompt for extracting product data from HTML
    EXTRACTION_PROMPT = """You are a product data extraction expert. Analyze the following HTML content and extract product information.

Return a JSON object with these fields (use null if not found):
- vendor_name: The seller/store name
- product_title: The product title/name
- price: The price as a number (without currency symbol)
- currency: The currency code (e.g., "LKR", "USD", "EUR")
- availability: One of "In Stock", "Out of Stock", "Limited Stock", "Pre-Order", or "Unknown"
- description: A brief product description (max 200 chars)

IMPORTANT:
- Extract ONLY factual data from the page
- If price is shown as a range, use the lowest price
- If multiple currencies shown, prefer LKR or USD
- Return ONLY valid JSON, no markdown or explanations

HTML Content:
{html_content}

JSON Response:"""
    
    def __init__(self):
        """Initialize the Web Agent Service."""
        self._validate_config()
        self._init_gemini()
    
    def _validate_config(self):
        """Validate that required API keys are configured."""
        if not settings.SERPER_API_KEY:
            logger.warning("SERPER_API_KEY not configured - web search will fail")
        if not settings.GEMINI_API_KEY:
            logger.warning("GEMINI_API_KEY not configured - AI scraping will fail")
    
    def _init_gemini(self):
        """Initialize Gemini client using google-genai SDK."""
        if settings.GEMINI_API_KEY:
            self.gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)
            self.gemini_model_name = "gemini-2.0-flash"
            logger.info("Gemini client initialized with google-genai SDK")
        else:
            self.gemini_client = None
            self.gemini_model_name = None
    
    async def _search_serper(
        self,
        query: str,
        location: str = "Sri Lanka",
        num_results: int = 10,
        search_type: str = "search"
    ) -> list[dict]:
        """
        Fast Path: Search using Serper.dev API.
        
        Args:
            query: Search query string
            location: Target location for localized results
            num_results: Maximum number of results
            search_type: "search" for organic or "shopping" for Google Shopping
        
        Returns:
            List of raw search result dictionaries
        """
        if not settings.SERPER_API_KEY:
            raise ValueError("SERPER_API_KEY not configured")
        
        url = self.SERPER_SHOPPING_URL if search_type == "shopping" else self.SERPER_API_URL
        
        # Map location to Google country code
        gl_map = {
            "Sri Lanka": "lk",
            "India": "in",
            "USA": "us",
            "UK": "gb",
        }
        gl = gl_map.get(location, "lk")
        
        payload = {
            "q": query,
            "location": location,
            "gl": gl,
            "num": num_results,
        }
        
        headers = {
            "X-API-KEY": settings.SERPER_API_KEY,
            "Content-Type": "application/json",
        }
        
        logger.info(f"Serper {search_type} search: {query}")
        
        async with httpx.AsyncClient(timeout=settings.WEB_AGENT_TIMEOUT) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
        
        # Extract results based on search type
        if search_type == "shopping":
            results = data.get("shopping", [])
        else:
            # Combine organic and shopping results if available
            results = data.get("organic", [])
            shopping = data.get("shopping", [])
            if shopping:
                results.extend(shopping)
        
        logger.info(f"Serper returned {len(results)} results")
        return results
    
    async def _scrape_and_parse(self, url: str) -> Optional[dict]:
        """
        Slow Path: Scrape page and use Gemini to extract product data.
        
        Args:
            url: URL of the product page to scrape
        
        Returns:
            Dictionary with extracted product data, or None if failed
        """
        if not self.gemini_client:
            logger.warning("Gemini not configured - skipping scrape")
            return None
        
        try:
            # Fetch page HTML
            headers = {"User-Agent": self.USER_AGENT}
            async with httpx.AsyncClient(
                timeout=settings.WEB_AGENT_TIMEOUT,
                follow_redirects=True
            ) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                html = response.text
            
            # Limit HTML size to avoid token overflow
            max_bytes = settings.WEB_AGENT_MAX_SCRAPE_BYTES
            if len(html) > max_bytes:
                # Try to keep the body content
                body_match = re.search(r'<body[^>]*>(.*?)</body>', html, re.DOTALL | re.IGNORECASE)
                if body_match:
                    html = body_match.group(1)[:max_bytes]
                else:
                    html = html[:max_bytes]
            
            # Clean HTML - remove scripts and styles
            html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
            html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
            html = re.sub(r'<!--.*?-->', '', html, flags=re.DOTALL)
            
            # Use Gemini to extract product data (using google-genai SDK)
            prompt = self.EXTRACTION_PROMPT.format(html_content=html[:max_bytes])
            
            response = await self.gemini_client.aio.models.generate_content(
                model=self.gemini_model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.1,  # Low temperature for factual extraction
                    max_output_tokens=500,
                )
            )
            response_text = response.text.strip()
            
            # Parse JSON response
            # Handle markdown code blocks if present
            if response_text.startswith("```"):
                response_text = re.sub(r'^```json?\n?', '', response_text)
                response_text = re.sub(r'\n?```$', '', response_text)
            
            extracted = json.loads(response_text)
            logger.info(f"Extracted data from {url}: {extracted.get('product_title', 'N/A')}")
            return extracted
            
        except httpx.HTTPError as e:
            logger.error(f"HTTP error scraping {url}: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error for {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            return None
    
    def _parse_serper_result(self, result: dict, source_type: str = SourceType.SERPER_SNIPPET.value) -> VendorResult:
        """
        Parse a Serper result into a VendorResult.
        
        Args:
            result: Raw result dictionary from Serper
            source_type: Source type for the result
        
        Returns:
            VendorResult object
        """
        # Try to extract price from various Serper fields
        price = None
        currency = "LKR"
        
        # Shopping results have direct price
        if "price" in result:
            price_str = str(result["price"])
            # Extract numeric price
            price_match = re.search(r'[\d,]+\.?\d*', price_str.replace(',', ''))
            if price_match:
                price = float(price_match.group())
            # Try to detect currency
            if "USD" in price_str or "$" in price_str:
                currency = "USD"
            elif "LKR" in price_str or "Rs" in price_str:
                currency = "LKR"
            elif "EUR" in price_str or "€" in price_str:
                currency = "EUR"
        
        # Extract vendor name
        vendor_name = result.get("source", result.get("site", "Unknown"))
        if not vendor_name or vendor_name == "Unknown":
            # Try to extract from URL
            link = result.get("link", "")
            if link:
                domain_match = re.search(r'https?://(?:www\.)?([^/]+)', link)
                if domain_match:
                    vendor_name = domain_match.group(1)
        
        # Determine confidence based on data quality
        confidence = 0.5
        if price is not None:
            confidence += 0.3
        if result.get("rating"):
            confidence += 0.1
        if result.get("reviews"):
            confidence += 0.1
        
        return VendorResult(
            vendor_name=vendor_name,
            product_title=result.get("title", "Unknown Product"),
            price=price,
            currency=currency,
            availability=Availability.UNKNOWN.value,
            product_url=result.get("link", ""),
            source_type=source_type,
            confidence_score=min(confidence, 1.0),
            image_url=result.get("imageUrl"),
            description=result.get("snippet", result.get("description"))
        )
    
    async def find_parts(self, request: PartSearchRequest) -> PartSearchResponse:
        """
        Main orchestration method: Find parts using dual-path strategy.
        
        Args:
            request: PartSearchRequest with search parameters
        
        Returns:
            PartSearchResponse with list of VendorResults
        """
        start_time = time.time()
        results: list[VendorResult] = []
        fast_path_count = 0
        slow_path_count = 0
        
        # Build search query
        query_parts = ["buy", request.part_name]
        if request.part_number:
            query_parts.append(request.part_number)
        if request.manufacturer:
            query_parts.append(request.manufacturer)
        query_parts.append(request.location)
        
        search_query = " ".join(query_parts)
        logger.info(f"Search query: {search_query}")
        
        try:
            # Step 1: Try Shopping search first (best for products with prices)
            shopping_results = await self._search_serper(
                query=search_query,
                location=request.location,
                num_results=request.max_results,
                search_type="shopping"
            )
            
            # Process shopping results (Fast Path)
            for raw_result in shopping_results[:request.max_results]:
                vendor_result = self._parse_serper_result(raw_result, SourceType.SERPER_SNIPPET.value)
                results.append(vendor_result)
                fast_path_count += 1
            
            # Step 2: If not enough results, also do organic search
            if len(results) < request.max_results:
                organic_results = await self._search_serper(
                    query=search_query,
                    location=request.location,
                    num_results=request.max_results - len(results),
                    search_type="search"
                )
                
                for raw_result in organic_results:
                    if len(results) >= request.max_results:
                        break
                    
                    vendor_result = self._parse_serper_result(raw_result, SourceType.SERPER_SNIPPET.value)
                    
                    # Step 3: Slow Path - If no price and scraping enabled, try AI extraction
                    if vendor_result.price is None and request.include_scraping and vendor_result.product_url:
                        scraped_data = await self._scrape_and_parse(vendor_result.product_url)
                        if scraped_data:
                            # Update result with scraped data
                            if scraped_data.get("price"):
                                vendor_result.price = float(scraped_data["price"])
                            if scraped_data.get("currency"):
                                vendor_result.currency = scraped_data["currency"]
                            if scraped_data.get("availability"):
                                vendor_result.availability = scraped_data["availability"]
                            if scraped_data.get("vendor_name"):
                                vendor_result.vendor_name = scraped_data["vendor_name"]
                            if scraped_data.get("product_title"):
                                vendor_result.product_title = scraped_data["product_title"]
                            if scraped_data.get("description"):
                                vendor_result.description = scraped_data["description"]
                            vendor_result.source_type = SourceType.PAGE_SCRAPE.value
                            vendor_result.confidence_score = min(vendor_result.confidence_score + 0.2, 1.0)
                            slow_path_count += 1
                    
                    results.append(vendor_result)
            
        except Exception as e:
            logger.error(f"Error in find_parts: {e}")
            raise
        
        # Calculate search time
        search_time_ms = int((time.time() - start_time) * 1000)
        
        # Sort by confidence score (highest first)
        results.sort(key=lambda x: x.confidence_score, reverse=True)
        
        return PartSearchResponse(
            results=results,
            search_query=search_query,
            total_results=len(results),
            fast_path_count=fast_path_count,
            slow_path_count=slow_path_count,
            search_time_ms=search_time_ms
        )


# Create a singleton instance
web_agent_service = WebAgentService()
