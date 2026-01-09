"""Generate a large ingredient -> (storage, category, subcategory) mapping.

Goal: Provide 500-1000 common ingredient names mapped to the inventory taxonomy used
by the mobile app (storage -> category -> subcategory).

Output:
  docs/inventory_ingredient_map.v1.json

Notes:
- This is metadata only (no DB writes).
- Canonical names are emitted in snake_case.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple


ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = ROOT / "docs" / "inventory_ingredient_map.v1.json"
TAXONOMY_PATH = ROOT / "docs" / "inventory_taxonomy.v1.json"


def _snake_case(value: str) -> str:
    s = (value or "").strip().lower()
    s = s.replace("&", " and ")
    for ch in ["/", "-", ".", ",", "(", ")", "[", "]", "{", "}", ":", ";", "'", '"']:
        s = s.replace(ch, " ")
    s = "_".join(part for part in s.split() if part)
    while "__" in s:
        s = s.replace("__", "_")
    return s


@dataclass(frozen=True)
class IngredientRow:
    canonical_name: str
    storage_location: str
    category: str
    subcategory: Optional[str]


def _add(rows: List[IngredientRow], seen: Set[str], name: str, storage: str, category: str, subcategory: Optional[str]) -> None:
    canon = _snake_case(name)
    if not canon:
        return
    if canon in seen:
        return
    seen.add(canon)
    rows.append(
        IngredientRow(
            canonical_name=canon,
            storage_location=storage,
            category=_snake_case(category),
            subcategory=_snake_case(subcategory) if subcategory else None,
        )
    )


def build_rows() -> List[IngredientRow]:
    rows: List[IngredientRow] = []
    seen: Set[str] = set()

    # ---------------------------------------------------------------------
    # FRIDGE
    # ---------------------------------------------------------------------
    fridge = "fridge"

    # vegetables -> leafy
    for n in [
        "spinach",
        "baby_spinach",
        "fenugreek_leaves",
        "coriander_leaves",
        "mint_leaves",
        "dill",
        "parsley",
        "lettuce",
        "romaine_lettuce",
        "iceberg_lettuce",
        "kale",
        "arugula",
        "bok_choy",
        "mustard_greens",
        "spring_onion_greens",
        "curry_leaves",
        "amaranth_leaves",
        "collard_greens",
        "watercress",
        "swiss_chard",
        "moringa_leaves",
        "taro_leaves",
        "basil",
        "thai_basil",
        "tender_gongura",
    ]:
        _add(rows, seen, n, fridge, "vegetables", "leafy")

    # vegetables -> root
    for n in [
        "potato",
        "sweet_potato",
        "yam",
        "onion",
        "red_onion",
        "white_onion",
        "shallot",
        "garlic",
        "ginger",
        "beetroot",
        "radish",
        "daikon",
        "carrot",
        "baby_carrot",
        "turnip",
        "parsnip",
        "celeriac",
        "taro_root",
        "cassava",
        "lotus_root",
    ]:
        _add(rows, seen, n, fridge, "vegetables", "root")

    # vegetables -> cruciferous
    for n in [
        "cabbage",
        "red_cabbage",
        "napa_cabbage",
        "broccoli",
        "cauliflower",
        "brussels_sprouts",
        "kohlrabi",
    ]:
        _add(rows, seen, n, fridge, "vegetables", "cruciferous")

    # vegetables -> other
    for n in [
        "tomato",
        "cherry_tomato",
        "sun_dried_tomato",
        "cucumber",
        "zucchini",
        "eggplant",
        "baby_eggplant",
        "brinjal",
        "bell_pepper",
        "red_bell_pepper",
        "green_bell_pepper",
        "yellow_bell_pepper",
        "capsicum",
        "chili",
        "green_chili",
        "jalapeno",
        "habanero",
        "serrano_pepper",
        "okra",
        "green_beans",
        "french_beans",
        "snap_peas",
        "peas",
        "corn",
        "mushroom",
        "button_mushroom",
        "shiitake_mushroom",
        "oyster_mushroom",
        "portobello_mushroom",
        "enoki_mushroom",
        "king_oyster_mushroom",
        "asparagus",
        "celery",
        "leek",
        "spring_onion",
        "scallions",
        "pumpkin",
        "bottle_gourd",
        "ridge_gourd",
        "snake_gourd",
        "bitter_gourd",
        "ivygourd",
        "chayote",
        "ash_gourd",
        "raw_banana",
        "plantain_green",
        "sweet_pepper",
        "green_pepper",
        "red_pepper",
        "yellow_pepper",
        "fresh_peas",
        "edamame",
        "bean_sprouts",
        "bamboo_shoots",
        "water_chestnut",
        "coriander_stems",
    ]:
        _add(rows, seen, n, fridge, "vegetables", "other")

    # fruits
    for sub, names in {
        "berries": [
            "strawberry",
            "blueberry",
            "raspberry",
            "blackberry",
            "cranberry",
            "gooseberry",
            "mulberry",
        ],
        "citrus": [
            "lemon",
            "lime",
            "orange",
            "mandarin",
            "grapefruit",
            "sweet_lime",
        ],
        "tropical": [
            "mango",
            "pineapple",
            "papaya",
            "banana",
            "plantain",
            "guava",
            "coconut",
            "jackfruit",
            "lychee",
        ],
        "other": [
            "apple",
            "green_apple",
            "pear",
            "peach",
            "plum",
            "apricot",
            "cherry",
            "nectarine",
            "grapes",
            "raisins",
            "watermelon",
            "melon",
            "pomegranate",
            "kiwi",
            "fig",
            "dates_fresh",
            "avocado",
            "guava_pink",
            "dragon_fruit",
            "passion_fruit",
            "star_fruit",
            "persimmon",
        ],
    }.items():
        for n in names:
            _add(rows, seen, n, fridge, "fruits", sub)

    # dairy
    for sub, names in {
        "milk": [
            "milk",
            "whole_milk",
            "skim_milk",
            "lactose_free_milk",
            "almond_milk",
            "soy_milk",
            "oat_milk",
            "coconut_milk",
        ],
        "cheese": [
            "paneer",
            "mozzarella",
            "cheddar",
            "parmesan",
            "feta",
            "cream_cheese",
            "processed_cheese",
            "ricotta",
            "gouda",
            "emmental",
        ],
        "yogurt": [
            "yogurt",
            "greek_yogurt",
            "hung_curd",
            "curd",
            "buttermilk",
            "kefir",
        ],
        "butter": [
            "butter",
            "salted_butter",
            "unsalted_butter",
            "ghee",
        ],
        "other": [
            "cream",
            "whipping_cream",
            "sour_cream",
            "condensed_milk",
            "evaporated_milk",
            "milk_powder",
        ],
    }.items():
        for n in names:
            _add(rows, seen, n, fridge, "dairy", sub)

    # proteins
    for sub, names in {
        "eggs": ["eggs", "egg_whites", "egg_yolks", "quail_eggs"],
        "paneer": ["paneer_blocks", "paneer_crumbled"],
        "meat": [
            "chicken",
            "chicken_breast",
            "chicken_thigh",
            "mutton",
            "lamb",
            "beef",
            "pork",
            "sausage",
            "bacon",
            "ham",
            "turkey",
            "duck",
        ],
        "fish": [
            "fish",
            "salmon",
            "tuna",
            "prawns",
            "shrimp",
            "crab",
        ],
        "other": [
            "tofu",
            "tempeh",
            "seitan",
        ],
    }.items():
        for n in names:
            _add(rows, seen, n, fridge, "proteins", sub)

    # condiments
    for sub, names in {
        "sauces": [
            "ketchup",
            "mayonnaise",
            "mustard",
            "soy_sauce",
            "hot_sauce",
            "sriracha",
            "oyster_sauce",
            "fish_sauce",
            "bbq_sauce",
        ],
        "pickles": [
            "pickle",
            "mango_pickle",
            "lime_pickle",
            "mixed_pickle",
            "gherkin_pickles",
        ],
        "spreads": [
            "jam",
            "marmalade",
            "peanut_butter",
            "chocolate_spread",
            "hummus",
        ],
        "other": [
            "chutney",
            "mint_chutney",
            "coriander_chutney",
            "relish",
        ],
    }.items():
        for n in names:
            _add(rows, seen, n, fridge, "condiments", sub)

    # beverages
    for sub, names in {
        "juice": [
            "orange_juice",
            "apple_juice",
            "mango_juice",
            "pomegranate_juice",
            "coconut_water",
        ],
        "soft_drinks": ["cola", "soda", "sparkling_water", "tonic_water"],
        "other": ["cold_coffee", "iced_tea", "kombucha"],
    }.items():
        for n in names:
            _add(rows, seen, n, fridge, "beverages", sub)

    # leftovers
    for sub, names in {
        "cooked": [
            "cooked_rice",
            "cooked_pasta",
            "cooked_chicken",
            "cooked_vegetables",
        ],
        "prepared": [
            "cut_vegetables",
            "marinated_chicken",
            "dough",
            "batter",
        ],
        "other": ["leftover_curry", "leftover_dal", "leftover_soup"],
    }.items():
        for n in names:
            _add(rows, seen, n, fridge, "leftovers", sub)

    # ---------------------------------------------------------------------
    # PANTRY
    # ---------------------------------------------------------------------
    pantry = "pantry"

    # grains
    for sub, names in {
        "rice": [
            "basmati_rice",
            "sona_masoori_rice",
            "jasmine_rice",
            "brown_rice",
            "parboiled_rice",
            "idli_rice",
            "sushi_rice",
            "wild_rice",
            "arborio_rice",
            "risotto_rice",
            "red_rice",
            "black_rice",
            "sticky_rice",
            "broken_rice",
            "poha",
            "puffed_rice",
        ],
        "millets": [
            "finger_millet",
            "pearl_millet",
            "foxtail_millet",
            "little_millet",
            "barnyard_millet",
            "proso_millet",
            "sorghum",
            "kodo_millet",
            "teff",
        ],
        "wheat": [
            "wheat",
            "whole_wheat",
            "bulgur",
            "semolina",
            "couscous",
            "pasta",
            "spaghetti",
            "macaroni",
            "noodles",
            "vermicelli",
            "lasagna_sheets",
            "penne",
            "fusilli",
            "farfalle",
            "ramen_noodles",
            "udon_noodles",
            "soba_noodles",
        ],
        "oats": [
            "rolled_oats",
            "steel_cut_oats",
            "instant_oats",
        ],
        "other": [
            "quinoa",
            "barley",
            "buckwheat",
            "amaranth",
            "cornmeal",
            "polenta",
            "cereal",
        ],
    }.items():
        for n in names:
            _add(rows, seen, n, pantry, "grains", sub)

    # pulses
    for sub, names in {
        "lentils": [
            "red_lentils",
            "yellow_lentils",
            "brown_lentils",
            "green_lentils",
            "black_lentils",
            "split_pigeon_peas",
            "split_mung_beans",
            "whole_mung_beans",
            "toor_dal",
            "moong_dal",
            "masoor_dal",
            "urad_dal",
            "chana_dal",
        ],
        "beans": [
            "chickpeas",
            "kidney_beans",
            "black_beans",
            "pinto_beans",
            "navy_beans",
            "white_beans",
            "soybeans",
            "edamame_dried",
            "adzuki_beans",
            "lima_beans",
            "mung_beans",
        ],
        "chickpeas": [
            "chana_dal",
            "roasted_chana",
            "kabuli_chana",
            "kala_chana",
            "besan",
        ],
        "other": [
            "peas_dried",
            "black_eyed_peas",
            "horse_gram",
            "green_peas_dried",
            "pigeon_peas",
            "broad_beans",
        ],
    }.items():
        for n in names:
            _add(rows, seen, n, pantry, "pulses", sub)

    # flours
    for sub, names in {
        "wheat_flour": ["wheat_flour", "whole_wheat_flour", "maida", "semolina_flour"],
        "rice_flour": ["rice_flour", "idiyappam_flour", "glutinous_rice_flour"],
        "besan": ["besan", "gram_flour", "chickpea_flour"],
        "other": [
            "corn_flour",
            "cornstarch",
            "arrowroot_powder",
            "tapioca_starch",
            "almond_flour",
            "coconut_flour",
            "millet_flour",
            "ragi_flour",
            "jowar_flour",
            "bajra_flour",
            "oat_flour",
        ],
    }.items():
        for n in names:
            _add(rows, seen, n, pantry, "flours", sub)

    # spices
    for sub, names in {
        "whole": [
            "cumin_seeds",
            "mustard_seeds",
            "coriander_seeds",
            "fennel_seeds",
            "fenugreek_seeds",
            "black_pepper",
            "cloves",
            "cardamom",
            "green_cardamom",
            "black_cardamom",
            "cinnamon",
            "bay_leaf",
            "star_anise",
            "nutmeg",
            "mace",
            "dry_red_chili",
            "curry_leaves_dried",
            "carom_seeds",
            "nigella_seeds",
            "pomegranate_seeds",
            "white_pepper",
            "pink_peppercorn",
        ],
        "powdered": [
            "turmeric_powder",
            "chili_powder",
            "coriander_powder",
            "cumin_powder",
            "garam_masala_powder",
            "black_pepper_powder",
            "ginger_powder",
            "garlic_powder",
            "onion_powder",
            "paprika",
            "cayenne_pepper",
            "cinnamon_powder",
            "cardamom_powder",
            "clove_powder",
        ],
        "blends": [
            "garam_masala",
            "sambar_powder",
            "rasam_powder",
            "biryani_masala",
            "pav_bhaji_masala",
            "chai_masala",
            "tandoori_masala",
            "curry_powder",
            "taco_seasoning",
            "italian_seasoning",
            "five_spice",
            "zaatar",
            "herbes_de_provence",
        ],
        "other": [
            "asafoetida",
            "kasuri_methi",
            "sesame_seeds",
            "poppy_seeds",
            "dry_mango_powder",
            "sumac",
        ],
    }.items():
        for n in names:
            _add(rows, seen, n, pantry, "spices", sub)

    # powders
    for sub, names in {
        "baking": ["baking_powder", "baking_soda", "yeast", "gelatin", "agar_agar"],
        "protein": ["whey_protein", "plant_protein", "collagen_powder"],
        "other": ["cocoa_powder", "instant_coffee", "tea_powder", "malt_powder"],
    }.items():
        for n in names:
            _add(rows, seen, n, pantry, "powders", sub)

    # oils
    for sub, names in {
        "cooking_oils": [
            "sunflower_oil",
            "canola_oil",
            "olive_oil",
            "extra_virgin_olive_oil",
            "groundnut_oil",
            "mustard_oil",
            "coconut_oil",
            "sesame_oil",
            "rice_bran_oil",
        ],
        "ghee": ["ghee"],
        "vinegar": ["white_vinegar", "apple_cider_vinegar", "balsamic_vinegar", "rice_vinegar"],
        "other": ["cooking_spray"],
    }.items():
        for n in names:
            _add(rows, seen, n, pantry, "oils", sub)

    # snacks
    for sub, names in {
        "chips": ["potato_chips", "banana_chips", "tortilla_chips", "nachos"],
        "biscuits": ["biscuits", "cookies", "crackers", "digestive_biscuits"],
        "nuts": [
            "almonds",
            "cashews",
            "pistachios",
            "walnuts",
            "peanuts",
            "hazelnuts",
            "sunflower_seeds",
            "pumpkin_seeds",
        ],
        "other": ["popcorn_kernels", "muesli", "granola"],
    }.items():
        for n in names:
            _add(rows, seen, n, pantry, "snacks", sub)

    # canned
    for sub, names in {
        "vegetables": ["canned_corn", "canned_tomatoes", "tomato_puree", "tomato_paste"],
        "beans": ["canned_chickpeas", "canned_kidney_beans", "canned_black_beans"],
        "fish": ["canned_tuna", "canned_sardines"],
        "other": ["coconut_milk_can", "condensed_milk_can"],
    }.items():
        for n in names:
            _add(rows, seen, n, pantry, "canned", sub)

    # baking
    for sub, names in {
        "sugar": ["sugar", "brown_sugar", "powdered_sugar", "jaggery", "honey"],
        "baking_powder": ["baking_powder"],
        "cocoa": ["cocoa_powder", "chocolate_chips"],
        "other": ["vanilla_extract", "baking_chocolate", "sprinkles"],
    }.items():
        for n in names:
            _add(rows, seen, n, pantry, "baking", sub)

    # ---------------------------------------------------------------------
    # FREEZER
    # ---------------------------------------------------------------------
    freezer = "freezer"

    for sub, names in {
        "mixed": ["mixed_vegetables_frozen", "frozen_mix"],
        "leafy": ["frozen_spinach", "frozen_methi"],
        "other": ["frozen_peas", "frozen_corn", "frozen_broccoli"],
    }.items():
        for n in names:
            _add(rows, seen, n, freezer, "frozen_vegetables", sub)

    for sub, names in {
        "berries": ["frozen_strawberries", "frozen_blueberries", "frozen_mixed_berries"],
        "other": ["frozen_mango", "frozen_banana", "frozen_pineapple"],
    }.items():
        for n in names:
            _add(rows, seen, n, freezer, "frozen_fruits", sub)

    for sub, names in {
        "meat": ["chicken_frozen", "mutton_frozen", "mince_frozen"],
        "fish": ["fish_frozen", "prawns_frozen", "salmon_frozen"],
        "other": ["sausages_frozen"],
    }.items():
        for n in names:
            _add(rows, seen, n, freezer, "meat_seafood", sub)

    for sub, names in {
        "leftovers": ["leftover_paratha", "leftover_curry_frozen"],
        "ready_to_cook": ["frozen_fries", "frozen_nuggets", "frozen_paratha"],
        "other": ["frozen_pizza", "frozen_dumplings"],
    }.items():
        for n in names:
            _add(rows, seen, n, freezer, "prepared_meals", sub)

    for sub, names in {
        "ice_cream": ["ice_cream", "gelato", "sorbet"],
        "other": ["frozen_yogurt", "frozen_cake"],
    }.items():
        for n in names:
            _add(rows, seen, n, freezer, "desserts", sub)

    # ---------------------------------------------------------------------
    # COUNTER
    # ---------------------------------------------------------------------
    counter = "counter"

    for sub, names in {
        "fruits": ["banana_ripe", "apple_room_temp", "mango_ripe", "avocado_ripe"],
        "vegetables": ["tomato_room_temp", "onion_room_temp", "garlic_room_temp"],
        "other": ["lemon_room_temp"],
    }.items():
        for n in names:
            _add(rows, seen, n, counter, "produce", sub)

    for sub, names in {
        "bread": ["bread", "sandwich_bread", "sourdough"],
        "buns": ["burger_buns", "hotdog_buns"],
        "other": ["tortilla", "pita"],
    }.items():
        for n in names:
            _add(rows, seen, n, counter, "breads", sub)

    for sub, names in {
        "chips": ["chips_opened", "nachos_opened"],
        "biscuits": ["cookies_opened", "crackers_opened"],
        "nuts": ["almonds_opened", "cashews_opened"],
        "other": ["trail_mix"],
    }.items():
        for n in names:
            _add(rows, seen, n, counter, "snacks", sub)

    for n in ["other"]:
        _add(rows, seen, n, counter, "other", "other")

    # Ensure we land in the requested range.
    if not (500 <= len(rows) <= 1000):
        raise SystemExit(f"Expected 500-1000 ingredients, got {len(rows)}. Adjust lists.")

    rows.sort(key=lambda r: (r.storage_location, r.category, r.subcategory or "", r.canonical_name))
    return rows


def main() -> None:
    rows = build_rows()

    taxonomy = json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))

    payload = {
        "version": "1.0",
        "generated_at": date.today().isoformat(),
        "taxonomy_ref": {
            "path": str(TAXONOMY_PATH.relative_to(ROOT)).replace("\\", "/"),
            "version": taxonomy.get("version"),
        },
        "count": len(rows),
        "ingredients": [
            {
                "canonical_name": r.canonical_name,
                "storage_location": r.storage_location,
                "category": r.category,
                "subcategory": r.subcategory,
            }
            for r in rows
        ],
    }

    OUT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(rows)} rows -> {OUT_PATH}")


if __name__ == "__main__":
    main()
