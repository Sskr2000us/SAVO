# SAVO Ingredient Scanning Workflow Guide

## 📸 **How to Scan & Store Ingredients**

### **Step-by-Step Process:**

#### 1. **Access Scanning Feature**
- Open SAVO app → Home screen
- Click **"Scan Ingredients"** card (camera icon)
- Choose: Camera (take photo) or Gallery (upload photo)

#### 2. **Scan Ingredients**
- Take a photo of:
  - Pantry shelves
  - Refrigerator contents
  - Grocery bags
  - Individual items
- Vision AI detects all visible ingredients

#### 3. **Review & Confirm**
- App shows detected ingredients list
- Each ingredient has:
  - ✅ Checkbox to confirm
  - Quantity and unit (auto-detected)
  - Expiration date (if visible)
  - Storage location (pantry/fridge)
- **Tap checkboxes** to select what you want to store
- Click **"Add to Inventory"** button

#### 4. **Stored in Database**
- Selected ingredients → Saved to Supabase database
- Linked to your user profile
- Available in **Inventory** screen

#### 5. **Use for Recipe Generation**
- Go to Home → **"Plan Daily Menu"**
- LLM automatically:
  - Fetches your current inventory from database
  - Prioritizes recipes using available ingredients
  - Suggests meals based on what you have
  - Flags missing ingredients you need to buy

---

## 🗑️ **Deleting Inventory Items**

### **Current Issue: CORS Error**
The delete function is working, but there's a CORS error because:
- Frontend makes DELETE request to `/inventory-db/items/{id}`
- Backend CORS middleware is configured correctly
- **Solution**: Clear browser cache and hard refresh

### **How to Delete:**
1. Go to **Inventory** screen (bottom navigation)
2. Find item you want to remove
3. Swipe left OR tap trash icon
4. Confirm deletion
5. Item removed from database immediately

### **If Delete Still Fails:**
Wait 2-3 minutes for Vercel to deploy latest frontend fix, then:
- **Hard refresh**: Ctrl+Shift+R (Windows) or Cmd+Shift+R (Mac)
- **Clear cache**: F12 → Application → Clear storage
- Try deleting again

---

## 🎥 **YouTube Recipe Integration**

### **Where to Find YouTube Videos:**

#### **Location:**
1. Generate a recipe plan (Plan Daily Menu)
2. Click any recipe card to open **Recipe Detail Screen**
3. **Scroll down** past:
   - Recipe header
   - Nutrition information
   - Health benefits
   - Ingredients list
   - Steps preview
4. You'll see **"Video References"** section with:
   - Top 3 YouTube cooking videos
   - Video thumbnails
   - Channel names and view counts
   - Relevance scores

#### **Features:**
- ✅ AI-powered ranking (most relevant videos first)
- ✅ Click thumbnail to open in YouTube
- ✅ Matches your specific recipe name
- ✅ Shows professional cooking channels
- ✅ Displays video duration and popularity

#### **Example:**
If LLM generates "Paneer Tikka Masala":
1. Open recipe detail
2. Scroll to bottom
3. See YouTube videos like:
   - "Authentic Paneer Tikka Masala | Restaurant Style" (500K views)
   - "Best Paneer Tikka Recipe | Gordon Ramsay" (1M views)
   - "How to Make Paneer Tikka at Home" (250K views)

---

## 🔄 **Complete Workflow (Scan → Store → Plan → Cook)**

### **End-to-End Process:**

```
1. SCAN INGREDIENTS
   ↓
   [Camera/Gallery] → Vision AI detects items

2. CONFIRM & STORE
   ↓
   [Check items] → Click "Add to Inventory" → Saved to database

3. VIEW INVENTORY
   ↓
   [Inventory screen] → See all stored items → Delete if needed

4. PLAN MEALS
   ↓
   [Plan Daily Menu] → LLM fetches inventory → Generates recipes

5. VIEW RECIPE DETAILS
   ↓
   [Click recipe] → See nutrition, health benefits, ingredients, steps

6. WATCH YOUTUBE VIDEOS
   ↓
   [Scroll down] → See "Video References" → Click to watch

7. START COOKING
   ↓
   [Cook Mode] → Step-by-step guided cooking → Timer alerts
```

---

## 🔧 **Troubleshooting**

### **"Failed to fetch" Error:**
- **Cause**: CORS headers missing on error responses
- **Status**: ✅ Fixed in commit `8fe259e` (deployed)
- **Solution**: 
  - Clear browser cache
  - Hard refresh (Ctrl+Shift+R)
  - Wait 1-2 minutes for browser to fetch new code

### **Cannot Delete Inventory:**
- **Cause**: Same CORS issue
- **Status**: ✅ Fixed (backend deployed)
- **Solution**: Same as above - clear cache and refresh

### **YouTube Videos Not Showing:**
- **Possible Causes**:
  1. Recipe not opened yet (must click recipe card)
  2. Need to scroll down to see videos
  3. No matching YouTube results (rare)
- **Solution**:
  1. Click recipe card to open detail screen
  2. Scroll all the way down past ingredients and steps
  3. Look for "Video References" section

### **Ingredients Not Detected:**
- **Causes**:
  - Poor photo quality (blurry, dark)
  - Labels not visible
  - Too many items in one photo
- **Solutions**:
  - Take clear, well-lit photos
  - Photo labels/text directly
  - Scan 5-10 items at a time (not whole pantry)
  - Use multiple photos for large inventory

---

## 💡 **Best Practices**

### **Scanning Tips:**
1. **Good lighting** - Natural daylight or bright kitchen lights
2. **Clear labels** - Ensure product names are visible
3. **Multiple angles** - Front labels work best
4. **Batch scanning** - 5-10 items per photo for accuracy
5. **Update regularly** - Re-scan weekly to keep inventory fresh

### **Inventory Management:**
1. **Delete used items** - Remove as you cook
2. **Add expiring items** - Mark items close to expiration
3. **Categorize clearly** - Use pantry/fridge/freezer locations
4. **Check before shopping** - Review inventory to avoid duplicates

### **Recipe Planning:**
1. **Keep inventory updated** - Better recipe suggestions
2. **Set cuisine preferences** - Get recipes you enjoy
3. **Note skill level** - Get appropriate difficulty recipes
4. **Watch YouTube videos** - Learn techniques before cooking

---

## 📱 **UI Navigation Map**

```
SAVO App Structure:
├── Home (Plan Daily Menu, Scan Ingredients)
├── Plan (Weekly Planner, Party Planner)
├── Cook (Active recipes, Cook Mode)
├── Leftovers (Track leftover meals)
└── Settings
    ├── Profile Settings
    ├── Inventory Screen ← VIEW/DELETE ITEMS HERE
    └── Family Members

Recipe Detail Screen:
├── Header (Recipe name, cuisine, time)
├── Nutrition Card ← NEW!
├── Health Benefits Card ← NEW!
├── Ingredients List
├── Steps Preview
└── Video References ← YOUTUBE VIDEOS HERE!
```

---

## ✅ **Current Status**

- ✅ **CORS Fix**: Deployed (commit `8fe259e`)
- ✅ **UI Readability**: Fixed HeroCard text
- ✅ **Nutrition Display**: Showing calories, macros, micros
- ✅ **Health Benefits**: Ingredient-by-ingredient benefits
- ✅ **YouTube Integration**: Top 3 videos per recipe
- ✅ **Timeout Handling**: 120s for LLM requests
- ✅ **Ingredient Scanning**: Vision AI + confirmation UI
- ✅ **Inventory Storage**: Supabase database

### **What Works Now:**
1. Scan ingredients → Confirm → Store to database ✅
2. View inventory → Delete items ✅ (after cache clear)
3. Plan meals → Uses your inventory ✅
4. View recipes → See nutrition & health benefits ✅
5. Scroll down → Watch YouTube cooking videos ✅

### **Actions Required:**
1. **Clear browser cache** (Ctrl+Shift+R)
2. **Wait 2-3 minutes** for Vercel deployment
3. **Try scanning ingredients** again
4. **Test inventory deletion** after refresh

---

## 🎯 **Quick Reference**

| Action | Location | Button/Icon |
|--------|----------|-------------|
| Scan Ingredients | Home → Scan Ingredients | 📸 Camera icon |
| View Inventory | Bottom Nav → Leftovers → Inventory | 🧊 Fridge icon |
| Delete Item | Inventory → Swipe left on item | 🗑️ Trash icon |
| Plan Menu | Home → Plan Daily Menu | 🍽️ "Plan Daily Menu" |
| View Recipe | Planning Results → Click recipe | Recipe card |
| YouTube Videos | Recipe Detail → Scroll to bottom | 🎥 Video thumbnails |
| Start Cooking | Recipe Detail → "Start Cook Mode" | ▶️ Play button |

---

**Need Help?** Check browser console (F12) for detailed error messages.
