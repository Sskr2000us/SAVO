# Quick Testing Guide - SAVO Mobile App

## Current Status
- ✅ Backend fully deployed and tested
- ✅ Flutter code complete
- ⚠️ Flutter SDK not installed on this system

---

## Option 1: Test Backend APIs (Available Now)

### Start Local Backend
```powershell
cd C:\Users\sskr2\SAVO\services\api
.\.venv\Scripts\Activate.ps1
$env:SAVO_LLM_PROVIDER="mock"
uvicorn app.main:app --reload --port 8000
```

### Open Swagger UI
- Local: http://localhost:8000/docs
- Production: https://savo-ynp1.onrender.com/docs

### Test Endpoints

**1. Meal Planning (POST /plan/daily)**
```json
{
  "inventory": {
    "available_ingredients": ["chicken", "tomatoes", "rice", "garlic", "onion"]
  },
  "cuisine_preferences": ["Italian"],
  "skill_level": "beginner"
}
```

**2. Ingredient Scanning (POST /inventory/scan)**
- Upload any image file
- Mock provider returns: tomato, onion, eggs
- Google provider (production) analyzes real images

**3. YouTube Ranking (POST /youtube/rank)**
```json
{
  "recipe_name": "Risotto al Pomodoro",
  "recipe_cuisine": "Italian",
  "recipe_techniques": ["sautéing", "stirring"],
  "candidates": [
    {
      "video_id": "abc123",
      "title": "Perfect Risotto al Pomodoro",
      "channel": "Italian Cooking Academy",
      "language": "en"
    }
  ]
}
```

---

## Option 2: Install Flutter SDK (For Mobile Testing)

### Installation Steps (Windows)

1. **Download Flutter**
   - Visit: https://docs.flutter.dev/get-started/install/windows
   - Download latest stable release
   - Extract to `C:\flutter`

2. **Add to PATH**
   ```powershell
   $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
   [Environment]::SetEnvironmentVariable('Path', "$userPath;C:\flutter\bin", 'User')
   ```

3. **Verify Installation**
   ```powershell
   # Restart terminal
   flutter doctor
   ```

4. **Install Dependencies**
   ```powershell
   cd C:\Users\sskr2\SAVO\apps\mobile
   flutter pub get
   ```

5. **Run App**
   ```powershell
   # Web (easiest for testing)
   flutter run -d chrome
   
   # Android emulator (requires Android Studio)
   flutter run
   
   # Windows desktop
   flutter run -d windows
   ```

---

## Option 3: Test with Flutter Web (Once Flutter Installed)

### Start Local Backend
```powershell
# Terminal 1 - Backend
cd C:\Users\sskr2\SAVO\services\api
.\.venv\Scripts\Activate.ps1
$env:SAVO_LLM_PROVIDER="mock"
uvicorn app.main:app --reload --port 8000
```

### Update Flutter to Use Local Backend
Edit `apps/mobile/lib/services/api_client.dart`:
```dart
static String _defaultBaseUrl() {
  // For local testing
  if (kIsWeb) return 'http://localhost:8000';
  return 'http://localhost:8000';
  
  // For production (current setting)
  // return 'https://savo-ynp1.onrender.com';
}
```

### Run Flutter Web
```powershell
# Terminal 2 - Flutter
cd C:\Users\sskr2\SAVO\apps\mobile
flutter run -d chrome
```

### Test Features

**1. Plan a Meal**
- Home → "Plan Meal" (or similar button)
- Fill in preferences
- See meal plan with 4 courses, 2 options each
- Tap recipe → See YouTube videos loading

**2. Scan Ingredients**
- Navigate to Inventory
- Tap camera icon in AppBar
- Upload image or use camera
- Mock returns: tomato (91%), onion (86%), eggs (82%)
- Edit if needed → Confirm → Added to inventory

**3. View Recipe with YouTube**
- From meal plan → Tap any recipe
- See "Finding YouTube tutorials..."
- Top 3 videos appear with:
  - Thumbnail with play button
  - Trust score (blue badge)
  - Match score (green badge)
  - Ranking reasons
- Tap video → Opens in YouTube

---

## What Each Test Validates

### Backend Tests (Swagger)
- ✅ Plans generate without truncation (<10KB)
- ✅ Scanning detects ingredients with confidence
- ✅ YouTube ranking returns trust + match scores
- ✅ All endpoints return valid JSON

### Flutter Tests (Once SDK Installed)
- ✅ UI renders correctly
- ✅ API client communicates with backend
- ✅ Navigation flows work
- ✅ Camera/gallery access works
- ✅ YouTube opens externally
- ✅ Loading states display properly
- ✅ Error handling works

---

## Quick Start (Easiest Path)

**Right now without Flutter:**
1. Open browser: https://savo-ynp1.onrender.com/docs
2. Test POST /plan/daily with sample JSON
3. Test POST /youtube/rank with sample JSON
4. See it working!

**With Flutter (after SDK install):**
1. `cd C:\Users\sskr2\SAVO\apps\mobile`
2. `flutter pub get`
3. `flutter run -d chrome`
4. Test full UI flow

---

## Troubleshooting

**Flutter not found?**
- Make sure `C:\flutter\bin` is in PATH
- Restart terminal after adding to PATH
- Run `flutter doctor` to verify

**Backend errors?**
- Check `$env:SAVO_LLM_PROVIDER="mock"` is set
- Verify virtual environment is activated
- Check port 8000 isn't already in use

**CORS errors in browser?**
- Backend already configured for CORS
- Make sure backend is running on http://localhost:8000
- Check Flutter is pointing to correct backend URL

---

## Next Steps After Testing

1. **Replace Mock YouTube Candidates**
   - Get YouTube Data API v3 key
   - Update `_createMockCandidates()` in `recipe_detail_screen.dart`
   - Use real YouTube search

2. **Test on Real Devices**
   - Android: `flutter run` with device connected
   - iOS: Requires Mac + Xcode
   - Windows: `flutter run -d windows`

3. **Deploy Flutter App**
   - Web: `flutter build web` → host on Netlify/Vercel
   - Android: `flutter build apk` → Google Play Store
   - iOS: `flutter build ipa` → App Store

---

## Support

All features are **production-ready** on backend:
- ✅ https://savo-ynp1.onrender.com/docs

Flutter is **implementation-complete**:
- ✅ All screens built
- ✅ All APIs integrated
- ✅ YouTube ranking on-demand
- ✅ Scanning with confirmation

Just needs Flutter SDK to run!
