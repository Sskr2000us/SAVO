# 🧪 PHYSICAL DEVICE TESTING GUIDE - Quantity Tracking System

**Testing Date:** January 2, 2026  
**App Version:** Beta v1.0  
**Features to Test:** Vision Scanning + Quantity Tracking + Serving Calculator

---

## 📱 Pre-Test Setup

### Requirements
- ✅ Physical Android device (API 21+) OR iOS device (iOS 12+)
- ✅ Device connected via USB with Developer Mode enabled
- ✅ Stable internet connection (WiFi or 4G/5G)
- ✅ Test ingredients available (see list below)
- ✅ Good lighting conditions
- ✅ Backend API running (https://savo-api.onrender.com)

### Installation Commands

**Android:**
```bash
cd C:\Users\sskr2\SAVO\apps\mobile
flutter run --release
# OR build APK
flutter build apk --release
# APK location: build/app/outputs/flutter-apk/app-release.apk
```

**iOS:**
```bash
cd /path/to/SAVO/apps/mobile
flutter run --release
# OR build for TestFlight
flutter build ios --release
```

### Test Ingredients (Recommended)

Prepare these ingredients for comprehensive testing:

**Clear Labels (High Success Rate):**
- ✅ Milk carton (with "1 liter" or "1000 ml" label)
- ✅ Rice bag (with "500g" label)
- ✅ Canned beans (with "400g" label)
- ✅ Pasta package (with "500g" label)
- ✅ Oil bottle (with "750ml" label)

**Items Without Labels (Manual Entry Test):**
- ✅ 3-4 loose tomatoes
- ✅ 2-3 onions
- ✅ 5-6 eggs
- ✅ Fresh garlic cloves

**Edge Cases (Robustness Test):**
- ⚠️ Partially obscured label
- ⚠️ Non-English label
- ⚠️ Handwritten label
- ⚠️ Very small label (<1cm text)

---

## 🎯 Test Cases - Complete E2E Flows

### Test 1: Image Scanning with OCR Quantity Detection (CRITICAL)

**Objective:** Verify Vision API correctly detects ingredients AND quantities from package labels

**Steps:**
1. Launch app → Navigate to Inventory screen
2. Tap camera/scan button (white + FAB)
3. Point camera at milk carton with visible "1000 ml" label
4. Ensure good lighting and label is in focus
5. Tap capture button

**Expected Results:**
- ✅ Image uploads successfully (<5 seconds)
- ✅ Confirmation screen appears with detected ingredients
- ✅ "Milk" appears with HIGH confidence (green badge)
- ✅ Quantity picker shows "1000 ml" pre-filled
- ✅ "Auto-detected" blue badge visible
- ✅ +/- buttons functional
- ✅ Unit dropdown shows ml, liters, cups, fl oz

**Pass Criteria:**
- Ingredient name correct: ✅ / ❌
- Quantity detected: ✅ / ❌
- Unit detected: ✅ / ❌
- Confidence level: HIGH / MEDIUM / LOW

**If Failed:**
- Screenshot error message
- Note lighting conditions
- Try with different angle/distance
- Check internet connection

---

### Test 2: Multiple Ingredients Scanning (ROBUSTNESS)

**Objective:** Verify system handles multiple items in one photo

**Steps:**
1. Arrange 3-4 items with visible labels (milk, rice, pasta, oil)
2. Take photo with all items visible
3. Wait for analysis

**Expected Results:**
- ✅ All 3-4 ingredients detected
- ✅ Each has separate quantity picker
- ✅ Quantities correctly extracted from labels
- ✅ Confidence badges appropriate (mostly HIGH)

**Robustness Check:**
- Items partially overlapping → Should still detect
- Mixed lighting → Should still work
- Different label sizes → Should handle all

**Pass Criteria:**
- All items detected: ✅ / ❌
- Quantities correct: ✅ / ❌
- No false positives: ✅ / ❌

---

### Test 3: Low Confidence Handling (USER TRUST)

**Objective:** Verify system provides alternatives when uncertain

**Steps:**
1. Take photo of ambiguous item (e.g., bell pepper that could be red/green/yellow)
2. Wait for analysis

**Expected Results:**
- ✅ Item detected with MEDIUM or LOW confidence (orange/red badge)
- ✅ "Please Review" or "Uncertain" section header
- ✅ Close alternatives shown as chips (e.g., "red_pepper", "green_pepper")
- ✅ User can select correct one
- ✅ Quantity picker still functional

**User Confidence Check:**
- Does user understand why it's uncertain? ✅ / ❌
- Are alternatives helpful? ✅ / ❌
- Can user easily correct? ✅ / ❌

---

### Test 4: Quantity Confirmation and Override (CRITICAL)

**Objective:** Verify user can adjust OCR-detected quantities

**Steps:**
1. Scan item with detected quantity (e.g., "500g rice")
2. Note auto-detected value
3. Tap - button 3 times
4. Tap + button 2 times
5. Change unit from grams to kg
6. Manually type "0.6" in text field
7. Tap "Confirm" button

**Expected Results:**
- ✅ - button decrements (500 → 499.5 → 499 → ...)
- ✅ + button increments properly
- ✅ Unit dropdown changes unit
- ✅ Manual text entry works
- ✅ Invalid input rejected (e.g., "abc")
- ✅ Confirm button stores final value
- ✅ Item appears in pantry with correct quantity

**Pass Criteria:**
- All controls responsive: ✅ / ❌
- Final value correct: ✅ / ❌
- Stored in database: ✅ / ❌

---

### Test 5: Manual Entry Flow (SPEED TEST)

**Objective:** Verify manual entry is faster than scanning for known items

**Steps:**
1. Navigate to Inventory screen
2. Tap green edit FAB (manual entry)
3. Type "tom" in search field
4. Select "tomato" from autocomplete
5. Note unit auto-suggested "pieces"
6. Set quantity to 3 using +/- buttons
7. Tap "Add to Pantry"
8. **Time this entire flow** ⏱️

**Expected Results:**
- ✅ Autocomplete filters instantly (<50ms)
- ✅ "tomato" appears in suggestions
- ✅ Unit auto-suggests "pieces" (not ml)
- ✅ Quantity picker functional
- ✅ Success snackbar appears
- ✅ Auto-navigates back to inventory
- ✅ Item appears in pantry immediately
- ✅ **Total time < 10 seconds**

**Speed Comparison:**
- Manual entry time: ______ seconds
- Scanning time (same item): ______ seconds
- Manual is faster? ✅ / ❌

---

### Test 6: Quick-Add Chips (UX TEST)

**Objective:** Verify quick-add is even faster

**Steps:**
1. Open manual entry screen
2. Scroll to "Quick Add Common Items" section
3. Tap "onion" chip
4. Note quantity auto-sets to 1 pieces
5. Adjust to 2
6. Tap "Add to Pantry"
7. **Time this flow** ⏱️

**Expected Results:**
- ✅ Name pre-filled
- ✅ Smart unit selected
- ✅ **Total time < 5 seconds**

**UX Check:**
- Chips visible without scrolling? ✅ / ❌
- Obvious they're tappable? ✅ / ❌
- Faster than typing? ✅ / ❌

---

### Test 7: Serving Calculator Sufficiency Check (HIGH VALUE)

**Objective:** Verify serving calculator provides actionable results

**Steps:**
1. Ensure pantry has some ingredients (from Tests 1-6)
2. Navigate to Recipes → Select any recipe
3. Note default serving size (usually 4)
4. Change to 8 people using +/- buttons
5. Tap "Check if I have enough" button
6. Wait for results (<500ms)

**Expected Results:**
- ✅ Loading indicator appears briefly
- ✅ Result card appears with color-coded status:
  - Green = Sufficient ✅
  - Orange = Missing items ⚠️
- ✅ If missing items:
  - List shows "Missing Ingredients:"
  - Each item shows: name + needed quantity + unit
  - Shopping list appears below
  - Practical rounded quantities (250g not 237g)
- ✅ Copy button functional

**Pass Criteria:**
- Results accurate: ✅ / ❌
- Response time < 1 second: ✅ / ❌
- UI clear and actionable: ✅ / ❌

---

### Test 8: Shopping List Copy (MINOR FIX)

**Objective:** Verify clipboard copy works

**Steps:**
1. From Test 7, with missing ingredients showing
2. Tap "Copy" button on shopping list
3. Open Notes app (or any text field)
4. Long-press → Paste

**Expected Results:**
- ✅ Success snackbar: "Shopping list copied to clipboard!"
- ✅ Pasted text contains:
  ```
  250 grams chicken
  150 grams rice
  100 ml oil
  ```
- ✅ Format is clean and readable

**Pass Criteria:**
- Clipboard contains list: ✅ / ❌
- Format is usable: ✅ / ❌

---

### Test 9: Error Handling and Robustness (FOUNDATIONAL)

**Objective:** Verify app gracefully handles edge cases

#### 9A: No Internet Connection
**Steps:**
1. Enable Airplane Mode
2. Try to scan ingredient
3. Note error message

**Expected Result:**
- ✅ Clear error: "No internet connection. Please check your network and try again."
- ✅ No crash
- ✅ User can retry after reconnecting

#### 9B: Timeout Scenario
**Steps:**
1. Use very slow network (3G or throttled WiFi)
2. Scan ingredient
3. Wait for timeout

**Expected Result:**
- ✅ Request times out after 30 seconds
- ✅ Shows: "Request timed out. Please check your internet connection and try again."
- ✅ Option to retry

#### 9C: Large Image File
**Steps:**
1. Try to upload very high-res image (>10MB)
2. Note response

**Expected Result:**
- ✅ Error: "Image file is too large (>10MB). Please try taking a smaller photo."
- ✅ Suggests solution

#### 9D: Server Error (500)
**Steps:**
1. (Requires backend down or mock error)
2. Try to scan

**Expected Result:**
- ✅ Automatic retry (up to 2 times)
- ✅ Clear error message after retries exhausted

#### 9E: Session Expired
**Steps:**
1. Logout → Login → Leave app idle for 24 hours
2. Try to scan

**Expected Result:**
- ✅ Error: "Session expired. Please log in again."
- ✅ Redirects to login screen

**Pass Criteria:**
- All errors handled gracefully: ✅ / ❌
- No crashes: ✅ / ❌
- Clear user guidance: ✅ / ❌

---

### Test 10: Edge Cases for Vision Scanning (ROBUSTNESS)

**Objective:** Verify system handles difficult scenarios

#### 10A: Poor Lighting
**Steps:**
1. Take photo in dim lighting
2. Wait for analysis

**Expected Result:**
- ✅ Detection still works (may be MEDIUM confidence)
- ✅ OR clear message: "Image too dark, please retry with better lighting"

#### 10B: Blurry Image
**Steps:**
1. Move camera while capturing (intentional blur)
2. Wait for analysis

**Expected Result:**
- ✅ Detection attempts
- ✅ May show LOW confidence with alternatives
- ✅ OR message: "Image unclear, please retry"

#### 10C: No Ingredients Visible
**Steps:**
1. Take photo of empty table
2. Wait for analysis

**Expected Result:**
- ✅ Message: "No ingredients detected. Please try again with items visible."
- ✅ Suggests retaking photo

#### 10D: Non-Food Items
**Steps:**
1. Take photo of phone/book/non-food item
2. Wait for analysis

**Expected Result:**
- ✅ Either no detection (expected)
- ✅ OR detects with LOW confidence (acceptable)
- ✅ User can reject and retry

#### 10E: Handwritten Labels
**Steps:**
1. Scan item with handwritten label
2. Wait for analysis

**Expected Result:**
- ✅ May not detect quantity (expected)
- ✅ User can manually enter via quantity picker
- ✅ Ingredient name might still detect

---

## 📊 Performance Benchmarks

Track these metrics during testing:

| Operation | Target | Actual | Pass? |
|-----------|--------|--------|-------|
| Image scan + analysis | < 5 sec | _____ | ✅ / ❌ |
| Autocomplete filter | < 50 ms | _____ | ✅ / ❌ |
| Manual entry submit | < 300 ms | _____ | ✅ / ❌ |
| Sufficiency check API | < 500 ms | _____ | ✅ / ❌ |
| Recipe detail load | < 200 ms | _____ | ✅ / ❌ |
| Clipboard copy | Instant | _____ | ✅ / ❌ |

---

## 🎯 Confidence & Trust Indicators

Rate these on scale of 1-5 (5 = Excellent):

### User Confidence
- **Ingredient detection accuracy:** ___/5
- **Quantity detection accuracy:** ___/5
- **Confidence badges helpful:** ___/5
- **Alternatives useful when uncertain:** ___/5
- **Error messages clear and actionable:** ___/5

### System Robustness
- **Handles poor lighting:** ___/5
- **Handles blurry images:** ___/5
- **Handles network issues gracefully:** ___/5
- **Retry logic works:** ___/5
- **No crashes observed:** ✅ / ❌

### User Experience
- **Scanning is intuitive:** ___/5
- **Manual entry is fast:** ___/5
- **Quantity pickers easy to use:** ___/5
- **Serving calculator valuable:** ___/5
- **Overall trust in system:** ___/5

---

## 🐛 Bug Report Template

Use this format to report issues:

```
### Bug #___: [Brief Description]

**Severity:** Critical / High / Medium / Low
**Device:** Android [version] / iOS [version]
**Steps to Reproduce:**
1. 
2. 
3. 

**Expected Result:**


**Actual Result:**


**Screenshot:** [Attach if available]

**Frequency:** Always / Sometimes / Rare

**Workaround:** [If known]

**Notes:**
```

---

## ✅ Success Criteria

### Critical (Must Pass)
- [ ] Image scanning works with clear labels (>90% accuracy)
- [ ] Quantity detection works with visible labels (>85% accuracy)
- [ ] Manual entry faster than scanning (<10 seconds)
- [ ] Serving calculator returns accurate results
- [ ] No crashes during normal operation
- [ ] Error handling graceful and informative

### Important (Should Pass)
- [ ] Multiple ingredients detected in one photo
- [ ] Low confidence items show alternatives
- [ ] User can override all auto-detected values
- [ ] Quick-add chips work as expected
- [ ] Clipboard copy functional
- [ ] Performance meets benchmarks

### Nice-to-Have (Good to Pass)
- [ ] Handles poor lighting reasonably
- [ ] Blurry images give helpful feedback
- [ ] Non-food items don't cause false positives
- [ ] Handwritten labels degrade gracefully
- [ ] Network issues auto-retry

---

## 📝 Testing Checklist

Complete this checklist during testing:

### Pre-Test Setup
- [ ] Device connected and recognized
- [ ] App installed in release mode
- [ ] Backend API accessible
- [ ] Test ingredients prepared
- [ ] Good lighting available

### Core Functionality
- [ ] Test 1: Single ingredient scan ✅ / ❌
- [ ] Test 2: Multiple ingredients scan ✅ / ❌
- [ ] Test 3: Low confidence handling ✅ / ❌
- [ ] Test 4: Quantity override ✅ / ❌
- [ ] Test 5: Manual entry ✅ / ❌
- [ ] Test 6: Quick-add chips ✅ / ❌
- [ ] Test 7: Serving calculator ✅ / ❌
- [ ] Test 8: Clipboard copy ✅ / ❌

### Robustness
- [ ] Test 9A: No internet ✅ / ❌
- [ ] Test 9B: Timeout ✅ / ❌
- [ ] Test 9C: Large file ✅ / ❌
- [ ] Test 9D: Server error ✅ / ❌
- [ ] Test 9E: Session expired ✅ / ❌

### Edge Cases
- [ ] Test 10A: Poor lighting ✅ / ❌
- [ ] Test 10B: Blurry image ✅ / ❌
- [ ] Test 10C: No ingredients ✅ / ❌
- [ ] Test 10D: Non-food items ✅ / ❌
- [ ] Test 10E: Handwritten labels ✅ / ❌

### Performance
- [ ] All benchmarks met ✅ / ❌
- [ ] No UI lag observed ✅ / ❌
- [ ] Memory usage acceptable ✅ / ❌

### User Experience
- [ ] Confidence ratings completed
- [ ] Bug reports filed (if any)
- [ ] Screenshots captured
- [ ] Tester feedback collected

---

## 📸 Screenshot Checklist

Capture these screenshots during testing:

1. **Successful scan** - High confidence with quantity detected
2. **Multiple ingredients** - 3-4 items in one photo
3. **Low confidence** - Showing alternatives
4. **Quantity picker** - With "Auto-detected" badge
5. **Manual entry** - Autocomplete in action
6. **Quick-add chips** - Visible and tappable
7. **Serving calculator** - Showing missing ingredients
8. **Shopping list** - With copy button
9. **Error handling** - Clear error message
10. **Edge case** - Poor lighting or blurry image

---

## 🚀 Post-Testing Actions

After completing all tests:

1. **Summarize Results:**
   - Overall pass rate: ____%
   - Critical bugs found: ___
   - Performance issues: ___
   - User confidence score: ___/5

2. **Prioritize Fixes:**
   - P0 (Critical): ___
   - P1 (High): ___
   - P2 (Medium): ___
   - P3 (Low): ___

3. **Next Steps:**
   - [ ] Fix critical bugs
   - [ ] Optimize slow operations
   - [ ] Improve error messages
   - [ ] Enhance edge case handling
   - [ ] Re-test failed cases
   - [ ] Deploy to beta testers

4. **Beta Deployment Decision:**
   - Ready for beta? ✅ / ❌
   - Blockers: _________________
   - Target beta date: _________

---

## 📞 Support During Testing

If you encounter issues:

1. **Check logs:**
   ```bash
   flutter logs --verbose
   ```

2. **Backend logs:**
   Check Render dashboard for API errors

3. **Common fixes:**
   - Clear app data and retry
   - Restart app
   - Check API_BASE_URL in environment
   - Verify backend is running

4. **Get help:**
   - Document issue with screenshots
   - Note device model and OS version
   - Capture console output
   - Check similar issues in docs

---

**Testing Goal:** Ensure the scanning system is **rock-solid** and gives users **confidence and trust** in the foundational ingredient detection feature.

**Success = Users feel:** "This just works. I can trust it. If something's unclear, I have clear options."

---

**Happy Testing! 🧪🎉**
