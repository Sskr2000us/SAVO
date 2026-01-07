"""
Test Advanced Scanning Features
Quick validation script for barcode and container scanning
"""
import asyncio
import httpx
import os
from pathlib import Path

# Configuration
API_BASE_URL = os.getenv("API_URL", "https://your-api.onrender.com")
AUTH_TOKEN = os.getenv("AUTH_TOKEN", "")

async def test_barcode_scanning():
    """Test barcode scanning endpoint"""
    print("\n=== Testing Barcode Scanning ===")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Test with a common Indian product barcode
        response = await client.post(
            f"{API_BASE_URL}/api/scanning/barcode",
            json={
                "barcode": "8901234567890",  # Example barcode
                "add_to_inventory": True,
                "storage_location": "pantry"
            },
            headers={"Authorization": f"Bearer {AUTH_TOKEN}"}
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Barcode scan successful")
            print(f"  Product: {data['product_name']}")
            print(f"  Brand: {data.get('brand', 'N/A')}")
            print(f"  Quantity: {data.get('quantity_value')} {data.get('quantity_unit')}")
            print(f"  Ingredient: {data.get('ingredient_canonical_name', 'Not matched')}")
            print(f"  Confidence: {data['confidence']}")
            print(f"  Added to inventory: {data['added_to_inventory']}")
            return True
        elif response.status_code == 404:
            print("⚠ Barcode not found in OpenFoodFacts database")
            return False
        else:
            print(f"✗ Error: {response.status_code} - {response.text}")
            return False


async def test_multi_language_search():
    """Test multi-language ingredient search"""
    print("\n=== Testing Multi-Language Search ===")
    
    test_queries = [
        ("rice", "en", "English - Rice"),
        ("चावल", "hi", "Hindi - Rice"),
        ("அரிசி", "ta", "Tamil - Rice"),
        ("दाल", "hi", "Hindi - Lentils"),
    ]
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        for query, lang, description in test_queries:
            response = await client.get(
                f"{API_BASE_URL}/api/scanning/ingredients/search-global",
                params={"query": query, "lang": lang, "limit": 5},
                headers={"Authorization": f"Bearer {AUTH_TOKEN}"}
            )
            
            if response.status_code == 200:
                results = response.json()
                print(f"✓ {description}: {len(results)} results")
                if results:
                    print(f"  Top result: {results[0]['canonical_name']} ({results[0]['matched_name']})")
            else:
                print(f"✗ {description}: Error {response.status_code}")


async def test_database_functions():
    """Test database functions directly"""
    print("\n=== Testing Database Functions ===")
    
    from app.core.database import get_db_client
    
    db = await get_db_client().__anext__()
    
    try:
        # Test search function
        results = await db.fetch(
            "SELECT * FROM search_ingredients_multilang($1, $2, $3)",
            "rice", "en", 5
        )
        print(f"✓ search_ingredients_multilang: {len(results)} results")
        
        # Test volume to weight conversion
        result = await db.fetchrow(
            "SELECT * FROM estimate_quantity_from_volume($1, $2, $3)",
            "rice", 500, "raw"
        )
        if result:
            print(f"✓ estimate_quantity_from_volume:")
            print(f"  500ml rice = {result['estimated_weight_g']}g (confidence: {result['confidence']})")
        
        print("✓ Database functions working correctly")
        
    except Exception as e:
        print(f"✗ Database error: {e}")


async def test_quantity_estimator():
    """Test quantity estimation model"""
    print("\n=== Testing Quantity Estimator ===")
    
    from app.core.quantity_estimator import (
        QuantityEstimator, BoundingBox, ReferenceObject
    )
    
    estimator = QuantityEstimator()
    
    # Test without reference objects
    ingredient_bbox = BoundingBox(
        x_min=100, y_min=50, x_max=300, y_max=400,
        image_width=800, image_height=600
    )
    
    estimate = estimator.estimate_from_bbox_and_reference(
        ingredient_bbox,
        reference_objects=[],
        container_type="glass_jar",
        fill_percentage=75
    )
    
    print(f"✓ Basic estimation (no reference):")
    print(f"  Quantity: {estimate.estimated_value} {estimate.unit}")
    print(f"  Confidence: {estimate.confidence}")
    print(f"  Method: {estimate.method}")
    
    # Test with reference object (hand)
    hand_bbox = BoundingBox(
        x_min=400, y_min=200, x_max=500, y_max=500,
        image_width=800, image_height=600
    )
    reference = ReferenceObject(
        object_type="hand",
        bbox=hand_bbox,
        avg_real_size_cm=18.0,
        confidence=0.85
    )
    
    estimate_with_ref = estimator.estimate_from_bbox_and_reference(
        ingredient_bbox,
        reference_objects=[reference],
        container_type="glass_jar",
        fill_percentage=75
    )
    
    print(f"✓ Estimation with reference object:")
    print(f"  Quantity: {estimate_with_ref.estimated_value} {estimate_with_ref.unit}")
    print(f"  Confidence: {estimate_with_ref.confidence}")
    print(f"  Real dimensions: {estimate_with_ref.details['dimensions_cm']}")
    
    # Test volume to weight conversion
    weight = estimator.convert_volume_to_weight(
        volume_ml=500,
        density_g_per_ml=0.75,
        density_confidence=0.80
    )
    
    print(f"✓ Volume to weight conversion:")
    print(f"  500ml rice = {weight.estimated_value}g")


async def test_openfoodfacts_client():
    """Test OpenFoodFacts API integration"""
    print("\n=== Testing OpenFoodFacts Client ===")
    
    from app.integrations.openfoodfacts import OpenFoodFactsClient
    
    client = OpenFoodFactsClient()
    
    try:
        # Test with a known product
        result = await client.lookup_barcode("737628064502")  # Nutella
        
        if result:
            print(f"✓ OpenFoodFacts lookup successful")
            print(f"  Product: {result['product_name']}")
            print(f"  Brand: {result.get('brand', 'N/A')}")
            print(f"  Quantity: {result.get('quantity_value')} {result.get('quantity_unit')}")
        else:
            print("⚠ Product not found (may not be in OpenFoodFacts)")
        
        # Test search
        products = await client.search_products("rice", limit=5)
        print(f"✓ Search found {len(products)} products")
        
    finally:
        await client.close()


async def run_all_tests():
    """Run all tests"""
    print("=" * 60)
    print("ADVANCED SCANNING FEATURES - TEST SUITE")
    print("=" * 60)
    
    if not AUTH_TOKEN:
        print("\n⚠ Warning: AUTH_TOKEN not set. Some tests may fail.")
        print("Set AUTH_TOKEN environment variable with valid JWT token.\n")
    
    # Unit tests (no API required)
    await test_quantity_estimator()
    await test_openfoodfacts_client()
    
    # API tests (require deployed backend)
    if AUTH_TOKEN and API_BASE_URL:
        try:
            await test_multi_language_search()
            await test_barcode_scanning()
        except Exception as e:
            print(f"\n⚠ API tests failed: {e}")
            print("Make sure backend is deployed and AUTH_TOKEN is valid.")
    
    print("\n" + "=" * 60)
    print("TEST SUITE COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_all_tests())
