"""
Seed Regional Intelligence Data
Populates ingredient_regional_variants table with regional data
"""

import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()


# Regional variant data for ingredients
REGIONAL_VARIANTS = [
    # Turmeric - Native to South/Southeast Asia
    {
        "ingredient_name": "turmeric",
        "region": "India",
        "country_code": "IN",
        "variant_notes": "Highest quality turmeric (Lakadong, Alleppey, Madras varieties)",
        "flavor_differences": "Bright, earthy flavor with higher curcumin content",
        "appearance_differences": "Deep orange-yellow color, fresh rhizomes widely available",
        "typical_uses": "Essential in curries, dal, rice dishes, pickles, medicinal uses",
        "is_native": True,
        "availability_level": "abundant"
    },
    {
        "ingredient_name": "turmeric",
        "region": "Southeast Asia",
        "country_code": "TH",
        "variant_notes": "Thai and Indonesian varieties",
        "flavor_differences": "Slightly milder, more citrusy notes",
        "appearance_differences": "Fresh turmeric used more than powder",
        "typical_uses": "Curries, soups, medicinal beverages",
        "is_native": True,
        "availability_level": "common"
    },
    {
        "ingredient_name": "turmeric",
        "region": "United States",
        "country_code": "US",
        "variant_notes": "Imported, primarily powder form",
        "flavor_differences": "Standard quality, variable freshness",
        "appearance_differences": "Mostly powder, fresh rhizomes in specialty stores",
        "typical_uses": "Health supplements, ethnic cooking, golden milk",
        "is_native": False,
        "availability_level": "common"
    },
    
    # Cumin - Native to Mediterranean/Middle East
    {
        "ingredient_name": "cumin",
        "region": "India",
        "country_code": "IN",
        "variant_notes": "Major producer and consumer",
        "flavor_differences": "Strong, warm, earthy flavor",
        "appearance_differences": "Whole seeds and powder widely available",
        "typical_uses": "Tempering, spice blends (garam masala), curries",
        "is_native": False,
        "availability_level": "abundant"
    },
    {
        "ingredient_name": "cumin",
        "region": "Middle East",
        "country_code": "SA",
        "variant_notes": "Traditional spice in Arab cuisine",
        "flavor_differences": "Toasted cumin more common",
        "appearance_differences": "Whole seeds preferred",
        "typical_uses": "Meat dishes, rice, spice mixes (baharat)",
        "is_native": True,
        "availability_level": "abundant"
    },
    {
        "ingredient_name": "cumin",
        "region": "Mexico",
        "country_code": "MX",
        "variant_notes": "Essential in Mexican cuisine",
        "flavor_differences": "Used generously, often toasted",
        "appearance_differences": "Ground cumin more common than whole",
        "typical_uses": "Tacos, chili, beans, salsas",
        "is_native": False,
        "availability_level": "common"
    },
    
    # Coriander - Global use
    {
        "ingredient_name": "coriander",
        "region": "India",
        "country_code": "IN",
        "variant_notes": "Both seeds and fresh leaves (cilantro) heavily used",
        "flavor_differences": "Fresh, citrusy seeds; pungent leaves",
        "appearance_differences": "Whole seeds, powder, fresh leaves all common",
        "typical_uses": "Curries, chutneys, garnish, spice blends",
        "is_native": False,
        "availability_level": "abundant"
    },
    {
        "ingredient_name": "coriander",
        "region": "Southeast Asia",
        "country_code": "TH",
        "variant_notes": "Fresh cilantro (pak chee) and roots used extensively",
        "flavor_differences": "More emphasis on fresh herb than seeds",
        "appearance_differences": "Fresh herbs with roots attached",
        "typical_uses": "Curries, salads, soups, garnish",
        "is_native": False,
        "availability_level": "abundant"
    },
    {
        "ingredient_name": "coriander",
        "region": "Mexico",
        "country_code": "MX",
        "variant_notes": "Cilantro essential, seeds rarely used",
        "flavor_differences": "Fresh herb preferred",
        "appearance_differences": "Bunches of fresh cilantro",
        "typical_uses": "Salsas, tacos, garnish, guacamole",
        "is_native": False,
        "availability_level": "common"
    },
    
    # Ginger - Native to South/Southeast Asia
    {
        "ingredient_name": "ginger",
        "region": "India",
        "country_code": "IN",
        "variant_notes": "Native region, fresh ginger widely available",
        "flavor_differences": "Spicy, pungent, highly aromatic",
        "appearance_differences": "Fresh rhizomes of various sizes",
        "typical_uses": "Curries, chai, pickles, medicinal",
        "is_native": True,
        "availability_level": "abundant"
    },
    {
        "ingredient_name": "ginger",
        "region": "China",
        "country_code": "CN",
        "variant_notes": "Major producer, used fresh and preserved",
        "flavor_differences": "Fresh, young ginger preferred",
        "appearance_differences": "Young ginger with pink tips",
        "typical_uses": "Stir-fries, soups, tea, preserved ginger",
        "is_native": True,
        "availability_level": "abundant"
    },
    {
        "ingredient_name": "ginger",
        "region": "Japan",
        "country_code": "JP",
        "variant_notes": "Fresh and pickled (gari) forms",
        "flavor_differences": "Mild varieties preferred",
        "appearance_differences": "Young ginger, thinly sliced pickled",
        "typical_uses": "Sushi, pickles, tea, dressings",
        "is_native": False,
        "availability_level": "common"
    },
    
    # Garlic - Global use
    {
        "ingredient_name": "garlic",
        "region": "India",
        "country_code": "IN",
        "variant_notes": "Indian garlic smaller but more pungent",
        "flavor_differences": "Strong, spicy flavor",
        "appearance_differences": "Smaller cloves, purple-tinged skin",
        "typical_uses": "Curries, chutneys, tempering, pickles",
        "is_native": False,
        "availability_level": "abundant"
    },
    {
        "ingredient_name": "garlic",
        "region": "China",
        "country_code": "CN",
        "variant_notes": "Major producer, various sizes",
        "flavor_differences": "Standard pungency",
        "appearance_differences": "White bulbs, various sizes",
        "typical_uses": "Stir-fries, dumplings, sauces",
        "is_native": False,
        "availability_level": "abundant"
    },
    {
        "ingredient_name": "garlic",
        "region": "Mediterranean",
        "country_code": "IT",
        "variant_notes": "Softneck varieties, braided for storage",
        "flavor_differences": "Mild to medium pungency",
        "appearance_differences": "White bulbs, softneck varieties",
        "typical_uses": "Pasta, sauces, roasted, bread",
        "is_native": True,
        "availability_level": "common"
    },
    
    # Onion - Global use
    {
        "ingredient_name": "onion",
        "region": "India",
        "country_code": "IN",
        "variant_notes": "Red onions and shallots most common",
        "flavor_differences": "Pungent, strong flavor",
        "appearance_differences": "Red/purple varieties dominant",
        "typical_uses": "Base for curries, raw in salads, pickles",
        "is_native": False,
        "availability_level": "abundant"
    },
    {
        "ingredient_name": "onion",
        "region": "United States",
        "country_code": "US",
        "variant_notes": "Yellow, white, and red varieties",
        "flavor_differences": "Mild to medium",
        "appearance_differences": "Larger bulbs, yellow dominant",
        "typical_uses": "General cooking, burgers, salads",
        "is_native": False,
        "availability_level": "abundant"
    },
    {
        "ingredient_name": "onion",
        "region": "Europe",
        "country_code": "FR",
        "variant_notes": "Yellow and white varieties, shallots popular",
        "flavor_differences": "Sweet varieties preferred",
        "appearance_differences": "Medium-sized bulbs",
        "typical_uses": "Soups, sauces, caramelized, stocks",
        "is_native": False,
        "availability_level": "common"
    },
    
    # Tomato - Global use, New World origin
    {
        "ingredient_name": "tomato",
        "region": "India",
        "country_code": "IN",
        "variant_notes": "Small to medium varieties",
        "flavor_differences": "Tangy, used in cooked dishes",
        "appearance_differences": "Red, small to medium size",
        "typical_uses": "Curries, gravies, chutneys, salads",
        "is_native": False,
        "availability_level": "abundant"
    },
    {
        "ingredient_name": "tomato",
        "region": "Italy",
        "country_code": "IT",
        "variant_notes": "San Marzano, Roma varieties famous",
        "flavor_differences": "Sweet, rich flavor",
        "appearance_differences": "Plum tomatoes, various sizes",
        "typical_uses": "Sauces, pasta, pizza, caprese",
        "is_native": False,
        "availability_level": "common"
    },
    {
        "ingredient_name": "tomato",
        "region": "Mexico",
        "country_code": "MX",
        "variant_notes": "Native region (Mesoamerica)",
        "flavor_differences": "Varies by variety",
        "appearance_differences": "Diverse varieties, green tomatoes used",
        "typical_uses": "Salsas, sauces, soups, fresh",
        "is_native": True,
        "availability_level": "abundant"
    },
    
    # Chili Pepper - Native to Americas
    {
        "ingredient_name": "chili pepper",
        "region": "India",
        "country_code": "IN",
        "variant_notes": "Byadgi, Kashmiri, Thai bird's eye varieties",
        "flavor_differences": "Wide range from mild to extremely hot",
        "appearance_differences": "Red and green, various sizes",
        "typical_uses": "Curries, chutneys, pickles, tempering",
        "is_native": False,
        "availability_level": "abundant"
    },
    {
        "ingredient_name": "chili pepper",
        "region": "Mexico",
        "country_code": "MX",
        "variant_notes": "Native region, dozens of varieties (jalapeño, serrano, habanero, poblano)",
        "flavor_differences": "Complex flavors, not just heat",
        "appearance_differences": "Incredible diversity in colors and sizes",
        "typical_uses": "Salsas, moles, stews, stuffed",
        "is_native": True,
        "availability_level": "abundant"
    },
    {
        "ingredient_name": "chili pepper",
        "region": "Thailand",
        "country_code": "TH",
        "variant_notes": "Bird's eye chili (prik kee noo) dominant",
        "flavor_differences": "Very hot, sharp heat",
        "appearance_differences": "Small, thin peppers",
        "typical_uses": "Curries, stir-fries, condiments, salads",
        "is_native": False,
        "availability_level": "abundant"
    },
    
    # Potato - Global use
    {
        "ingredient_name": "potato",
        "region": "India",
        "country_code": "IN",
        "variant_notes": "Small to medium starchy varieties",
        "flavor_differences": "Starchy, holds shape in curries",
        "appearance_differences": "Brown-skinned, white flesh",
        "typical_uses": "Curries, aloo paratha, samosas, snacks",
        "is_native": False,
        "availability_level": "abundant"
    },
    {
        "ingredient_name": "potato",
        "region": "United States",
        "country_code": "US",
        "variant_notes": "Russet, Yukon Gold varieties",
        "flavor_differences": "Varies by variety",
        "appearance_differences": "Large tubers",
        "typical_uses": "Fries, baked, mashed, chips",
        "is_native": False,
        "availability_level": "abundant"
    },
    {
        "ingredient_name": "potato",
        "region": "Peru",
        "country_code": "PE",
        "variant_notes": "Native region, thousands of varieties",
        "flavor_differences": "Incredible diversity",
        "appearance_differences": "All colors including purple, yellow, red",
        "typical_uses": "Soups, stews, causa, papa rellena",
        "is_native": True,
        "availability_level": "abundant"
    },
    
    # Rice - Global use, Asian staple
    {
        "ingredient_name": "rice",
        "region": "India",
        "country_code": "IN",
        "variant_notes": "Basmati rice famous, diverse varieties",
        "flavor_differences": "Aromatic basmati, other varieties less aromatic",
        "appearance_differences": "Long-grain basmati, medium and short grain",
        "typical_uses": "Biryani, pulao, plain rice, desserts",
        "is_native": True,
        "availability_level": "abundant"
    },
    {
        "ingredient_name": "rice",
        "region": "Japan",
        "country_code": "JP",
        "variant_notes": "Short-grain japonica rice",
        "flavor_differences": "Sticky, slightly sweet",
        "appearance_differences": "Short, round grains",
        "typical_uses": "Sushi, rice bowls, onigiri",
        "is_native": False,
        "availability_level": "abundant"
    },
    {
        "ingredient_name": "rice",
        "region": "Thailand",
        "country_code": "TH",
        "variant_notes": "Jasmine rice (Hom Mali) famous",
        "flavor_differences": "Fragrant, slightly sticky",
        "appearance_differences": "Long-grain, translucent",
        "typical_uses": "Accompaniment to curries, fried rice",
        "is_native": True,
        "availability_level": "abundant"
    },
    
    # Coconut - Tropical regions
    {
        "ingredient_name": "coconut",
        "region": "India",
        "country_code": "IN",
        "variant_notes": "Tall and dwarf varieties, coastal regions",
        "flavor_differences": "Rich, creamy",
        "appearance_differences": "Mature brown coconuts dominant",
        "typical_uses": "Curries, chutneys, coconut milk, oil",
        "is_native": True,
        "availability_level": "common"
    },
    {
        "ingredient_name": "coconut",
        "region": "Southeast Asia",
        "country_code": "TH",
        "variant_notes": "Young and mature coconuts",
        "flavor_differences": "Sweet water from young coconuts",
        "appearance_differences": "Green young coconuts popular",
        "typical_uses": "Curries, desserts, coconut water, milk",
        "is_native": True,
        "availability_level": "abundant"
    },
    {
        "ingredient_name": "coconut",
        "region": "Caribbean",
        "country_code": "JM",
        "variant_notes": "Tropical coastal varieties",
        "flavor_differences": "Sweet, tropical",
        "appearance_differences": "Mature coconuts",
        "typical_uses": "Rice and peas, desserts, drinks",
        "is_native": True,
        "availability_level": "common"
    },
    
    # Lemon - Global use
    {
        "ingredient_name": "lemon",
        "region": "India",
        "country_code": "IN",
        "variant_notes": "Small, thin-skinned limes (nimbu) more common",
        "flavor_differences": "Very sour, used generously",
        "appearance_differences": "Small green limes, some yellow lemons",
        "typical_uses": "Pickles, beverages, garnish, chutneys",
        "is_native": False,
        "availability_level": "common"
    },
    {
        "ingredient_name": "lemon",
        "region": "Mediterranean",
        "country_code": "IT",
        "variant_notes": "Large, thick-skinned varieties",
        "flavor_differences": "Balanced sour-sweet",
        "appearance_differences": "Large yellow lemons",
        "typical_uses": "Salads, seafood, limoncello, desserts",
        "is_native": True,
        "availability_level": "common"
    },
    {
        "ingredient_name": "lemon",
        "region": "United States",
        "country_code": "US",
        "variant_notes": "Eureka and Lisbon varieties",
        "flavor_differences": "Standard tartness",
        "appearance_differences": "Medium-large yellow lemons",
        "typical_uses": "Beverages, cooking, baking",
        "is_native": False,
        "availability_level": "common"
    },
    
    # Yogurt - Global dairy product
    {
        "ingredient_name": "yogurt",
        "region": "India",
        "country_code": "IN",
        "variant_notes": "Dahi/curd - fresh, unstrained",
        "flavor_differences": "Tangy, mild",
        "appearance_differences": "Thinner consistency",
        "typical_uses": "Raita, lassi, curries, marinades",
        "is_native": False,
        "availability_level": "abundant"
    },
    {
        "ingredient_name": "yogurt",
        "region": "Greece",
        "country_code": "GR",
        "variant_notes": "Greek yogurt - strained, thick",
        "flavor_differences": "Tangy, creamy",
        "appearance_differences": "Very thick, creamy texture",
        "typical_uses": "Tzatziki, breakfast, dips",
        "is_native": True,
        "availability_level": "common"
    },
    {
        "ingredient_name": "yogurt",
        "region": "Middle East",
        "country_code": "TR",
        "variant_notes": "Turkish yogurt, labneh (strained)",
        "flavor_differences": "Rich, tangy",
        "appearance_differences": "Thick yogurt, cheese-like labneh",
        "typical_uses": "Mezze, sauces, soups, drinks",
        "is_native": True,
        "availability_level": "common"
    },
]


async def seed_regional_data():
    """Seed regional variant data into database"""
    database_url = os.getenv("DATABASE_URL")
    
    if not database_url:
        print("❌ DATABASE_URL not found in environment")
        return
    
    try:
        conn = await asyncpg.connect(database_url)
        print("✅ Connected to database")
        
        # Get ingredient IDs
        ingredient_map = {}
        ingredients = await conn.fetch("SELECT id, canonical_name FROM master_ingredients")
        for row in ingredients:
            ingredient_map[row["canonical_name"]] = row["id"]
        
        print(f"📋 Found {len(ingredient_map)} ingredients in database")
        
        # Insert regional variants
        inserted = 0
        skipped = 0
        
        for variant in REGIONAL_VARIANTS:
            ingredient_name = variant["ingredient_name"]
            
            if ingredient_name not in ingredient_map:
                print(f"⚠️  Ingredient '{ingredient_name}' not found in database, skipping")
                skipped += 1
                continue
            
            ingredient_id = ingredient_map[ingredient_name]
            
            # Check if variant already exists
            existing = await conn.fetchrow("""
                SELECT id FROM ingredient_regional_variants
                WHERE ingredient_id = $1 AND region = $2
            """, ingredient_id, variant["region"])
            
            if existing:
                print(f"⏭️  Variant already exists: {ingredient_name} - {variant['region']}")
                skipped += 1
                continue
            
            # Insert variant
            await conn.execute("""
                INSERT INTO ingredient_regional_variants (
                    ingredient_id,
                    region,
                    country_code,
                    variant_notes,
                    flavor_differences,
                    appearance_differences,
                    typical_uses,
                    is_native,
                    availability_level
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """,
                ingredient_id,
                variant["region"],
                variant["country_code"],
                variant["variant_notes"],
                variant["flavor_differences"],
                variant["appearance_differences"],
                variant["typical_uses"],
                variant["is_native"],
                variant["availability_level"]
            )
            
            print(f"✅ Inserted: {ingredient_name} - {variant['region']}")
            inserted += 1
        
        print(f"\n📊 Seeding Summary:")
        print(f"  ✅ Inserted: {inserted} regional variants")
        print(f"  ⏭️  Skipped: {skipped} (already exist or ingredient not found)")
        print(f"  📝 Total: {len(REGIONAL_VARIANTS)} variants processed")
        
        # Show statistics
        stats = await conn.fetchrow("""
            SELECT 
                COUNT(*) as total_variants,
                COUNT(DISTINCT ingredient_id) as ingredients_with_variants,
                COUNT(DISTINCT region) as unique_regions
            FROM ingredient_regional_variants
        """)
        
        print(f"\n📈 Database Statistics:")
        print(f"  Total regional variants: {stats['total_variants']}")
        print(f"  Ingredients with variants: {stats['ingredients_with_variants']}")
        print(f"  Unique regions: {stats['unique_regions']}")
        
        # Show regional breakdown
        print(f"\n🌍 Regional Breakdown:")
        regions = await conn.fetch("""
            SELECT region, COUNT(*) as count
            FROM ingredient_regional_variants
            GROUP BY region
            ORDER BY count DESC
        """)
        
        for region_row in regions:
            print(f"  {region_row['region']}: {region_row['count']} variants")
        
        await conn.close()
        print("\n✅ Seeding complete!")
        
    except Exception as e:
        print(f"❌ Error seeding data: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(seed_regional_data())
