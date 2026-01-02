# QUANTITY ESTIMATION & SERVING SIZE - IMPLEMENTATION PLAN

**Date:** January 2, 2026  
**Priority:** 🔴 CRITICAL - Blocks recipe scaling and party planning features  
**Timeline:** 2-3 weeks

---

## Problem Statement

**Current Gap:** Vision scanning detects ingredients but not quantities.

**User Impact:**
- ❌ Can't determine if they have enough for a recipe
- ❌ Can't scale recipes for parties ("Is this enough for 8 people?")
- ❌ Can't track consumption rates or build shopping lists
- ❌ Recipe generation is "blind" to actual availability

**Business Impact:**
- SAVO recommends recipes users can't actually make
- Trust erosion when users discover missing quantities mid-cooking
- Competitive disadvantage (other apps have quantity tracking)

---

## Solution Architecture

### 3-Tier Approach (Progressive Enhancement)

```
Tier 3 (User Entry) → Tier 2 (OCR) → Tier 1 (Visual Estimation)
    ↓                      ↓                  ↓
  100% accurate       95% accurate       70% accurate
  Always available    Package labels      Reference objects
```

**Strategy:** Start with Tier 3 (easiest, 100% accurate), add Tier 2 (medium effort, high ROI), defer Tier 1 (complex, lower accuracy).

---

## Phase 1: Tier 3 - Manual Quantity Entry (Week 6)

### Goal
Allow users to enter/confirm quantities during ingredient confirmation.

### Database Changes

**File:** `services/api/migrations/003_add_quantities.sql`

```sql
-- Add quantity columns to user_pantry
ALTER TABLE user_pantry 
ADD COLUMN quantity DECIMAL(10,2),
ADD COLUMN unit VARCHAR(50),  -- 'grams', 'ml', 'pieces', 'cups', 'tbsp', 'tsp'
ADD COLUMN estimated BOOLEAN DEFAULT false,  -- true if auto-estimated, false if user-entered
ADD COLUMN confidence DECIMAL(3,2);  -- 0.0-1.0 for auto-estimates

-- Add quantity to detected_ingredients (from Vision API)
ALTER TABLE detected_ingredients
ADD COLUMN detected_quantity DECIMAL(10,2),
ADD COLUMN detected_unit VARCHAR(50),
ADD COLUMN quantity_confidence DECIMAL(3,2);

-- Create quantity_units reference table
CREATE TABLE quantity_units (
    id SERIAL PRIMARY KEY,
    unit_name VARCHAR(50) UNIQUE NOT NULL,
    category VARCHAR(20) NOT NULL,  -- 'weight', 'volume', 'count'
    base_unit VARCHAR(50) NOT NULL,  -- for conversion
    conversion_factor DECIMAL(10,6) NOT NULL,
    display_order INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert common units
INSERT INTO quantity_units (unit_name, category, base_unit, conversion_factor, display_order) VALUES
-- Weight
('grams', 'weight', 'grams', 1.0, 1),
('kg', 'weight', 'grams', 1000.0, 2),
('oz', 'weight', 'grams', 28.3495, 3),
('lb', 'weight', 'grams', 453.592, 4),

-- Volume
('ml', 'volume', 'ml', 1.0, 5),
('liters', 'volume', 'ml', 1000.0, 6),
('cups', 'volume', 'ml', 236.588, 7),
('tbsp', 'volume', 'ml', 14.7868, 8),
('tsp', 'volume', 'ml', 4.92892, 9),
('fl oz', 'volume', 'ml', 29.5735, 10),

-- Count
('pieces', 'count', 'pieces', 1.0, 11),
('items', 'count', 'pieces', 1.0, 12),
('cloves', 'count', 'pieces', 1.0, 13),
('slices', 'count', 'pieces', 1.0, 14);

-- Create index for fast unit lookups
CREATE INDEX idx_quantity_units_category ON quantity_units(category);
```

---

### Backend Changes

**File:** `services/api/app/core/unit_converter.py` (NEW)

```python
"""Unit conversion service for ingredient quantities"""

from typing import Dict, Tuple, Optional
from decimal import Decimal

class UnitConverter:
    """Convert between different units of measurement"""
    
    # Conversion table: {from_unit: {to_unit: factor}}
    CONVERSIONS = {
        # Weight conversions (base: grams)
        "grams": {"kg": 0.001, "oz": 0.035274, "lb": 0.00220462},
        "kg": {"grams": 1000, "oz": 35.274, "lb": 2.20462},
        "oz": {"grams": 28.3495, "kg": 0.0283495, "lb": 0.0625},
        "lb": {"grams": 453.592, "kg": 0.453592, "oz": 16},
        
        # Volume conversions (base: ml)
        "ml": {"liters": 0.001, "cups": 0.00422675, "tbsp": 0.067628, "tsp": 0.202884, "fl oz": 0.033814},
        "liters": {"ml": 1000, "cups": 4.22675, "tbsp": 67.628, "tsp": 202.884, "fl oz": 33.814},
        "cups": {"ml": 236.588, "liters": 0.236588, "tbsp": 16, "tsp": 48, "fl oz": 8},
        "tbsp": {"ml": 14.7868, "liters": 0.0147868, "cups": 0.0625, "tsp": 3, "fl oz": 0.5},
        "tsp": {"ml": 4.92892, "liters": 0.00492892, "cups": 0.0208333, "tbsp": 0.333333, "fl oz": 0.166667},
        "fl oz": {"ml": 29.5735, "liters": 0.0295735, "cups": 0.125, "tbsp": 2, "tsp": 6},
        
        # Count (no conversion needed)
        "pieces": {"items": 1, "cloves": 1, "slices": 1},
        "items": {"pieces": 1},
        "cloves": {"pieces": 1},
        "slices": {"pieces": 1},
    }
    
    @classmethod
    def convert(cls, quantity: float, from_unit: str, to_unit: str) -> float:
        """
        Convert quantity from one unit to another
        
        Args:
            quantity: Amount to convert
            from_unit: Source unit
            to_unit: Target unit
            
        Returns:
            Converted quantity
            
        Raises:
            ValueError: If conversion not supported
        """
        # Normalize unit names
        from_unit = from_unit.lower().strip()
        to_unit = to_unit.lower().strip()
        
        # Same unit, no conversion
        if from_unit == to_unit:
            return quantity
        
        # Check if conversion exists
        if from_unit not in cls.CONVERSIONS:
            raise ValueError(f"Unknown unit: {from_unit}")
        
        if to_unit not in cls.CONVERSIONS[from_unit]:
            raise ValueError(f"Cannot convert {from_unit} to {to_unit}")
        
        # Perform conversion
        factor = cls.CONVERSIONS[from_unit][to_unit]
        return quantity * factor
    
    @classmethod
    def get_unit_category(cls, unit: str) -> str:
        """Get category of unit (weight, volume, count)"""
        unit = unit.lower().strip()
        
        weight_units = ["grams", "kg", "oz", "lb"]
        volume_units = ["ml", "liters", "cups", "tbsp", "tsp", "fl oz"]
        count_units = ["pieces", "items", "cloves", "slices"]
        
        if unit in weight_units:
            return "weight"
        elif unit in volume_units:
            return "volume"
        elif unit in count_units:
            return "count"
        else:
            return "unknown"
    
    @classmethod
    def can_convert(cls, from_unit: str, to_unit: str) -> bool:
        """Check if conversion is possible"""
        from_unit = from_unit.lower().strip()
        to_unit = to_unit.lower().strip()
        
        if from_unit == to_unit:
            return True
        
        return (from_unit in cls.CONVERSIONS and 
                to_unit in cls.CONVERSIONS[from_unit])
```

---

**File:** `services/api/app/api/routes/scanning.py` (UPDATE)

Add to existing file:

```python
from app.core.unit_converter import UnitConverter

# Update ConfirmIngredientsRequest model
class IngredientConfirmation(BaseModel):
    detected_name: str
    status: str  # 'confirmed', 'rejected', 'modified'
    final_name: Optional[str] = None  # If modified
    quantity: Optional[float] = None  # NEW
    unit: Optional[str] = None  # NEW

# Update confirm-ingredients endpoint
@router.post("/api/scanning/confirm-ingredients")
async def confirm_ingredients(
    request: ConfirmIngredientsRequest,
    user_id: str = Depends(get_current_user_id)
):
    """Confirm scanned ingredients with quantities"""
    
    # ... existing code ...
    
    for confirmation in request.confirmations:
        if confirmation.status == "confirmed":
            final_name = confirmation.detected_name
        elif confirmation.status == "modified":
            final_name = confirmation.final_name
        else:  # rejected
            continue
        
        # Normalize name
        canonical_name = normalizer.normalize_name(final_name)
        
        # Prepare pantry item
        pantry_item = {
            "user_id": user_id,
            "scan_id": request.scan_id,
            "ingredient_name": canonical_name,
            "display_name": final_name,
            "quantity": confirmation.quantity,  # NEW
            "unit": confirmation.unit,  # NEW
            "estimated": False,  # User-entered, not estimated
            "confidence": 1.0,  # 100% confident (user confirmed)
            "source": "scan",
            "status": "available"
        }
        
        # Check if ingredient already exists in pantry
        existing = await supabase.table("user_pantry")\
            .select("*")\
            .eq("user_id", user_id)\
            .eq("ingredient_name", canonical_name)\
            .eq("status", "available")\
            .execute()
        
        if existing.data:
            # Update existing quantity
            old_qty = existing.data[0].get("quantity", 0) or 0
            old_unit = existing.data[0].get("unit", "")
            
            # Convert to same unit if possible
            if confirmation.unit and old_unit and UnitConverter.can_convert(confirmation.unit, old_unit):
                converted_qty = UnitConverter.convert(confirmation.quantity, confirmation.unit, old_unit)
                new_qty = old_qty + converted_qty
                
                await supabase.table("user_pantry")\
                    .update({"quantity": new_qty, "updated_at": "now()"})\
                    .eq("id", existing.data[0]["id"])\
                    .execute()
            else:
                # Can't convert, just add as new row
                await supabase.table("user_pantry").insert(pantry_item).execute()
        else:
            # Insert new
            await supabase.table("user_pantry").insert(pantry_item).execute()
        
        confirmed_count += 1
    
    return {
        "success": True,
        "confirmed_count": confirmed_count,
        "rejected_count": rejected_count,
        "modified_count": modified_count
    }
```

---

### Flutter UI Changes

**File:** `apps/mobile/lib/screens/scanning/ingredient_confirmation_screen.dart` (UPDATE)

Add quantity picker to each ingredient card:

```dart
class _IngredientConfirmationScreenState extends State<IngredientConfirmationScreen> {
  // Add quantity tracking
  Map<String, double> ingredientQuantities = {};
  Map<String, String> ingredientUnits = {};
  
  // Common units by ingredient type
  final Map<String, List<String>> unitOptions = {
    'produce': ['pieces', 'grams', 'kg'],
    'liquid': ['ml', 'liters', 'cups'],
    'spice': ['grams', 'tbsp', 'tsp'],
    'default': ['pieces', 'grams', 'ml', 'cups'],
  };
  
  Widget _buildIngredientCard(DetectedIngredient ingredient) {
    // Initialize quantity if not set
    if (!ingredientQuantities.containsKey(ingredient.detectedName)) {
      ingredientQuantities[ingredient.detectedName] = ingredient.detectedQuantity ?? 1.0;
      ingredientUnits[ingredient.detectedName] = ingredient.detectedUnit ?? 'pieces';
    }
    
    return Card(
      child: Column(
        children: [
          // Existing ingredient name, confidence, allergens...
          
          // NEW: Quantity Picker
          Padding(
            padding: const EdgeInsets.all(8.0),
            child: Row(
              children: [
                Text('Quantity:', style: TextStyle(fontWeight: FontWeight.bold)),
                SizedBox(width: 8),
                
                // Decrement button
                IconButton(
                  icon: Icon(Icons.remove_circle_outline),
                  onPressed: () {
                    setState(() {
                      var current = ingredientQuantities[ingredient.detectedName]!;
                      if (current > 0.5) {
                        ingredientQuantities[ingredient.detectedName] = current - 0.5;
                      }
                    });
                  },
                ),
                
                // Quantity display/edit
                Container(
                  width: 60,
                  child: TextField(
                    textAlign: TextAlign.center,
                    keyboardType: TextInputType.numberWithOptions(decimal: true),
                    controller: TextEditingController(
                      text: ingredientQuantities[ingredient.detectedName].toString()
                    ),
                    onChanged: (value) {
                      setState(() {
                        ingredientQuantities[ingredient.detectedName] = 
                            double.tryParse(value) ?? 1.0;
                      });
                    },
                  ),
                ),
                
                // Increment button
                IconButton(
                  icon: Icon(Icons.add_circle_outline),
                  onPressed: () {
                    setState(() {
                      ingredientQuantities[ingredient.detectedName] = 
                          ingredientQuantities[ingredient.detectedName]! + 0.5;
                    });
                  },
                ),
                
                SizedBox(width: 8),
                
                // Unit dropdown
                DropdownButton<String>(
                  value: ingredientUnits[ingredient.detectedName],
                  items: _getUnitOptions(ingredient).map((String unit) {
                    return DropdownMenuItem<String>(
                      value: unit,
                      child: Text(unit),
                    );
                  }).toList(),
                  onChanged: (String? newUnit) {
                    if (newUnit != null) {
                      setState(() {
                        ingredientUnits[ingredient.detectedName] = newUnit;
                      });
                    }
                  },
                ),
              ],
            ),
          ),
          
          // Existing confirm/reject buttons...
        ],
      ),
    );
  }
  
  List<String> _getUnitOptions(DetectedIngredient ingredient) {
    // Smart unit suggestions based on ingredient category
    var category = ingredient.category ?? 'default';
    
    if (category.contains('vegetable') || category.contains('fruit')) {
      return unitOptions['produce']!;
    } else if (category.contains('dairy') || category.contains('liquid')) {
      return unitOptions['liquid']!;
    } else if (category.contains('spice')) {
      return unitOptions['spice']!;
    }
    
    return unitOptions['default']!;
  }
  
  Future<void> _submitConfirmations() async {
    // Build confirmations with quantities
    List<Map<String, dynamic>> confirmations = [];
    
    for (var ingredient in _detectedIngredients) {
      if (_confirmedIngredients.contains(ingredient.detectedName)) {
        confirmations.add({
          'detected_name': ingredient.detectedName,
          'status': 'confirmed',
          'quantity': ingredientQuantities[ingredient.detectedName],
          'unit': ingredientUnits[ingredient.detectedName],
        });
      }
      // ... handle rejected/modified ...
    }
    
    // Submit to API
    await _scanningService.confirmIngredients(
      widget.scanId,
      confirmations,
    );
    
    // Navigate back
    Navigator.pop(context);
  }
}
```

---

### Testing

**File:** `services/api/app/tests/test_quantity_conversion.py` (NEW)

```python
"""Tests for quantity conversion and storage"""

import pytest
from app.core.unit_converter import UnitConverter

class TestUnitConverter:
    """Test unit conversion functionality"""
    
    def test_same_unit_no_conversion(self):
        """No conversion needed for same unit"""
        assert UnitConverter.convert(5, "grams", "grams") == 5
    
    def test_weight_conversions(self):
        """Test weight unit conversions"""
        # Grams to kg
        assert UnitConverter.convert(1000, "grams", "kg") == 1.0
        
        # Kg to grams
        assert UnitConverter.convert(1, "kg", "grams") == 1000
        
        # Grams to oz
        result = UnitConverter.convert(100, "grams", "oz")
        assert abs(result - 3.5274) < 0.001
    
    def test_volume_conversions(self):
        """Test volume unit conversions"""
        # Cups to ml
        result = UnitConverter.convert(1, "cups", "ml")
        assert abs(result - 236.588) < 0.01
        
        # Tbsp to tsp
        assert UnitConverter.convert(1, "tbsp", "tsp") == 3
        
        # Liters to cups
        result = UnitConverter.convert(1, "liters", "cups")
        assert abs(result - 4.22675) < 0.001
    
    def test_count_conversions(self):
        """Test count unit conversions"""
        assert UnitConverter.convert(5, "pieces", "items") == 5
        assert UnitConverter.convert(3, "cloves", "pieces") == 3
    
    def test_invalid_conversion(self):
        """Test error handling for invalid conversions"""
        with pytest.raises(ValueError):
            UnitConverter.convert(5, "grams", "cups")  # Can't convert weight to volume
    
    def test_unit_categories(self):
        """Test unit category detection"""
        assert UnitConverter.get_unit_category("grams") == "weight"
        assert UnitConverter.get_unit_category("ml") == "volume"
        assert UnitConverter.get_unit_category("pieces") == "count"
```

**Estimated Time:** 3-4 days

---

## Phase 2: Serving Size Calculator (Week 6-7)

### Goal
Answer: "Do I have enough ingredients for N people?"

### Backend Changes

**File:** `services/api/app/core/serving_calculator.py` (NEW)

```python
"""Calculate serving sizes and ingredient sufficiency"""

from typing import Dict, List, Optional
from app.core.unit_converter import UnitConverter

class ServingCalculator:
    """Calculate if pantry has enough ingredients for N servings"""
    
    # Standard serving sizes (grams per person)
    STANDARD_SERVINGS = {
        # Proteins
        "chicken": 150,
        "beef": 150,
        "fish": 120,
        "pork": 150,
        "tofu": 100,
        
        # Vegetables
        "tomato": 80,
        "onion": 60,
        "carrot": 60,
        "potato": 150,
        "spinach": 60,
        
        # Carbs
        "rice": 60,  # dry weight
        "pasta": 80,  # dry weight
        "bread": 60,
        
        # Dairy
        "milk": 250,  # ml
        "yogurt": 150,
        "cheese": 30,
    }
    
    @classmethod
    def check_sufficiency(
        cls,
        pantry_items: Dict[str, Dict],  # {ingredient_name: {quantity, unit}}
        recipe_ingredients: List[Dict],  # [{name, quantity, unit}]
        recipe_servings: int,
        needed_servings: int
    ) -> Dict:
        """
        Check if pantry has enough for recipe
        
        Returns:
            {
                "sufficient": bool,
                "missing": [{ingredient, needed, unit}],
                "surplus": [{ingredient, extra}],
                "scaling_factor": float
            }
        """
        scaling_factor = needed_servings / recipe_servings
        missing = []
        surplus = []
        
        for ingredient in recipe_ingredients:
            required_qty = ingredient["quantity"] * scaling_factor
            required_unit = ingredient["unit"]
            ingredient_name = ingredient["name"]
            
            # Get pantry quantity
            pantry_item = pantry_items.get(ingredient_name, {})
            available_qty = pantry_item.get("quantity", 0)
            available_unit = pantry_item.get("unit", required_unit)
            
            # Convert to same unit if needed
            if available_unit != required_unit and UnitConverter.can_convert(available_unit, required_unit):
                available_qty = UnitConverter.convert(available_qty, available_unit, required_unit)
            
            # Check sufficiency
            if available_qty < required_qty:
                missing.append({
                    "ingredient": ingredient_name,
                    "needed": round(required_qty - available_qty, 2),
                    "unit": required_unit,
                    "have": round(available_qty, 2)
                })
            elif available_qty > required_qty * 1.5:
                # More than 50% extra
                surplus.append({
                    "ingredient": ingredient_name,
                    "extra": round(available_qty - required_qty, 2),
                    "unit": required_unit
                })
        
        return {
            "sufficient": len(missing) == 0,
            "missing": missing,
            "surplus": surplus,
            "scaling_factor": scaling_factor
        }
```

---

**File:** `services/api/app/api/routes/recipes.py` (UPDATE)

Add endpoint:

```python
from app.core.serving_calculator import ServingCalculator

@router.post("/api/recipes/check-sufficiency")
async def check_recipe_sufficiency(
    recipe_id: str,
    servings: int,
    user_id: str = Depends(get_current_user_id)
):
    """
    Check if user has enough ingredients for recipe
    
    Args:
        recipe_id: Recipe to check
        servings: Number of servings needed
    """
    # Get recipe with ingredients
    recipe = await supabase.table("recipes")\
        .select("*, recipe_ingredients(ingredient_name, quantity, unit)")\
        .eq("id", recipe_id)\
        .single()\
        .execute()
    
    # Get user's pantry with quantities
    pantry = await supabase.table("user_pantry")\
        .select("ingredient_name, quantity, unit")\
        .eq("user_id", user_id)\
        .eq("status", "available")\
        .execute()
    
    # Convert pantry to dict
    pantry_dict = {
        item["ingredient_name"]: {
            "quantity": item["quantity"],
            "unit": item["unit"]
        }
        for item in pantry.data
    }
    
    # Calculate sufficiency
    result = ServingCalculator.check_sufficiency(
        pantry_items=pantry_dict,
        recipe_ingredients=recipe.data["recipe_ingredients"],
        recipe_servings=recipe.data["servings"],
        needed_servings=servings
    )
    
    return result
```

---

### Flutter UI Changes

**File:** `apps/mobile/lib/screens/recipes/recipe_detail_screen.dart` (UPDATE)

Add serving calculator widget:

```dart
class _RecipeDetailScreenState extends State<RecipeDetailScreen> {
  int _servings = 4;  // Default
  Map<String, dynamic>? _sufficiencyResult;
  
  Widget _buildServingCalculator() {
    return Card(
      margin: EdgeInsets.all(16),
      child: Padding(
        padding: EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Plan Your Meal',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
            ),
            SizedBox(height: 12),
            
            // Serving size selector
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text('How many people?', style: TextStyle(fontSize: 16)),
                Row(
                  children: [
                    IconButton(
                      icon: Icon(Icons.remove_circle_outline),
                      onPressed: () {
                        if (_servings > 1) {
                          setState(() { _servings--; });
                          _sufficiencyResult = null;  // Clear old result
                        }
                      },
                    ),
                    Text('$_servings', style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
                    IconButton(
                      icon: Icon(Icons.add_circle_outline),
                      onPressed: () {
                        setState(() { _servings++; });
                        _sufficiencyResult = null;
                      },
                    ),
                  ],
                ),
              ],
            ),
            
            SizedBox(height: 12),
            
            // Check button
            ElevatedButton.icon(
              onPressed: _checkSufficiency,
              icon: Icon(Icons.check_circle_outline),
              label: Text('Check if I have enough'),
              style: ElevatedButton.styleFrom(
                minimumSize: Size(double.infinity, 48),
              ),
            ),
            
            // Results
            if (_sufficiencyResult != null)
              _buildSufficiencyResults(),
          ],
        ),
      ),
    );
  }
  
  Widget _buildSufficiencyResults() {
    final sufficient = _sufficiencyResult!['sufficient'] as bool;
    final missing = _sufficiencyResult!['missing'] as List;
    
    return Container(
      margin: EdgeInsets.only(top: 16),
      padding: EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: sufficient ? Colors.green[50] : Colors.orange[50],
        borderRadius: BorderRadius.circular(8),
        border: Border.all(
          color: sufficient ? Colors.green : Colors.orange,
          width: 2,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                sufficient ? Icons.check_circle : Icons.warning,
                color: sufficient ? Colors.green : Colors.orange,
              ),
              SizedBox(width: 8),
              Text(
                sufficient 
                    ? '✅ You have everything!' 
                    : '⚠️ Missing ${missing.length} items',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ],
          ),
          
          if (!sufficient) ...[
            SizedBox(height: 12),
            Text('Shopping List:', style: TextStyle(fontWeight: FontWeight.bold)),
            SizedBox(height: 8),
            ...missing.map((item) => Padding(
              padding: EdgeInsets.only(bottom: 4),
              child: Row(
                children: [
                  Icon(Icons.shopping_cart, size: 16),
                  SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      '${item['ingredient']}: ${item['needed']} ${item['unit']} more',
                      style: TextStyle(fontSize: 14),
                    ),
                  ),
                  IconButton(
                    icon: Icon(Icons.add_circle, color: Colors.blue),
                    iconSize: 20,
                    onPressed: () => _addToShoppingList(item),
                  ),
                ],
              ),
            )).toList(),
            
            SizedBox(height: 8),
            ElevatedButton.icon(
              onPressed: _addAllToShoppingList,
              icon: Icon(Icons.shopping_cart),
              label: Text('Add all to shopping list'),
              style: ElevatedButton.styleFrom(
                backgroundColor: Colors.orange,
                minimumSize: Size(double.infinity, 40),
              ),
            ),
          ],
        ],
      ),
    );
  }
  
  Future<void> _checkSufficiency() async {
    setState(() { _isLoading = true; });
    
    try {
      final result = await http.post(
        Uri.parse('${API_BASE_URL}/api/recipes/check-sufficiency'),
        headers: {
          'Authorization': 'Bearer $token',
          'Content-Type': 'application/json',
        },
        body: jsonEncode({
          'recipe_id': widget.recipeId,
          'servings': _servings,
        }),
      );
      
      if (result.statusCode == 200) {
        setState(() {
          _sufficiencyResult = jsonDecode(result.body);
        });
      }
    } catch (e) {
      print('Error checking sufficiency: $e');
    } finally {
      setState(() { _isLoading = false; });
    }
  }
}
```

**Estimated Time:** 5 days

---

## Phase 3: Tier 2 - OCR for Package Labels (Week 7)

### Goal
Auto-detect quantities from package labels (e.g., "16 oz", "500g").

### Implementation

**File:** `services/api/app/core/vision_api.py` (UPDATE)

Update prompt to extract quantities:

```python
def _build_detection_prompt(self, scan_type: str, location_hint: str) -> str:
    """Build Vision API prompt with quantity extraction"""
    
    prompt = f"""You are an ingredient detection system for a recipe app.

Analyze this image and detect ALL visible ingredients with the following information:
1. Ingredient name
2. Confidence level (0.0-1.0)
3. **QUANTITY** (if visible on labels or estimatable)
4. **UNIT** (grams, oz, ml, pieces, etc.)

Look for:
- Package labels with net weight ("16 oz", "500g", "2 cups")
- Serving sizes on nutrition labels
- Visible quantities (e.g., "2 apples", "1 can")

For produce/bulk items without labels:
- Estimate count if countable (e.g., "3 tomatoes")
- Use "pieces" as unit

Return JSON format:
{{
    "ingredients": [
        {{
            "name": "ingredient name",
            "confidence": 0.95,
            "quantity": 500,
            "unit": "grams",
            "quantity_confidence": 0.90  // How confident about quantity
        }}
    ]
}}
"""
    return prompt

def _parse_detection_response(self, response_text: str) -> List[Dict]:
    """Parse Vision API response with quantity extraction"""
    
    # ... existing parsing ...
    
    for item in parsed_data.get("ingredients", []):
        detection = {
            "detected_name": item.get("name", "unknown"),
            "confidence": item.get("confidence", 0.5),
            "quantity": item.get("quantity"),  # NEW
            "unit": item.get("unit"),  # NEW
            "quantity_confidence": item.get("quantity_confidence", 0.5),  # NEW
        }
        detections.append(detection)
    
    return detections
```

---

### Testing

Test with various package labels:
- Milk carton: "1 Gallon" → 3.785 liters
- Flour bag: "5 lb" → 2268 grams
- Tomato sauce: "28 oz" → 794 grams
- Spice jar: "2 oz" → 57 grams

**Estimated Time:** 5 days

---

## Success Metrics

### Phase 1 (Manual Entry)
- ✅ Users can enter quantities for 100% of confirmed ingredients
- ✅ Unit conversions work correctly (>99% accuracy)
- ✅ Quantities persist in pantry database
- ✅ UI is intuitive (< 3 taps to set quantity)

### Phase 2 (Serving Calculator)
- ✅ Correctly identifies missing ingredients (>95%)
- ✅ Accurate quantity calculations (>98%)
- ✅ Handles unit conversions (>99%)
- ✅ Response time < 500ms

### Phase 3 (OCR)
- ✅ Detects package quantities (>80% for visible labels)
- ✅ Parses common formats ("16 oz", "500g", "2 cups")
- ✅ Reduces manual entry needed by 40-50%

---

## Timeline

| Week | Phase | Tasks | Effort |
|------|-------|-------|--------|
| **Week 6** | Phase 1 | Database migration, backend API, Flutter UI | 3-4 days |
| **Week 6-7** | Phase 2 | Serving calculator backend, Flutter integration | 5 days |
| **Week 7** | Phase 3 | OCR enhancement, testing | 5 days |
| **Week 7** | Testing | E2E tests, user testing, bug fixes | 2-3 days |

**Total:** 15-17 days (3 weeks with buffer)

---

## Risk Mitigation

### Risk: Users don't enter quantities
**Mitigation:** 
- Make UI dead simple (+/- buttons, smart defaults)
- Show value ("Without quantities, we can't check if you have enough")
- Gamification (track pantry completion %)

### Risk: OCR fails for non-English labels
**Mitigation:**
- Phase 1 (manual entry) always works as fallback
- Show confidence indicator (low confidence → encourage manual review)
- Add language support in Q2 2026

### Risk: Unit conversions cause confusion
**Mitigation:**
- Show both units ("500g (1.1 lb)")
- Allow users to set preferred units in settings
- Smart defaults based on locale (US → oz/lb, rest → grams/kg)

---

## Next Steps

1. **Approve implementation plan**
2. **Run database migration (003_add_quantities.sql)**
3. **Start Phase 1 development** (Week 6)
4. **User testing** (internal team first)
5. **Iterate based on feedback**

**Ready to start implementation?** Let me know if you want me to begin with Phase 1!
