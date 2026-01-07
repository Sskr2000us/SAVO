"""
Seed Graph Intelligence Data
Seeds ingredient substitutions, confusions, and pairings
Based on culinary knowledge and common patterns
"""

import os
import sys
import asyncio
from datetime import datetime
import asyncpg

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DATABASE_URL = os.getenv("DATABASE_URL")

# ============================================================================
# GRAPH DATA DEFINITIONS
# ============================================================================

# Ingredient Substitutions (source → target)
SUBSTITUTIONS = [
    # Turmeric substitutions
    {"source": "Turmeric", "target": "Saffron", "type": "emergency", "score": 0.6, "forms": ["powder"], "dishes": ["rice_dishes", "curries"], "notes": "Use less saffron (more expensive, different flavor)"},
    {"source": "Turmeric", "target": "Paprika", "type": "emergency", "score": 0.5, "forms": ["powder"], "dishes": ["curries", "marinades"], "notes": "For color only, lacks turmeric's earthy flavor"},
    
    # Cumin substitutions
    {"source": "Cumin", "target": "Coriander", "type": "primary", "score": 0.7, "forms": ["ground", "whole"], "dishes": ["curries", "stews"], "notes": "Similar warm, earthy flavor profile"},
    {"source": "Cumin", "target": "Caraway Seeds", "type": "regional", "score": 0.65, "forms": ["whole"], "dishes": ["breads", "stews"], "notes": "Similar appearance and flavor"},
    
    # Coriander substitutions
    {"source": "Coriander", "target": "Cumin", "type": "primary", "score": 0.7, "forms": ["ground", "whole"], "dishes": ["curries", "marinades"], "notes": "Reverse substitution, slightly different flavor"},
    {"source": "Coriander", "target": "Cilantro", "type": "emergency", "score": 0.4, "forms": ["fresh"], "dishes": ["garnish", "salads"], "notes": "Fresh herb vs seed - very different uses"},
    
    # Ginger substitutions
    {"source": "Ginger", "target": "Garlic", "type": "emergency", "score": 0.5, "forms": ["fresh", "paste"], "dishes": ["curries", "stir_fry"], "notes": "Different flavor but similar pungency"},
    {"source": "Ginger", "target": "Galangal", "type": "regional", "score": 0.8, "forms": ["fresh", "dried"], "dishes": ["thai_curries", "soups"], "notes": "Similar root, slightly different flavor"},
    
    # Onion substitutions
    {"source": "Onion", "target": "Shallots", "type": "primary", "score": 0.85, "forms": ["fresh"], "dishes": ["curries", "stir_fry", "salads"], "notes": "Milder and sweeter than onions"},
    {"source": "Onion", "target": "Leeks", "type": "primary", "score": 0.7, "forms": ["fresh"], "dishes": ["soups", "stews"], "notes": "Milder flavor, good for cooking"},
    {"source": "Onion", "target": "Garlic", "type": "emergency", "score": 0.4, "forms": ["fresh"], "dishes": ["sauces", "curries"], "notes": "Stronger flavor, use less"},
    
    # Garlic substitutions
    {"source": "Garlic", "target": "Onion", "type": "emergency", "score": 0.4, "forms": ["fresh"], "dishes": ["curries", "stir_fry"], "notes": "Milder flavor, use more"},
    {"source": "Garlic", "target": "Shallots", "type": "primary", "score": 0.65, "forms": ["fresh"], "dishes": ["sauces", "marinades"], "notes": "Milder garlic-onion hybrid flavor"},
    
    # Tomato substitutions
    {"source": "Tomato", "target": "Bell Pepper", "type": "dietary", "score": 0.5, "forms": ["fresh"], "dishes": ["salads", "curries"], "notes": "For texture, not flavor"},
    {"source": "Tomato", "target": "Tomato Paste", "type": "primary", "score": 0.9, "forms": ["paste"], "dishes": ["curries", "sauces"], "notes": "Concentrated flavor, use less"},
    
    # Chicken substitutions
    {"source": "Chicken Breast", "target": "Tofu", "type": "dietary", "score": 0.6, "forms": ["cubed"], "dishes": ["curries", "stir_fry"], "notes": "Vegetarian alternative, different texture"},
    {"source": "Chicken Breast", "target": "Paneer", "type": "dietary", "score": 0.55, "forms": ["cubed"], "dishes": ["curries"], "notes": "Vegetarian alternative for Indian dishes"},
    
    # Paneer substitutions
    {"source": "Paneer", "target": "Tofu", "type": "primary", "score": 0.8, "forms": ["cubed"], "dishes": ["curries", "stir_fry"], "notes": "Similar texture when firm tofu used"},
    {"source": "Paneer", "target": "Halloumi", "type": "regional", "score": 0.75, "forms": ["cubed", "sliced"], "dishes": ["grilled", "curries"], "notes": "Similar texture, saltier flavor"},
    
    # Milk substitutions
    {"source": "Milk", "target": "Coconut Milk", "type": "dietary", "score": 0.7, "forms": ["liquid"], "dishes": ["curries", "desserts"], "notes": "Dairy-free, adds coconut flavor"},
    {"source": "Milk", "target": "Yogurt", "type": "primary", "score": 0.75, "forms": ["liquid"], "dishes": ["marinades", "curries"], "notes": "Adds tanginess, thinner consistency"},
    
    # Yogurt substitutions
    {"source": "Yogurt", "target": "Milk", "type": "emergency", "score": 0.6, "forms": ["liquid"], "dishes": ["marinades", "smoothies"], "notes": "Less tangy, thinner"},
    {"source": "Yogurt", "target": "Sour Cream", "type": "primary", "score": 0.85, "forms": ["thick"], "dishes": ["marinades", "dips"], "notes": "Similar texture and tang"},
    
    # Ghee substitutions
    {"source": "Ghee", "target": "Butter", "type": "primary", "score": 0.9, "forms": ["melted"], "dishes": ["cooking", "baking"], "notes": "Less nutty flavor, lower smoke point"},
    {"source": "Ghee", "target": "Coconut Oil", "type": "dietary", "score": 0.7, "forms": ["liquid", "solid"], "dishes": ["cooking", "baking"], "notes": "Dairy-free, coconut flavor"},
    
    # Cilantro substitutions
    {"source": "Cilantro", "target": "Parsley", "type": "primary", "score": 0.6, "forms": ["fresh"], "dishes": ["garnish", "salads"], "notes": "Milder flavor, similar appearance"},
    {"source": "Cilantro", "target": "Mint", "type": "emergency", "score": 0.5, "forms": ["fresh"], "dishes": ["chutneys", "garnish"], "notes": "Different flavor profile, refreshing"},
    
    # Mint substitutions
    {"source": "Mint", "target": "Cilantro", "type": "emergency", "score": 0.5, "forms": ["fresh"], "dishes": ["chutneys", "salads"], "notes": "Less refreshing, different flavor"},
    {"source": "Mint", "target": "Basil", "type": "regional", "score": 0.6, "forms": ["fresh"], "dishes": ["salads", "sauces"], "notes": "Aromatic herb, different flavor"},
    
    # Rice substitutions
    {"source": "Basmati Rice", "target": "Jasmine Rice", "type": "primary", "score": 0.85, "forms": ["grain"], "dishes": ["rice_dishes", "biryani"], "notes": "Similar aromatic quality"},
    {"source": "Basmati Rice", "target": "Long Grain Rice", "type": "primary", "score": 0.8, "forms": ["grain"], "dishes": ["rice_dishes"], "notes": "Less aromatic, similar texture"},
    
    # Lentil substitutions
    {"source": "Red Lentils", "target": "Yellow Lentils", "type": "primary", "score": 0.9, "forms": ["dried"], "dishes": ["dal", "soups"], "notes": "Very similar cooking properties"},
    {"source": "Red Lentils", "target": "Black Lentils", "type": "primary", "score": 0.7, "forms": ["dried"], "dishes": ["dal", "curries"], "notes": "Longer cooking time, different texture"},
]

# Ingredient Confusions (commonly mistaken pairs)
CONFUSIONS = [
    {"ing_a": "Turmeric", "ing_b": "Ginger", "reason": "similar_appearance", "rules": ["Turmeric is bright yellow inside", "Ginger is pale yellow/white inside"], "visual_diffs": ["Turmeric: bright yellow/orange flesh", "Ginger: pale tan flesh", "Turmeric stains easily"]},
    
    {"ing_a": "Cumin", "ing_b": "Caraway Seeds", "reason": "similar_appearance", "rules": ["Cumin seeds are slightly curved", "Caraway seeds are more crescent-shaped"], "visual_diffs": ["Cumin: lighter brown, ridged", "Caraway: darker, smooth"]},
    
    {"ing_a": "Coriander", "ing_b": "Cilantro", "reason": "same_plant", "rules": ["Coriander is the seed", "Cilantro is the fresh leaf"], "visual_diffs": ["Coriander: round brown seeds", "Cilantro: green leafy herb"]},
    
    {"ing_a": "Onion", "ing_b": "Shallots", "reason": "similar_appearance", "rules": ["Onions are larger, rounder", "Shallots are smaller, elongated"], "visual_diffs": ["Onion: large bulbs, papery skin", "Shallots: small bulbs, coppery skin"]},
    
    {"ing_a": "Garlic", "ing_b": "Onion", "reason": "same_category", "rules": ["Garlic has distinct cloves", "Onions have layers"], "visual_diffs": ["Garlic: white bulb with cloves", "Onion: larger, layered bulb"]},
    
    {"ing_a": "Cilantro", "ing_b": "Parsley", "reason": "similar_appearance", "rules": ["Cilantro has rounded leaves", "Parsley has pointed leaves"], "visual_diffs": ["Cilantro: delicate, lacy leaves", "Parsley: darker, pointed leaves"]},
    
    {"ing_a": "Mint", "ing_b": "Basil", "reason": "similar_appearance", "rules": ["Mint has serrated edges", "Basil has smooth edges"], "visual_diffs": ["Mint: pointed, serrated leaves", "Basil: smooth, rounded leaves"]},
    
    {"ing_a": "Black Pepper", "ing_b": "Peppercorn", "reason": "similar_name", "rules": ["They are the same thing"], "visual_diffs": ["No difference - black pepper is dried peppercorn"]},
    
    {"ing_a": "Cardamom", "ing_b": "Cloves", "reason": "similar_appearance", "rules": ["Cardamom pods are green/white", "Cloves are dark brown nail-shaped"], "visual_diffs": ["Cardamom: green pods with seeds", "Cloves: dark nail-shaped buds"]},
    
    {"ing_a": "Paneer", "ing_b": "Tofu", "reason": "similar_appearance", "rules": ["Paneer is cheese (dairy)", "Tofu is soy-based"], "visual_diffs": ["Paneer: crumbly texture, dairy", "Tofu: silky texture, plant-based"]},
]

# Ingredient Pairings (classic combinations)
PAIRINGS = [
    # Classic Indian spice combinations
    {"ing_a": "Cumin", "ing_b": "Coriander", "score": 0.95, "type": "classic", "cuisines": ["indian", "middle_eastern"], "dishes": ["curries", "dal", "biryani"], "source": "expert_knowledge"},
    {"ing_a": "Turmeric", "ing_b": "Cumin", "score": 0.9, "type": "classic", "cuisines": ["indian"], "dishes": ["curries", "dal"], "source": "expert_knowledge"},
    {"ing_a": "Turmeric", "ing_b": "Ginger", "score": 0.85, "type": "classic", "cuisines": ["indian", "asian"], "dishes": ["curries", "stir_fry"], "source": "expert_knowledge"},
    {"ing_a": "Ginger", "ing_b": "Garlic", "score": 0.95, "type": "classic", "cuisines": ["indian", "chinese", "asian"], "dishes": ["curries", "stir_fry", "marinades"], "source": "expert_knowledge"},
    {"ing_a": "Onion", "ing_b": "Garlic", "score": 0.95, "type": "classic", "cuisines": ["indian", "italian", "universal"], "dishes": ["curries", "pasta", "stir_fry"], "source": "expert_knowledge"},
    {"ing_a": "Onion", "ing_b": "Tomato", "score": 0.9, "type": "classic", "cuisines": ["indian", "italian"], "dishes": ["curries", "sauces"], "source": "expert_knowledge"},
    {"ing_a": "Tomato", "ing_b": "Garlic", "score": 0.85, "type": "classic", "cuisines": ["italian", "indian"], "dishes": ["pasta", "curries"], "source": "expert_knowledge"},
    
    # Whole spices combinations
    {"ing_a": "Cardamom", "ing_b": "Cinnamon", "score": 0.9, "type": "classic", "cuisines": ["indian", "middle_eastern"], "dishes": ["biryani", "tea", "desserts"], "source": "expert_knowledge"},
    {"ing_a": "Cloves", "ing_b": "Cinnamon", "score": 0.85, "type": "classic", "cuisines": ["indian", "middle_eastern"], "dishes": ["biryani", "tea"], "source": "expert_knowledge"},
    {"ing_a": "Bay Leaves", "ing_b": "Black Pepper", "score": 0.8, "type": "classic", "cuisines": ["indian", "french"], "dishes": ["curries", "stews"], "source": "expert_knowledge"},
    
    # Vegetable combinations
    {"ing_a": "Potato", "ing_b": "Cauliflower", "score": 0.85, "type": "classic", "cuisines": ["indian"], "dishes": ["aloo_gobi", "curries"], "source": "expert_knowledge"},
    {"ing_a": "Spinach", "ing_b": "Paneer", "score": 0.95, "type": "classic", "cuisines": ["indian"], "dishes": ["palak_paneer"], "source": "expert_knowledge"},
    {"ing_a": "Carrot", "ing_b": "Potato", "score": 0.8, "type": "classic", "cuisines": ["universal"], "dishes": ["stews", "soups"], "source": "expert_knowledge"},
    {"ing_a": "Bell Pepper", "ing_b": "Onion", "score": 0.85, "type": "classic", "cuisines": ["universal"], "dishes": ["stir_fry", "fajitas"], "source": "expert_knowledge"},
    {"ing_a": "Eggplant", "ing_b": "Tomato", "score": 0.85, "type": "classic", "cuisines": ["indian", "mediterranean"], "dishes": ["curry", "ratatouille"], "source": "expert_knowledge"},
    
    # Protein pairings
    {"ing_a": "Chicken Breast", "ing_b": "Yogurt", "score": 0.9, "type": "classic", "cuisines": ["indian"], "dishes": ["tandoori", "marinades"], "source": "expert_knowledge"},
    {"ing_a": "Paneer", "ing_b": "Bell Pepper", "score": 0.85, "type": "classic", "cuisines": ["indian"], "dishes": ["paneer_tikka", "curries"], "source": "expert_knowledge"},
    {"ing_a": "Tofu", "ing_b": "Ginger", "score": 0.85, "type": "classic", "cuisines": ["chinese", "asian"], "dishes": ["stir_fry"], "source": "expert_knowledge"},
    {"ing_a": "Eggs", "ing_b": "Onion", "score": 0.8, "type": "classic", "cuisines": ["universal"], "dishes": ["omelette", "scrambled"], "source": "expert_knowledge"},
    
    # Dairy pairings
    {"ing_a": "Milk", "ing_b": "Cardamom", "score": 0.8, "type": "classic", "cuisines": ["indian"], "dishes": ["tea", "desserts"], "source": "expert_knowledge"},
    {"ing_a": "Yogurt", "ing_b": "Mint", "score": 0.9, "type": "classic", "cuisines": ["indian", "middle_eastern"], "dishes": ["raita", "tzatziki"], "source": "expert_knowledge"},
    {"ing_a": "Ghee", "ing_b": "Cumin", "score": 0.85, "type": "classic", "cuisines": ["indian"], "dishes": ["dal", "rice"], "source": "expert_knowledge"},
    
    # Herb and spice pairings
    {"ing_a": "Cilantro", "ing_b": "Lime", "score": 0.95, "type": "classic", "cuisines": ["mexican", "asian"], "dishes": ["salsa", "garnish"], "source": "expert_knowledge"},
    {"ing_a": "Mint", "ing_b": "Cilantro", "score": 0.8, "type": "classic", "cuisines": ["indian"], "dishes": ["chutney", "garnish"], "source": "expert_knowledge"},
    {"ing_a": "Curry Leaves", "ing_b": "Mustard Seeds", "score": 0.95, "type": "classic", "cuisines": ["indian"], "dishes": ["tadka", "sambar"], "source": "expert_knowledge"},
    
    # Oil pairings
    {"ing_a": "Mustard Oil", "ing_b": "Cumin", "score": 0.85, "type": "regional", "cuisines": ["bengali", "indian"], "dishes": ["fish_curry", "dal"], "source": "expert_knowledge"},
    {"ing_a": "Coconut Oil", "ing_b": "Curry Leaves", "score": 0.9, "type": "regional", "cuisines": ["south_indian"], "dishes": ["sambar", "curries"], "source": "expert_knowledge"},
    
    # Legume pairings
    {"ing_a": "Red Lentils", "ing_b": "Turmeric", "score": 0.9, "type": "classic", "cuisines": ["indian"], "dishes": ["dal"], "source": "expert_knowledge"},
    {"ing_a": "Chickpeas", "ing_b": "Tomato", "score": 0.85, "type": "classic", "cuisines": ["indian", "mediterranean"], "dishes": ["chana_masala", "hummus"], "source": "expert_knowledge"},
    {"ing_a": "Black Lentils", "ing_b": "Butter", "score": 0.9, "type": "classic", "cuisines": ["indian"], "dishes": ["dal_makhani"], "source": "expert_knowledge"},
]

# ============================================================================
# DATABASE OPERATIONS
# ============================================================================

async def get_ingredient_id(conn, canonical_name: str):
    """Get ingredient ID by canonical name"""
    result = await conn.fetchrow(
        "SELECT id FROM master_ingredients WHERE canonical_name = $1",
        canonical_name
    )
    return result["id"] if result else None

async def seed_substitutions(conn):
    """Seed ingredient substitutions"""
    print("\n" + "="*80)
    print("SEEDING INGREDIENT SUBSTITUTIONS")
    print("="*80)
    
    inserted = 0
    skipped = 0
    
    for sub in SUBSTITUTIONS:
        try:
            # Get ingredient IDs
            source_id = await get_ingredient_id(conn, sub["source"])
            target_id = await get_ingredient_id(conn, sub["target"])
            
            if not source_id or not target_id:
                print(f"⚠️  Skipping {sub['source']} → {sub['target']}: Ingredient not found")
                skipped += 1
                continue
            
            # Check if exists
            existing = await conn.fetchrow("""
                SELECT id FROM ingredient_substitutions
                WHERE source_ingredient_id = $1 AND target_ingredient_id = $2
            """, source_id, target_id)
            
            if existing:
                skipped += 1
                continue
            
            # Insert
            await conn.execute("""
                INSERT INTO ingredient_substitutions (
                    source_ingredient_id, target_ingredient_id,
                    substitution_type, similarity_score,
                    applicable_forms, applicable_dishes, notes
                ) VALUES ($1, $2, $3, $4, $5, $6, $7)
            """, source_id, target_id, sub["type"], sub["score"],
                sub["forms"], sub["dishes"], sub["notes"])
            
            print(f"✅ {sub['source']} → {sub['target']} ({sub['score']})")
            inserted += 1
            
        except Exception as e:
            print(f"❌ Error: {e}")
            continue
    
    print(f"\n✅ Inserted: {inserted}, Skipped: {skipped}")
    return inserted

async def seed_confusions(conn):
    """Seed ingredient confusions"""
    print("\n" + "="*80)
    print("SEEDING INGREDIENT CONFUSIONS")
    print("="*80)
    
    inserted = 0
    skipped = 0
    
    for conf in CONFUSIONS:
        try:
            # Get ingredient IDs
            ing_a_id = await get_ingredient_id(conn, conf["ing_a"])
            ing_b_id = await get_ingredient_id(conn, conf["ing_b"])
            
            if not ing_a_id or not ing_b_id:
                print(f"⚠️  Skipping {conf['ing_a']} ⟷ {conf['ing_b']}: Ingredient not found")
                skipped += 1
                continue
            
            # Check if exists
            existing = await conn.fetchrow("""
                SELECT id FROM ingredient_confusion
                WHERE (ingredient_a_id = $1 AND ingredient_b_id = $2)
                   OR (ingredient_a_id = $2 AND ingredient_b_id = $1)
            """, ing_a_id, ing_b_id)
            
            if existing:
                skipped += 1
                continue
            
            # Insert
            await conn.execute("""
                INSERT INTO ingredient_confusion (
                    ingredient_a_id, ingredient_b_id,
                    confusion_reason, disambiguation_rules, key_visual_differences
                ) VALUES ($1, $2, $3, $4, $5)
            """, ing_a_id, ing_b_id, conf["reason"],
                conf["rules"], conf["visual_diffs"])
            
            print(f"✅ {conf['ing_a']} ⟷ {conf['ing_b']}")
            inserted += 1
            
        except Exception as e:
            print(f"❌ Error: {e}")
            continue
    
    print(f"\n✅ Inserted: {inserted}, Skipped: {skipped}")
    return inserted

async def seed_pairings(conn):
    """Seed ingredient pairings"""
    print("\n" + "="*80)
    print("SEEDING INGREDIENT PAIRINGS")
    print("="*80)
    
    inserted = 0
    skipped = 0
    
    for pair in PAIRINGS:
        try:
            # Get ingredient IDs
            ing_a_id = await get_ingredient_id(conn, pair["ing_a"])
            ing_b_id = await get_ingredient_id(conn, pair["ing_b"])
            
            if not ing_a_id or not ing_b_id:
                print(f"⚠️  Skipping {pair['ing_a']} + {pair['ing_b']}: Ingredient not found")
                skipped += 1
                continue
            
            # Check if exists
            existing = await conn.fetchrow("""
                SELECT id FROM ingredient_pairings
                WHERE (ingredient_a_id = $1 AND ingredient_b_id = $2)
                   OR (ingredient_a_id = $2 AND ingredient_b_id = $1)
            """, ing_a_id, ing_b_id)
            
            if existing:
                skipped += 1
                continue
            
            # Insert
            await conn.execute("""
                INSERT INTO ingredient_pairings (
                    ingredient_a_id, ingredient_b_id,
                    pairing_score, pairing_type,
                    cuisine_types, dish_types, source
                ) VALUES ($1, $2, $3, $4, $5, $6, $7)
            """, ing_a_id, ing_b_id, pair["score"], pair["type"],
                pair["cuisines"], pair["dishes"], pair["source"])
            
            print(f"✅ {pair['ing_a']} + {pair['ing_b']} ({pair['score']})")
            inserted += 1
            
        except Exception as e:
            print(f"❌ Error: {e}")
            continue
    
    print(f"\n✅ Inserted: {inserted}, Skipped: {skipped}")
    return inserted

# ============================================================================
# MAIN
# ============================================================================

async def main():
    """Main seeding function"""
    if not DATABASE_URL:
        print("❌ ERROR: DATABASE_URL not set")
        return
    
    print("\n" + "="*80)
    print("SAVO GRAPH INTELLIGENCE SEEDER")
    print(f"Time: {datetime.now().isoformat()}")
    print("="*80)
    
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        print("✅ Connected to database")
        
        # Seed all graph data
        sub_count = await seed_substitutions(conn)
        conf_count = await seed_confusions(conn)
        pair_count = await seed_pairings(conn)
        
        await conn.close()
        
        print("\n" + "="*80)
        print("🎉 GRAPH SEEDING COMPLETE!")
        print(f"   • {sub_count} substitutions")
        print(f"   • {conf_count} confusions")
        print(f"   • {pair_count} pairings")
        print("="*80 + "\n")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(main())
