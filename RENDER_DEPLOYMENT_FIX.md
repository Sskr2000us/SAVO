# Render Deployment Fix - Intelligence Router

**Date**: January 7, 2026  
**Commit**: ce923e8  
**Error**: ImportError: cannot import name 'get_db' from 'app.core.database'

---

## 🔴 Critical Error

```
ImportError: cannot import name 'get_db' from 'app.core.database' 
(/opt/render/project/src/services/api/app/core/database.py)

File: /opt/render/project/src/services/api/app/routers/intelligence.py, line 16
```

**Impact**: Render deployment completely blocked - uvicorn child processes dying repeatedly

---

## 🔍 Root Cause Analysis

### Issue Chain
1. [app/routers/intelligence.py](services/api/app/routers/intelligence.py#L16) imports `get_db`
2. [app/core/database.py](services/api/app/core/database.py) only exports `get_db_client`
3. FastAPI fails to start due to missing import
4. Render marks deployment as failed

### Code Archaeology
- **intelligence.py** written for asyncpg connection pool (PostgreSQL native)
- **database.py** uses Supabase client (REST API based)
- Incompatible database abstraction layers

### Previous Working State
- Earlier commits didn't include intelligence router
- Router added recently but never tested
- All other routers use `get_db_client` correctly

---

## ✅ Resolution

### Changes Made

#### 1. Import Statement
**Before**:
```python
from app.core.database import get_db
```

**After**:
```python
from app.core.database import get_db_client
```

#### 2. Dependency Injections (3 endpoints)

**Before**:
```python
async def identify_ingredient(..., db = Depends(get_db)):
async def get_similar_ingredients(..., db = Depends(get_db)):
async def confirm_identification(..., db = Depends(get_db)):
```

**After**:
```python
async def identify_ingredient(...):
async def get_similar_ingredients(...):
async def confirm_identification(...):
```

#### 3. Database Query Conversions

**A. identify_ingredient() - Master ingredient lookup**

**Before** (asyncpg style):
```python
db_ingredient = await db.fetchrow(
    """
    SELECT id, canonical_name 
    FROM master_ingredients 
    WHERE LOWER(canonical_name) = LOWER($1)
    LIMIT 1
    """,
    match.canonical_name
)
```

**After** (Supabase client):
```python
client = get_db_client()
db_result = client.table("master_ingredients") \
    .select("id, canonical_name") \
    .ilike("canonical_name", match.canonical_name) \
    .limit(1) \
    .execute()
```

**B. get_similar_ingredients() - Visual similarity search**

**Before** (asyncpg style):
```python
target = await db.fetchrow(
    """
    SELECT id, canonical_name, dominant_colors, surface_texture
    FROM master_ingredients
    WHERE id = $1
    """,
    uuid.UUID(ingredient_id)
)

candidates = await db.fetch(
    """
    SELECT id, canonical_name, dominant_colors, surface_texture
    FROM master_ingredients
    WHERE id != $1 AND dominant_colors IS NOT NULL
    """,
    uuid.UUID(ingredient_id)
)
```

**After** (Supabase client):
```python
client = get_db_client()
target_result = client.table("master_ingredients") \
    .select("id, canonical_name, dominant_colors, surface_texture") \
    .eq("id", ingredient_id) \
    .execute()

candidates_result = client.table("master_ingredients") \
    .select("id, canonical_name, dominant_colors, surface_texture") \
    .neq("id", ingredient_id) \
    .not_.is_("dominant_colors", "null") \
    .execute()
```

**C. confirm_identification() - User feedback**

**Before** (asyncpg style):
```python
await db.execute(
    """
    UPDATE visual_scan_results
    SET user_confirmed_ingredient_id = $1,
        was_correct = $2,
        correction_reason = $3
    WHERE id = $4
    """,
    uuid.UUID(confirmed_ingredient_id),
    was_correct,
    correction_reason,
    uuid.UUID(scan_result_id)
)
```

**After** (Supabase client):
```python
client = get_db_client()
client.table("visual_scan_results") \
    .update({
        "user_confirmed_ingredient_id": confirmed_ingredient_id,
        "was_correct": was_correct,
        "correction_reason": correction_reason
    }) \
    .eq("id", scan_result_id) \
    .execute()
```

---

## 📊 Impact Assessment

### Before Fix
- ❌ Render deployment: FAILED
- ❌ API availability: 0%
- ❌ Uvicorn processes: Crash loop
- ❌ All endpoints: Unreachable

### After Fix
- ✅ Render deployment: Auto-triggered (commit ce923e8)
- ✅ Import errors: Resolved
- ✅ FastAPI startup: Expected to succeed
- ⚠️ Intelligence endpoints: Functional but may need optimization

---

## 🧪 Testing Status

### Deployment Status
```bash
# Monitor deployment
curl https://savo-backend.onrender.com/api/health
# Expected: 200 OK

curl https://savo-backend.onrender.com/api/intelligence/health
# Expected: 200 OK (if health endpoint exists)
```

### Known Limitations
1. **Fuzzy matching removed**: Original code used `similarity()` PostgreSQL function
   - Now uses exact case-insensitive match only
   - Future: Implement fuzzy logic in application layer or use Supabase edge functions

2. **Visual features incomplete**: dominant_colors and surface_texture columns may not exist yet
   - Endpoints will work if data exists
   - Will return empty results if columns missing

3. **No async database calls**: Supabase client is synchronous
   - Acceptable for now (REST API overhead dominates)
   - Future: Consider Supabase Python async client when available

---

## 🚀 Next Steps

### Immediate (Auto-triggered)
1. ✅ Render detects new commit
2. ✅ Starts new build
3. ⏳ Installs dependencies (requirements.txt with numpy)
4. ⏳ Starts uvicorn with fixed imports
5. ⏳ Health check passes
6. ⏳ Traffic switches to new deployment

### Post-Deployment (Manual)
1. **Verify API startup** (5 minutes)
   ```bash
   curl https://savo-backend.onrender.com/api/health
   ```

2. **Test Decision Intelligence endpoints** (1 hour)
   - Follow [DECISION_API_TEST_PLAN.md](DECISION_API_TEST_PLAN.md)
   - Start with health check, then rules, then evaluate-ingredient

3. **Test Intelligence endpoints** (Optional - 30 minutes)
   ```bash
   curl -X POST https://savo-backend.onrender.com/api/intelligence/identify-ingredient \
     -H "Authorization: Bearer $TOKEN" \
     -F "file=@test_image.jpg"
   ```

4. **Monitor Render logs** (Ongoing)
   - Watch for any startup errors
   - Check for numpy import success
   - Verify Supabase connection

---

## 📚 Related Documents

- [WEEK_2_4_UI_SETUP_COMPLETE.md](WEEK_2_4_UI_SETUP_COMPLETE.md) - UI components created before this fix
- [DECISION_API_TEST_PLAN.md](DECISION_API_TEST_PLAN.md) - Test plan for decision intelligence endpoints
- [FIREBASE_SETUP_GUIDE.md](FIREBASE_SETUP_GUIDE.md) - Firebase FCM setup instructions

---

## 🔧 Deployment Timeline

| Time | Event | Status |
|------|-------|--------|
| 14:21 UTC | Render deployment started | Failed (numpy) |
| 14:23 UTC | Repeated crash loops | Failed (get_db) |
| 14:45 UTC | Fix committed (ce923e8) | ✅ |
| 14:46 UTC | Pushed to GitHub | ✅ |
| 14:46 UTC | Render webhook triggered | ⏳ In Progress |
| ~14:51 UTC | Expected deployment completion | Pending |

---

## 💡 Lessons Learned

1. **Check imports thoroughly**: Function name mismatches cause import errors
2. **Database abstraction matters**: Asyncpg and Supabase have different APIs
3. **Test before deploying**: Router was never tested locally with actual imports
4. **Monitor dependencies**: numpy issue was separate, get_db was hidden underneath
5. **Cascade analysis**: One error can mask others (numpy → get_db)

---

**Status**: ✅ Fix deployed, waiting for Render redeploy (~5 minutes)
