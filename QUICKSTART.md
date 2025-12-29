# SAVO Quick Start Guide

## Prerequisites
- Python 3.12
- Flutter SDK 3.10.4+
- Android Studio / Xcode (for emulators)

## Backend Setup

### 1. Navigate to API directory
```powershell
cd services\api
```

### 2. Create and activate virtual environment
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies
```powershell
pip install -r requirements.txt
```

### 4. Configure LLM Provider

**Option A: Mock Mode (Default - No API Key Required)**
```powershell
$env:SAVO_LLM_PROVIDER="mock"
```

**Option B: OpenAI (Requires API Key)**
```powershell
# Copy example env file and add your API key
Copy-Item .env.example .env
# Edit .env and set:
# SAVO_LLM_PROVIDER=openai
# OPENAI_API_KEY=sk-your-actual-key-here

$env:SAVO_LLM_PROVIDER="openai"
$env:OPENAI_API_KEY="sk-your-key-here"
```

**Option C: Anthropic Claude (Requires API Key)**
```powershell
$env:SAVO_LLM_PROVIDER="anthropic"
$env:ANTHROPIC_API_KEY="sk-ant-your-key-here"
```

> 📖 See [docs/LLM_INTEGRATION.md](docs/LLM_INTEGRATION.md) for detailed setup guide

### 5. Start backend
```powershell
uvicorn app.main:app --reload --port 8000
```

The backend should now be running at `http://localhost:8000`

### 6. Verify backend health
Open browser to: `http://localhost:8000/docs`

You should see the FastAPI Swagger documentation.

## Mobile App Setup

### 1. Navigate to mobile directory (in a new terminal)
```powershell
cd apps\mobile
```

### 2. Install Flutter dependencies
```powershell
flutter pub get
```

### 3. Verify Flutter setup
```powershell
flutter doctor
```

### 4. Run the app

**Android Emulator:**
```powershell
flutter run
```

**iOS Simulator (Mac only):**
```powershell
flutter run
```

**Web:**
```powershell
flutter run -d chrome
```

## First Use

### 1. Configure Settings
- Tap the **Settings** tab (bottom right)
- Review household profile, dietary restrictions
- Set measurement system (metric/imperial)
- Verify timezone

### 2. Add Inventory Items
- From Settings → **Manage Inventory**
- Tap the **+** button
- Add items with:
  - Name (e.g., "Chicken Breast")
  - Quantity (e.g., 2)
  - Unit (e.g., "pounds")
  - Storage (refrigerator/freezer/pantry)
- Add some items with low freshness days (≤3) to test expiring indicators

### 3. Try Daily Planning
- Go to **Home** tab
- Tap **Daily Menu**
- Wait for mock LLM to generate plan
- Browse recipe options
- Tap a recipe to view details
- Tap **Start Cook Mode**

### 4. Test Weekly Planning
- From Home → **Weekly Planner**
- Select start date
- Choose number of days (1-4)
- Tap **Generate Weekly Plan**
- View per-day menus

### 5. Test Party Planning
- From Home → **Party Menu**
- Adjust guest count slider
- Set age groups using +/- buttons
- Ensure age groups sum to guest count (green checkmark)
- Tap **Generate Party Menu**

### 6. Test Cook Mode
- Open any recipe
- Tap **Start Cook Mode**
- Navigate through steps with Previous/Next
- For timed steps:
  - Tap **Start Timer**
  - Use **+1 Min** to extend
- Complete recipe to save to history

### 7. Check Leftovers
- Add inventory items with state="leftover"
- Go to **Leftovers** tab
- See filtered list of leftover items

## API Endpoints Available

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Backend health check |
| `/config` | GET | Get app configuration |
| `/config` | PUT | Update configuration |
| `/inventory` | GET | List all inventory items |
| `/inventory` | POST | Add new item |
| `/inventory/{id}` | PUT | Update item |
| `/inventory/{id}` | DELETE | Delete item |
| `/inventory/normalize` | POST | Normalize ingredients |
| `/cuisines` | GET | List available cuisines |
| `/plan/daily` | POST | Generate daily menu |
| `/plan/weekly` | POST | Generate weekly plan |
| `/plan/party` | POST | Generate party menu |
| `/history/recipes` | POST | Record recipe completion |
| `/youtube/rank` | POST | Rank YouTube videos |

## Testing Mock Responses

The mock LLM provider returns structured JSON responses that match the schemas. To test:

1. **Daily Planning**: Returns 1 menu with 3 courses, 2-3 recipes each
2. **Weekly Planning**: Returns N menus (based on num_days), each with 3 courses
3. **Party Planning**: Returns party menu scaled to guest count

## Troubleshooting

### Backend not reachable from Android emulator
- Ensure backend uses port 8000
- Android emulator uses `10.0.2.2` to reach host's localhost
- Already configured in `api_client.dart`

### Flutter dependencies not installing
```powershell
flutter clean
flutter pub get
```

### Backend module not found errors
```powershell
cd services\api
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### CORS errors on web
- CORS is already configured in `services/api/app/main.py`
- Allows all origins for development

### Mock LLM not returning data
- Check `SAVO_LLM_PROVIDER` environment variable is set to "mock"
- Check backend logs in terminal

## Development Workflow

### Backend Development
1. Make changes to Python code
2. FastAPI auto-reloads (uvicorn --reload)
3. Test via Swagger UI: `http://localhost:8000/docs`

### Mobile Development
1. Make changes to Dart code
2. Hot reload: Press `r` in terminal or save in IDE
3. Hot restart: Press `R` in terminal
4. Full rebuild: `flutter run` again

## Architecture Overview

```
SAVO/
├── services/api/              # FastAPI backend
│   ├── app/
│   │   ├── main.py           # FastAPI app + CORS
│   │   ├── models/           # Pydantic DTOs
│   │   ├── api/routes/       # Endpoint handlers
│   │   ├── core/             # Orchestration, storage, LLM
│   │   └── ...
│   └── requirements.txt
│
├── apps/mobile/              # Flutter app
│   ├── lib/
│   │   ├── main.dart         # Entry point + navigation
│   │   ├── models/           # Dart models
│   │   ├── services/         # API client
│   │   └── screens/          # UI screens
│   └── pubspec.yaml
│
└── docs/                     # Documentation
    ├── ACTION_ITEMS_END_TO_END.md
    ├── FLUTTER_IMPLEMENTATION.md
    ├── Build_Plan.md
    ├── PRD.md
    └── spec/                 # JSON specs
```

## Next Steps

1. **Add Real LLM Integration**:
   - Set `SAVO_LLM_PROVIDER=openai` or `anthropic`
   - Add API keys to `.env`
   - Test with real AI responses

2. **Add Persistence**:
   - Set up PostgreSQL
   - Run migrations
   - Update storage backend

3. **Add Images**:
   - Replace placeholder icons with recipe images
   - Add cuisine flags/icons

4. **Deploy**:
   - Backend: Docker + Cloud Run / Heroku
   - Mobile: Build APK/IPA and distribute

## Support

For issues or questions:
1. Check logs in backend terminal
2. Check Flutter debug console
3. Review [FLUTTER_IMPLEMENTATION.md](FLUTTER_IMPLEMENTATION.md)
4. Review [ACTION_ITEMS_END_TO_END.md](ACTION_ITEMS_END_TO_END.md)

## Environment Variables

### Backend (.env)
```bash
SAVO_LLM_PROVIDER=mock           # or 'openai', 'anthropic'
SAVO_PROMPT_PACK_PATH=docs/spec/prompt-pack.gpt-5.2.json
OPENAI_API_KEY=your-key          # if using OpenAI
ANTHROPIC_API_KEY=your-key       # if using Anthropic
DATABASE_URL=postgresql://...    # if using real DB
```

### Mobile
- No environment variables needed for MVP
- API base URL is auto-detected based on platform
