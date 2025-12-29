# SAVO MVP Testing Checklist

**Test Date:** December 29, 2025  
**Tester:** User  
**Backend:** Mock LLM mode  
**Environment:** Flutter Web (Chrome) + FastAPI localhost:8000

---

## Pre-Test Setup

- [x] Backend running: `http://localhost:8000/health` returns 200 OK
- [x] Flutter app running: `http://localhost:52884`
- [x] Browser cache cleared (Ctrl+Shift+R)
- [ ] Settings configured with test household data

---

## Test 1: Daily Menu Planning (S1 → S3 → S4 → S7)

### 1.1 Daily Menu Generation
**Steps:**
1. Open Home screen
2. Click "Daily Menu"
3. Wait for loading spinner
4. Verify planning results screen appears

**Expected Results:**
- [ ] Loading spinner shows
- [ ] Results screen displays with cuisine selection
- [ ] Menu headers visible (Starter, Main, Side)
- [ ] 2-3 recipe cards per course with horizontal scroll
- [ ] Each card shows: name, time badge, difficulty badge
- [ ] "Start Cooking" button at bottom

**Actual Results:**
```
Status: 
Notes: 
```

---

### 1.2 Recipe Detail Navigation (S3 → S4)
**Steps:**
1. From planning results, tap any recipe card
2. Verify recipe detail screen appears

**Expected Results:**
- [ ] Recipe name in title
- [ ] Badges: time, difficulty, cuisine, cooking method
- [ ] Ingredients list with checkboxes
- [ ] First 3 steps visible in preview
- [ ] "Start Cooking" button visible

**Actual Results:**
```
Status: 
Notes: 
```

---

### 1.3 Cook Mode Flow (S4 → S7)
**Steps:**
1. From recipe detail, click "Start Cooking"
2. Verify cook mode screen with stepper UI
3. Check overall timer starts automatically
4. Tap "Start Timer" for step 1 (if step has time_minutes > 0)
5. Verify step timer counts down
6. Click "+1 min" button
7. Wait for timer to complete or click "Next Step"
8. Complete dialog appears with auto-advance option
9. Continue through all steps
10. On final step, click "Finish"

**Expected Results:**
- [ ] Cook mode screen loads with step 1
- [ ] Overall recipe timer visible and counting up
- [ ] Step timer shows when time_minutes > 0
- [ ] "Start Timer" button visible for timed steps
- [ ] Timer counts down when started
- [ ] "+1 min" adds 1 minute to step timer
- [ ] Step completion dialog shows with auto-advance checkbox
- [ ] Can navigate through all steps
- [ ] "Finish" button on last step
- [ ] Success message after finish

**Actual Results:**
```
Status: 
Notes: 
```

---

## Test 2: Party Menu Planning (S6 → S3)

### 2.1 Party Planning - All Adults
**Steps:**
1. Navigate to Home screen
2. Click "Party Menu"
3. Set guest count: 10
4. Set age distribution:
   - child_0_12: 0
   - teen_13_17: 0
   - adult_18_plus: 10
5. Click "Generate Party Menu"

**Expected Results:**
- [ ] Guest slider works (2-80 range)
- [ ] Age steppers work
- [ ] Validation passes (sum = 10)
- [ ] Success feedback shown
- [ ] Planning results screen appears
- [ ] Recipes suitable for adults

**Actual Results:**
```
Status: 
Notes: 
```

---

### 2.2 Party Planning - With Kids
**Steps:**
1. Navigate to Party Menu screen
2. Set guest count: 12
3. Set age distribution:
   - child_0_12: 4
   - teen_13_17: 2
   - adult_18_plus: 6
4. Click "Generate Party Menu"

**Expected Results:**
- [ ] Validation passes (sum = 12)
- [ ] Planning results screen appears
- [ ] Recipes should be kid-friendly (mild spice, appropriate textures)
- [ ] At least one explicitly kid-friendly option per course

**Actual Results:**
```
Status: 
Notes: 
Recipe differences from adult-only party: 
```

---

### 2.3 Party Planning - Validation Error
**Steps:**
1. Navigate to Party Menu screen
2. Set guest count: 10
3. Set age distribution:
   - child_0_12: 3
   - teen_13_17: 2
   - adult_18_plus: 2
   (sum = 7, not 10)
4. Click "Generate Party Menu"

**Expected Results:**
- [ ] Validation error shown
- [ ] Error message explains sum mismatch
- [ ] No API call made
- [ ] User can correct values

**Actual Results:**
```
Status: 
Notes: 
```

---

## Test 3: Weekly Planning (S5 → S3 → per-day drill-down)

### 3.1 Weekly Planning - 3 Days
**Steps:**
1. Navigate to Home screen
2. Click "Weekly Planner"
3. Start date should default to today (Dec 29, 2025)
4. Select "3 days" from dropdown
5. Click "Generate Weekly Plan"

**Expected Results:**
- [ ] Date picker defaults to today
- [ ] Num days dropdown shows 1-4 options
- [ ] Planning summary card shows: "Planning for 3 days starting Dec 29, 2025"
- [ ] Planning results screen appears
- [ ] Contains planning_window with start_date, num_days, timezone
- [ ] Menu sections for 3 days (day_index 0, 1, 2)
- [ ] Each day shows date (2025-12-29, 2025-12-30, 2025-12-31)

**Actual Results:**
```
Status: 
Notes: 
Dates shown: 
```

---

### 3.2 Weekly Planning - 1 Day (edge case)
**Steps:**
1. Navigate to Weekly Planner
2. Keep start date as today
3. Select "1 day"
4. Click "Generate Weekly Plan"

**Expected Results:**
- [ ] Planning for 1 day only
- [ ] Single day section shows
- [ ] Date matches start_date

**Actual Results:**
```
Status: 
Notes: 
```

---

### 3.3 Weekly Planning - 4 Days (max)
**Steps:**
1. Navigate to Weekly Planner
2. Change start date to Jan 1, 2026
3. Select "4 days"
4. Click "Generate Weekly Plan"

**Expected Results:**
- [ ] Planning for 4 days
- [ ] Dates: Jan 1, 2, 3, 4, 2026
- [ ] All days rendered correctly

**Actual Results:**
```
Status: 
Notes: 
```

---

## Test 4: Inventory & Leftovers (S2 & S8)

### 4.1 Inventory Management
**Steps:**
1. Navigate to Settings → Inventory
2. Add new item:
   - Name: "Tomatoes"
   - Quantity: 5
   - Expiration: 2 days from now
   - State: fresh
3. Verify item appears in list
4. Check if expiring items are highlighted (orange)
5. Delete the test item

**Expected Results:**
- [ ] Add item form works
- [ ] Item appears in list
- [ ] Expiring items (≤3 days) show orange highlight
- [ ] Delete button works

**Actual Results:**
```
Status: 
Notes: 
```

---

### 4.2 Leftovers Center
**Steps:**
1. From inventory, add item with state="leftover"
2. Navigate to Leftovers tab
3. Verify leftover items appear
4. Check freshness indicators

**Expected Results:**
- [ ] Only leftover items shown
- [ ] Items with state='leftover' display
- [ ] Freshness indicators visible
- [ ] Refresh button works

**Actual Results:**
```
Status: 
Notes: 
```

---

## Test 5: Settings & Configuration (S9)

### 5.1 Settings - Save & Load
**Steps:**
1. Navigate to Settings
2. Update household profile:
   - Members: 4
   - Dietary restrictions: Add "vegetarian"
3. Change preferences:
   - Language: en-US
   - Measurement: metric
4. Update behavior settings:
   - Prefer expiring ingredients: ON
   - Avoid repetition days: 5
5. Click Save
6. Navigate away and back to Settings
7. Verify values persisted

**Expected Results:**
- [ ] All fields editable
- [ ] Save button works (200 OK)
- [ ] Values persist across navigation
- [ ] GET /config returns saved values

**Actual Results:**
```
Status: 
Notes: 
```

---

## Test 6: Backend Contract Verification

### 6.1 Daily Plan Schema Validation
**Command:**
```powershell
cd services\api
.\.venv\Scripts\Activate.ps1
$env:SAVO_LLM_PROVIDER="mock"
python test_daily_endpoint.py
```

**Expected Results:**
- [ ] Status: 200
- [ ] Response contains: status, selected_cuisine, menu_headers, menus, variety_log, nutrition_summary, waste_summary, shopping_suggestions
- [ ] No JSON validation errors

**Actual Results:**
```
Status: 
Response structure: 
```

---

### 6.2 Party Plan - Kids vs Adults
**Test Script:**
Create `test_party_kids.py`:
```python
import asyncio
import httpx

async def test():
    async with httpx.AsyncClient() as client:
        # Test with kids
        kids_response = await client.post(
            "http://localhost:8000/plan/party",
            json={
                "party_settings": {
                    "guest_count": 10,
                    "age_group_counts": {
                        "child_0_12": 4,
                        "teen_13_17": 0,
                        "adult_18_plus": 6
                    }
                }
            },
            timeout=30.0
        )
        print(f"With kids: {kids_response.status_code}")
        kids_menu = kids_response.json()
        
        # Test without kids
        adults_response = await client.post(
            "http://localhost:8000/plan/party",
            json={
                "party_settings": {
                    "guest_count": 10,
                    "age_group_counts": {
                        "child_0_12": 0,
                        "teen_13_17": 0,
                        "adult_18_plus": 10
                    }
                }
            },
            timeout=30.0
        )
        print(f"Adults only: {adults_response.status_code}")
        adults_menu = adults_response.json()
        
        # Compare recipes
        print("\nKids menu recipes:", [r['recipe_name'] for course in kids_menu['menus'][0]['courses'] for r in course['recipe_options']])
        print("Adults menu recipes:", [r['recipe_name'] for course in adults_menu['menus'][0]['courses'] for r in course['recipe_options']])

asyncio.run(test())
```

**Expected Results:**
- [ ] Both return 200
- [ ] Recipes differ based on age groups
- [ ] Kids version has kid-friendly indicators

**Actual Results:**
```
Status: 
Differences noted: 
```

---

### 6.3 Weekly Plan - Dates & Window
**Command:**
```powershell
python test_weekly_endpoint.py
```

Create `test_weekly_endpoint.py`:
```python
import asyncio
import httpx
from datetime import date

async def test():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/plan/weekly",
            json={
                "start_date": "2026-01-01",
                "num_days": 3
            },
            timeout=30.0
        )
        print(f"Status: {response.status_code}")
        data = response.json()
        print(f"Planning window: {data.get('planning_window')}")
        print(f"Number of menus: {len(data.get('menus', []))}")
        for menu in data.get('menus', []):
            print(f"  Day {menu.get('day_index')}: {menu.get('date')}")

asyncio.run(test())
```

**Expected Results:**
- [ ] Status: 200
- [ ] planning_window: {start_date: "2026-01-01", num_days: 3, timezone: "..."}
- [ ] 3 menus with day_index 0, 1, 2
- [ ] Dates: 2026-01-01, 2026-01-02, 2026-01-03

**Actual Results:**
```
Status: 
Planning window: 
Menus: 
```

---

## Summary

### Passed Tests: __ / 18

### Critical Issues:
```
1. 
2. 
3. 
```

### Minor Issues:
```
1. 
2. 
3. 
```

### Ready for Demo: [ ] Yes [ ] No

**Notes:**
```
```
