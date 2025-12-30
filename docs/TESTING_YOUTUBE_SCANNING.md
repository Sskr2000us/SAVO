# Testing Guide: YouTube & Scanning Features

## ✅ Completed Backend Features

### 1. YouTube Ranking (`POST /youtube/rank`)

**Purpose**: On-demand YouTube video ranking for specific recipes (keeps plans lean, fetches YT data only when user opens a recipe)

**Endpoint**: `POST /youtube/rank`

**Request Example**:
```json
{
  "recipe_name": "Risotto al Pomodoro",
  "recipe_cuisine": "Italian",
  "recipe_techniques": ["sautéing", "risotto technique", "stirring"],
  "candidates": [
    {
      "video_id": "abc123",
      "title": "Perfect Risotto al Pomodoro - Italian Chef",
      "channel": "Italian Cooking Academy",
      "language": "en",
      "transcript": "Today we make authentic risotto with tomatoes...",
      "metadata": {"duration": "12:45", "views": 500000}
    }
  ],
  "output_language": "en"
}
```

**Response Example**:
```json
{
  "ranked_videos": [
    {
      "video_id": "abc123",
      "title": "Perfect Risotto al Pomodoro - Italian Chef",
      "channel": "Italian Cooking Academy",
      "trust_score": 0.9,
      "match_score": 0.85,
      "reasons": ["High quality tutorial", "Authentic Italian technique"]
    }
  ]
}
```

**Local Test**:
```bash
cd services/api
.\.venv\Scripts\Activate.ps1
$env:SAVO_LLM_PROVIDER="mock"
python test_youtube_rank.py
```

**Mock Provider Behavior**:
- Returns deterministic ranked video for testing UI
- Real provider (Google) will analyze transcripts and rank by trust/match scores

---

### 2. Ingredient Scanning (`POST /inventory/scan`)

**Purpose**: Camera-based ingredient detection with user confirmation (non-negotiable trust step)

**Endpoint**: `POST /inventory/scan` (multipart/form-data)

**Request**:
- `image`: Image file (JPEG/PNG, max 5MB)
- `storage_hint`: Optional ("pantry" | "refrigerator" | "freezer")

**Response Example**:
```json
{
  "status": "ok",
  "scanned_items": [
    {
      "ingredient": "tomato",
      "quantity_estimate": "4 pcs",
      "confidence": 0.91,
      "storage_hint": "refrigerator"
    },
    {
      "ingredient": "onion",
      "quantity_estimate": "2 pcs",
      "confidence": 0.86,
      "storage_hint": "pantry"
    }
  ],
  "error_message": null
}
```

**Local Test**:
```bash
cd services/api
.\.venv\Scripts\Activate.ps1
$env:SAVO_LLM_PROVIDER="mock"
python test_scan_asgi.py
```

**Mock Provider Behavior**:
- Returns tomato, onion, eggs with confidence scores
- Real provider (Google) requires `SAVO_LLM_PROVIDER=google` with Gemini API key

---

## 🎯 Flutter Integration (When Flutter is Installed)

### Install Dependencies
```bash
cd apps/mobile
flutter pub get
```

### Test Scanning Flow

1. **Start local backend** (mock provider):
   ```bash
   cd services/api
   .\.venv\Scripts\Activate.ps1
   $env:SAVO_LLM_PROVIDER="mock"
   uvicorn app.main:app --reload --port 8000
   ```

2. **Update Flutter to use local backend** (if testing locally):
   ```dart
   // apps/mobile/lib/services/api_client.dart
   static String _defaultBaseUrl() {
     if (kIsWeb) return 'http://localhost:8000';
     return 'http://10.0.2.2:8000'; // Android emulator
   }
   ```

3. **Run Flutter app**:
   ```bash
   cd apps/mobile
   flutter run -d chrome  # Web
   # OR
   flutter run            # Android/iOS
   ```

4. **Test scanning**:
   - Open app → Navigate to "Inventory" screen
   - Tap camera icon in AppBar
   - Choose "Take Photo" or "Pick From Gallery"
   - Mock backend returns: tomato (91%), onion (86%), eggs (82%)
   - Edit ingredients/quantities if needed
   - Tap "Confirm & Add to Inventory"
   - Items normalized and added to inventory

### Production Scanning (with Gemini)

1. Set environment variable on Render dashboard:
   - `SAVO_LLM_PROVIDER=google`
   - `GOOGLE_API_KEY=your_gemini_api_key`

2. Flutter app automatically uses production backend:
   ```
   https://savo-ynp1.onrender.com
   ```

3. Gemini multimodal will:
   - Analyze uploaded image
   - Detect visible ingredients
   - Return confidence scores
   - Suggest storage hints

---

## 📋 Next Integration Steps

### For Recipe Detail Screen (YouTube Integration)

When user opens a recipe from the plan:

1. **Extract recipe context**:
   ```dart
   final recipeName = recipe['recipe_name']['en'];
   final cuisine = recipe['cuisine'];
   final techniques = recipe['steps']
       .map((s) => extractTechniquesFromStep(s))
       .expand((t) => t)
       .toList();
   ```

2. **Fetch YouTube candidates** (external service or YouTube API):
   ```dart
   final candidates = await fetchYouTubeCandidates(
     query: '$recipeName $cuisine recipe',
     maxResults: 5,
   );
   ```

3. **Rank candidates**:
   ```dart
   final response = await apiClient.post('/youtube/rank', {
     'recipe_name': recipeName,
     'recipe_cuisine': cuisine,
     'recipe_techniques': techniques,
     'candidates': candidates,
     'output_language': 'en',
   });
   
   final rankedVideos = response['ranked_videos'];
   ```

4. **Display ranked videos** in recipe UI:
   - Show top 3 videos with trust/match scores
   - Embed YouTube player or link to YouTube
   - Show reasons for ranking

### Benefits of Lazy YouTube Loading

- **Plan responses stay <10KB** (no truncation)
- **Faster plan generation** (30s → 10s)
- **Personalized video ranking** based on user's recipe choice
- **Scalable** (only fetch videos for recipes user actually views)

---

## 🧪 Production Testing Checklist

- [x] YouTube ranking endpoint works with mock provider
- [x] Scanning endpoint works with mock provider
- [x] Plan generation returns valid JSON without truncation
- [ ] Flutter app receives and displays scanned ingredients
- [ ] Scanning works with Google provider in production
- [ ] Recipe detail screen calls /youtube/rank on-demand
- [ ] YouTube videos ranked and displayed in recipe UI
- [ ] End-to-end: Scan → Plan → View Recipe → Watch YouTube

---

## 🚀 Deployment Status

**Backend (Render)**: ✅ Deployed
- `/youtube/rank` available at `https://savo-ynp1.onrender.com/youtube/rank`
- `/inventory/scan` available at `https://savo-ynp1.onrender.com/inventory/scan`
- `/plan/daily` returns compact plans without truncation

**Flutter App**: Ready for integration
- `ScanIngredientsScreen` implemented
- `image_picker` dependency added to pubspec.yaml
- Camera icon wired in InventoryScreen
- Multipart upload helper ready

**Next**: Install Flutter SDK and test scanning flow end-to-end
