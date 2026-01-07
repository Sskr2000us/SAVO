"""
OpenFoodFacts API Integration
Provides barcode lookup, product information extraction, and nutrition data
"""
import httpx
import logging
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class OpenFoodFactsClient:
    """Client for OpenFoodFacts API - https://world.openfoodfacts.org/"""
    
    BASE_URL = "https://world.openfoodfacts.org/api/v2"
    USER_AGENT = "SAVO-App/1.0 (Ingredient Management)"
    
    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=10.0,
            headers={"User-Agent": self.USER_AGENT}
        )
    
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()
    
    async def lookup_barcode(self, barcode: str) -> Optional[Dict[str, Any]]:
        """
        Look up product by barcode (EAN-13, UPC-A, etc.)
        
        Args:
            barcode: The barcode number (without spaces or dashes)
        
        Returns:
            Product information or None if not found
        """
        try:
            url = f"{self.BASE_URL}/product/{barcode}.json"
            response = await self.client.get(url)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == 1:  # Product found
                    return self._parse_product(data.get("product", {}))
                else:
                    logger.info(f"Barcode {barcode} not found in OpenFoodFacts")
                    return None
            else:
                logger.error(f"OpenFoodFacts API error: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error looking up barcode {barcode}: {str(e)}")
            return None
    
    def _parse_product(self, product: Dict[str, Any]) -> Dict[str, Any]:
        """Parse OpenFoodFacts product data into our format"""
        
        # Extract quantity and unit
        quantity_value, quantity_unit = self._parse_quantity(
            product.get("quantity", ""),
            product.get("product_quantity", 0)
        )
        
        # Get ingredient name (prioritize generic name over brand name)
        product_name = product.get("generic_name") or product.get("product_name") or "Unknown"
        
        # Extract country
        country_code = self._extract_country_code(product.get("countries_tags", []))
        
        return {
            "barcode": product.get("code"),
            "product_name": product_name,
            "brand": product.get("brands", "").split(",")[0].strip() if product.get("brands") else None,
            "manufacturer": product.get("manufacturing_places"),
            "quantity_value": quantity_value,
            "quantity_unit": quantity_unit,
            "country_code": country_code,
            "image_url": product.get("image_url"),
            "ingredients_text": product.get("ingredients_text"),
            "categories": product.get("categories", "").split(","),
            "nutrition_facts": self._parse_nutrition(product.get("nutriments", {})),
            "allergens": product.get("allergens_tags", []),
            "labels": product.get("labels_tags", []),
            "packaging": product.get("packaging", ""),
            "external_id": product.get("_id"),
            "data_source": "openfoodfacts",
            "last_modified": product.get("last_modified_t"),
        }
    
    def _parse_quantity(self, quantity_str: str, quantity_num: float) -> tuple[Optional[float], Optional[str]]:
        """
        Parse quantity from string or number
        Examples: "500g", "1L", "2 kg", "16 oz"
        """
        import re
        
        if quantity_num and quantity_num > 0:
            # Try to extract unit from string
            unit_match = re.search(r'(g|kg|ml|l|oz|lb|fl oz)', quantity_str.lower())
            unit = unit_match.group(1) if unit_match else "g"
            return float(quantity_num), unit
        
        if quantity_str:
            # Parse from string like "500 g"
            match = re.search(r'(\d+\.?\d*)\s*(g|kg|ml|l|oz|lb|fl oz)', quantity_str.lower())
            if match:
                value = float(match.group(1))
                unit = match.group(2)
                
                # Normalize units
                if unit == "kg":
                    value *= 1000
                    unit = "g"
                elif unit == "l":
                    value *= 1000
                    unit = "ml"
                
                return value, unit
        
        return None, None
    
    def _extract_country_code(self, countries_tags: list) -> Optional[str]:
        """Extract ISO country code from OpenFoodFacts tags"""
        if not countries_tags:
            return None
        
        # Tags are like "en:india", "en:united-states"
        for tag in countries_tags:
            if ":" in tag:
                country = tag.split(":")[1]
                
                # Map common names to ISO codes
                country_map = {
                    "india": "IN",
                    "united-states": "US",
                    "united-kingdom": "GB",
                    "france": "FR",
                    "germany": "DE",
                    "spain": "ES",
                    "italy": "IT",
                    "china": "CN",
                    "japan": "JP",
                }
                
                return country_map.get(country, country[:2].upper())
        
        return None
    
    def _parse_nutrition(self, nutriments: Dict[str, Any]) -> Dict[str, Any]:
        """Parse nutrition facts per 100g"""
        return {
            "energy_kcal": nutriments.get("energy-kcal_100g"),
            "protein_g": nutriments.get("proteins_100g"),
            "carbs_g": nutriments.get("carbohydrates_100g"),
            "fat_g": nutriments.get("fat_100g"),
            "fiber_g": nutriments.get("fiber_100g"),
            "sugar_g": nutriments.get("sugars_100g"),
            "sodium_mg": nutriments.get("sodium_100g"),
            "salt_g": nutriments.get("salt_100g"),
        }
    
    async def search_products(
        self, 
        query: str, 
        country: Optional[str] = None,
        limit: int = 20
    ) -> list[Dict[str, Any]]:
        """
        Search products by name
        
        Args:
            query: Search term
            country: ISO country code to filter by
            limit: Maximum results to return
        """
        try:
            url = f"{self.BASE_URL}/search"
            params = {
                "search_terms": query,
                "page_size": limit,
                "json": 1,
            }
            
            if country:
                params["countries"] = country
            
            response = await self.client.get(url, params=params)
            
            if response.status_code == 200:
                data = response.json()
                products = data.get("products", [])
                return [self._parse_product(p) for p in products]
            else:
                logger.error(f"OpenFoodFacts search error: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Error searching products: {str(e)}")
            return []


# Global client instance
_client: Optional[OpenFoodFactsClient] = None

def get_openfoodfacts_client() -> OpenFoodFactsClient:
    """Get or create the global OpenFoodFacts client"""
    global _client
    if _client is None:
        _client = OpenFoodFactsClient()
    return _client

async def close_openfoodfacts_client():
    """Close the global client"""
    global _client
    if _client:
        await _client.close()
        _client = None
