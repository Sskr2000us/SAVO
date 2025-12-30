# Family Profile Settings Guide

## Overview
Complete family profile configuration system for personalized meal planning with medical dietary needs, cultural preferences, and regional appropriateness.

## Features

### 1. Regional & Cultural Settings
Configure meal appropriateness based on location and culture:

- **Region**: US, IN (India), UK, CA, AU
- **Culture**: western, indian, asian, middle_eastern, mediterranean
- **Meal Times**: Configurable breakfast, lunch, dinner windows
  - Example: India lunch 13:00-15:00, US dinner 18:00-21:00

### 2. Meal Preferences
Customize meal styles for each meal type:

- **Breakfast**: continental, indian, american, healthy
- **Lunch**: balanced, light, hearty, quick
- **Dinner**: family_meal, romantic, quick, elaborate
- **Dinner Courses**: 1-5 courses

### 3. Family Members
Add unlimited family members with detailed profiles:

#### Basic Information
- **Name**: Text input
- **Age**: Number (0-120)
- **Age Category**: Auto-set or manual
  - Child (0-12)
  - Teen (13-17)
  - Adult (18-64)
  - Senior (65+)

#### Dietary Requirements
**Dietary Restrictions** (multi-select):
- vegetarian, vegan, halal, kosher
- gluten-free, dairy-free, pescatarian

**Allergens** (multi-select):
- peanuts, tree nuts, shellfish, fish
- eggs, milk, soy, wheat

**Health Conditions** (multi-select):
- diabetes, hypertension, high_cholesterol
- kidney_disease, heart_disease

**Medical Dietary Needs** (checkboxes):
- ☐ Low Sodium (for hypertension, heart disease)
- ☐ Low Sugar (for diabetes)
- ☐ Low Fat (for cholesterol, heart disease)

**Spice Tolerance**:
- none → mild → medium → hot → very_hot

## How It Works

### Backend Integration
- **Load**: GET /config - Auto-loads on screen open
- **Save**: PUT /config - Saves all settings
- **Format**: JSON with household_profile and global_settings

### Meal Planning Integration
When you plan meals, the system automatically:
1. **Enforces** dietary restrictions and allergens
2. **Applies** medical dietary needs (low sodium/sugar/fat)
3. **Adjusts** spice levels for all family members
4. **Selects** culturally appropriate recipes
5. **Times** meals based on regional customs
6. **Scales** portions by age category

### Time-Based Classification
The system intelligently classifies meals:
- 13:30 in India → Lunch (dal, rice, roti)
- 19:00 in US → Dinner (pasta, protein, salad)
- 08:00 anywhere → Breakfast (regional style)

## Example: Indian Family

### Configuration
```
Region: IN (India)
Culture: indian
Meal Times:
  - Breakfast: 08:00-10:00
  - Lunch: 13:00-15:00
  - Dinner: 20:00-22:00

Family Members:
  Father (45, adult)
    - Health: diabetes, hypertension
    - Medical: ✓ low_sodium, ✓ low_sugar
    - Spice: mild

  Mother (42, adult)
    - Dietary: vegetarian
    - Allergens: peanuts
    - Spice: medium

  Child (8, child)
    - Spice: none
    - Dislikes: bitter vegetables
```

### Meal Planning Result (13:30)
**Indian Lunch Menu** (automatically generated):
- Dal Tadka (low sodium, no peanuts)
- Jeera Rice (diabetes-friendly portion)
- Palak Paneer (vegetarian, mild spice)
- Roti (whole wheat for health)
- Raita (cooling, child-friendly)

**Features Applied**:
✓ Indian lunch recipes (cultural)
✓ Low sodium for father
✓ Low sugar options (diabetes)
✓ Vegetarian for mother
✓ No peanuts (allergen)
✓ Mild spice (family compromise)
✓ Age-appropriate portions

## Example: Western Family

### Configuration
```
Region: US
Culture: western
Meal Times:
  - Breakfast: 07:00-09:00
  - Lunch: 12:00-14:00
  - Dinner: 18:00-21:00

Family Members:
  Dad (50, adult)
    - Health: high_cholesterol
    - Medical: ✓ low_fat
    - Spice: medium

  Mom (48, adult)
    - Dietary: gluten-free
    - Spice: medium

  Teen (16, teen)
    - Preferences: pizza, pasta
    - Spice: hot
```

### Meal Planning Result (19:00)
**Western Dinner Menu**:
- Grilled Chicken Breast (low-fat for dad)
- Quinoa Pilaf (gluten-free for mom)
- Roasted Vegetables (healthy)
- Caesar Salad (gluten-free dressing)

**Features Applied**:
✓ Western dinner recipes (cultural)
✓ Low-fat protein (cholesterol)
✓ Gluten-free options
✓ Teen-appropriate portions
✓ Balanced nutrition

## UI Navigation

### Access Settings
1. Open SAVO app
2. Click **Settings icon** (⚙️ top right)
3. Settings screen opens with smooth animation

### Add Family Member
1. Click **"Add Member"** button (green)
2. Expand the new card
3. Fill in details:
   - Name → "John"
   - Age → 45 (auto-sets "adult")
   - Tap dietary restrictions chips
   - Tap allergen chips
   - Tap health condition chips
   - Check medical dietary needs
   - Select spice tolerance
4. Repeat for all family members

### Configure Regional Settings
1. Scroll to "Regional & Cultural Settings"
2. Select **Region** dropdown → IN
3. Select **Culture** dropdown → indian
4. Configure **Meal Times**:
   - Breakfast: 08:00-10:00
   - Lunch: 13:00-15:00
   - Dinner: 20:00-22:00

### Configure Meal Preferences
1. Scroll to "Meal Preferences"
2. Set **Breakfast Style** → indian
3. Set **Lunch Style** → balanced
4. Set **Dinner Style** → family_meal
5. Set **Dinner Courses** → 2

### Save Configuration
1. Click **Save icon** (💾 top right)
2. Wait for success notification
3. Configuration sent to backend
4. Ready for personalized meal planning

## Testing

### Local Development
```bash
# 1. Start Backend
cd C:\Users\sskr2\SAVO\services\api
.\.venv\Scripts\Activate.ps1
$env:SAVO_VISION_PROVIDER='openai'
$env:SAVO_REASONING_PROVIDER='openai'
uvicorn app.main:app --reload --port 8000

# 2. Update Flutter for localhost (optional)
# Edit: apps/mobile/lib/services/api_client.dart
# Uncomment: if (kIsWeb) return 'http://localhost:8000';

# 3. Run Flutter
cd C:\Users\sskr2\SAVO\apps\mobile
flutter run -d chrome
```

### Test Flow
1. **Configure Family**:
   - Add 2-3 family members
   - Set dietary restrictions
   - Add health conditions
   - Check medical needs

2. **Set Regional**:
   - Region: IN
   - Culture: indian
   - Lunch: 13:00-15:00

3. **Save Settings**:
   - Click save button
   - Verify success message

4. **Test Meal Planning**:
   - Go to home screen
   - Plan daily menu
   - Verify Indian lunch recipes
   - Verify medical restrictions enforced
   - Verify allergens excluded

### Production
- Backend: https://savo-ynp1.onrender.com
- Auto-deployed from GitHub
- Settings persist across sessions

## Technical Details

### API Endpoints
```
GET  /config       - Load configuration
PUT  /config       - Save configuration
POST /plan/daily   - Plan meals with config context
```

### Configuration Format
```json
{
  "household_profile": {
    "members": [
      {
        "member_id": "member_123",
        "name": "John",
        "age": 45,
        "age_category": "adult",
        "dietary_restrictions": ["vegetarian"],
        "allergens": ["peanuts"],
        "health_conditions": ["diabetes", "hypertension"],
        "medical_dietary_needs": {
          "low_sodium": true,
          "low_sugar": true
        },
        "spice_tolerance": "mild"
      }
    ]
  },
  "global_settings": {
    "region": "IN",
    "culture": "indian",
    "meal_times": {
      "breakfast": "08:00-10:00",
      "lunch": "13:00-15:00",
      "dinner": "20:00-22:00"
    },
    "breakfast_preferences": {
      "style": "indian"
    },
    "lunch_preferences": {
      "style": "balanced",
      "include_rice_roti": true
    },
    "dinner_preferences": {
      "style": "family_meal",
      "courses": 2
    }
  }
}
```

### Planning Context
When planning meals, the backend receives:
```json
{
  "time_available_minutes": 45,
  "servings": 4,
  "meal_type": "lunch",
  "meal_time": "13:30",
  "inventory": {...},
  "family_profile": {
    "members": [...],
    "region": "IN",
    "culture": "indian",
    "meal_preferences": {...}
  }
}
```

## Benefits

### For Users
- ✅ Personalized meal planning
- ✅ Medical dietary needs enforced automatically
- ✅ Culturally appropriate meals
- ✅ Individual family member preferences
- ✅ Age-appropriate portions
- ✅ Time-based meal suggestions

### For Developers
- ✅ Complete configuration system
- ✅ Backend integration ready
- ✅ Extensible family member model
- ✅ Clean UI with expansion tiles
- ✅ Form validation
- ✅ Error handling

## Roadmap

### Phase 1 (Complete ✅)
- [x] Backend models (config.py, planning.py)
- [x] Planning route integration
- [x] Flutter settings screen
- [x] Family member management
- [x] Regional/cultural settings
- [x] Meal preferences

### Phase 2 (Next)
- [ ] Food preferences autocomplete
- [ ] Equipment availability
- [ ] Budget preferences
- [ ] Favorite recipes
- [ ] Shopping list preferences

### Phase 3 (Future)
- [ ] Multiple profiles (work lunch vs family dinner)
- [ ] Guest mode (temporary dietary needs)
- [ ] Meal history and favorites
- [ ] Nutritional goals tracking
- [ ] Meal plan templates

## Commit Info
- **Commit**: fae3d2c
- **Date**: December 30, 2025
- **Files Changed**: 2 (settings_screen.dart, home_screen.dart)
- **Lines**: +656, -130
- **Status**: Pushed to GitHub

## Support
For issues or questions:
1. Check backend logs: `uvicorn app.main:app --reload --log-level debug`
2. Check Flutter console for errors
3. Verify API connectivity: `GET /config` in Swagger UI
4. Test with production backend: https://savo-ynp1.onrender.com/docs
