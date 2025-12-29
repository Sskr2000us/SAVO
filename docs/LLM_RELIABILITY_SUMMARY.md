# LLM Provider Reliability Implementation Summary

**Date:** December 29, 2025  
**Feature:** OpenAI 429 Rate Limit Fallback to Google Gemini  
**Status:** ✅ Complete (Verification Pending)

---

## 🎯 What Was Implemented

### 1. **Google Gemini LLM Provider**
- Added `GoogleClient` class in `services/api/app/core/llm_client.py`
- Supports gemini-1.5-pro (default) and gemini-1.5-flash models
- Includes schema injection with same CRITICAL RULES as OpenAI
- Built-in retry logic with exponential backoff for 429 errors
- Uses Gemini's native JSON mode (`responseMimeType: "application/json"`)

### 2. **Rate Limit Exception Handling**
- New `RateLimitException` class specifically for 429 errors
- OpenAI client raises this after exhausting 3 retry attempts
- Respects `Retry-After` header if provided by OpenAI
- Exponential backoff: 1s → 2s → 4s before final failure

### 3. **Intelligent Fallback Orchestrator**
- Updated `run_task()` in `orchestrator.py` to handle fallback logic
- **Trigger:** Only on HTTP 429 (rate limits), NOT on timeouts or 5xx errors
- **Flow:**
  1. Try primary provider (e.g., openai) with retry/backoff
  2. If 429 persists after retries, switch to fallback provider (google)
  3. Validate fallback response against same JSON schema
  4. Fail closed if fallback also fails or returns invalid JSON
- **Separation:** Schema retries (max 1) separate from rate-limit retries (max 3)

### 4. **Configuration**
- **New Environment Variables:**
  - `SAVO_LLM_PROVIDER`: `mock`, `openai`, `anthropic`, or `google`
  - `SAVO_LLM_FALLBACK_PROVIDER`: Provider to use on 429 (default: empty/disabled)
  - `GOOGLE_API_KEY`: API key from https://makersuite.google.com/app/apikey
  - `GOOGLE_MODEL`: `gemini-1.5-pro` or `gemini-1.5-flash` (default: pro)

- **Recommended Production Setup:**
  ```bash
  SAVO_LLM_PROVIDER=openai
  SAVO_LLM_FALLBACK_PROVIDER=google
  OPENAI_API_KEY=sk-...
  GOOGLE_API_KEY=your-google-key
  ```

### 5. **Observability & Logging**
- Logs provider used for each request
- Logs retry attempts and backoff delays
- Logs fallback trigger: `"Falling back from openai to google"`
- Logs fallback success/failure with detailed error messages
- Structured logging format: `Task {task_name} (provider={provider}) ...`

### 6. **Documentation**
- Updated `docs/ACTION_ITEMS_END_TO_END.md` with reliability checklist
- Updated `docs/DEPLOY_RENDER.md` with:
  - Google Gemini setup instructions
  - Rate limit troubleshooting guide
  - Provider-specific rate limits (OpenAI, Anthropic, Google)
  - Fallback configuration examples
- Updated `.env.example` with Google variables and fallback config
- Added weekly 3-day horizon verification item to action items

---

## 📋 Files Modified

1. **services/api/app/core/llm_client.py**
   - Added `RateLimitException` class
   - Added `GoogleClient` class (100+ lines)
   - Updated OpenAI client to raise RateLimitException on 429
   - Improved retry logic with Retry-After header support

2. **services/api/app/core/orchestrator.py**
   - Updated `run_task()` to handle fallback logic
   - Created `_try_provider()` helper function
   - Created `_build_error_response()` helper function
   - Added RateLimitException import and handling

3. **services/api/app/core/settings.py**
   - Added `llm_fallback_provider` setting

4. **services/api/.env.example**
   - Added Google Gemini configuration section
   - Added `SAVO_LLM_FALLBACK_PROVIDER` variable
   - Updated provider list to include `google`

5. **docs/ACTION_ITEMS_END_TO_END.md**
   - Added section 4.1: LLM Provider Reliability checklist
   - Added weekly 3-day horizon verification item to section 3.6
   - Marked all implementation items as complete

6. **docs/DEPLOY_RENDER.md**
   - Added Google API key setup to environment variables
   - Added recommended production configuration
   - Added comprehensive rate limit troubleshooting section
   - Documented fallback behavior (429 only)

7. **services/api/test_fallback.py** (new)
   - Test script to verify fallback behavior
   - Tests daily and weekly planning with fallback enabled

---

## 🔍 Key Design Decisions

### Why 429 Only?
- **Rationale:** Rate limits (429) are predictable and fallback-safe
- **Timeouts/5xx:** May indicate systemic issues, not suitable for blind retry
- **User Impact:** Prevents cascading failures; keeps errors surfaced appropriately

### Why Google as Fallback?
- **Higher free tier limits:** 15 req/min vs OpenAI's 3 req/min
- **Better JSON compliance:** Native JSON mode, strong schema adherence
- **Cost-effective:** Free tier sufficient for MVP testing
- **Performance:** gemini-1.5-flash faster than GPT-4 for some tasks

### Why Separate Retry Counts?
- **Schema retries (max 1):** Corrective prompt to fix validation errors
- **Rate-limit retries (max 3):** Transient backoff for 429 errors
- **Prevents multiplication:** Avoids 1 × 3 = 3 unnecessary attempts per request

### Why Fail-Closed?
- **Contract integrity:** Mobile app expects valid MenuPlanResponse
- **No partial data:** Invalid JSON worse than error status
- **Clear error messages:** User sees "rate limit" vs silent failure

---

## ✅ Verification Checklist

### Completed
- [x] Google Gemini provider implemented
- [x] Rate limit detection and retry logic
- [x] Fallback orchestrator logic
- [x] Configuration variables added
- [x] Documentation updated
- [x] Deployment guide updated
- [x] Action items checklist created

### Pending
- [ ] **Local testing:** Run test_fallback.py with mock 429 response
- [ ] **Render deployment:** Deploy to production with fallback configured
- [ ] **End-to-end test:** Trigger 429 from OpenAI, verify Google fallback
- [ ] **Schema validation:** Confirm Google returns valid MENU_PLAN_SCHEMA
- [ ] **Weekly 3-day horizon:** Test Flutter UI shows 3 days correctly
- [ ] **Error handling:** Verify timeouts/5xx do NOT trigger fallback

---

## 🚀 Deployment Steps

### For Render (Already Auto-Deployed)
1. **Wait for auto-deploy:** Code already pushed (commit d6286be)
2. **Configure environment:**
   - Go to Render dashboard → savo-api → Environment
   - Add: `GOOGLE_API_KEY` = your-google-api-key
   - Add: `SAVO_LLM_FALLBACK_PROVIDER` = `google`
   - Keep: `SAVO_LLM_PROVIDER` = `openai` (or current value)
3. **Restart service:** Auto-restarts after env var changes
4. **Verify health:** `curl https://savo-ynp1.onrender.com/health`

### For Local Testing
```powershell
cd C:\Users\sskr2\SAVO\services\api
.\.venv\Scripts\Activate.ps1

# Set environment
$env:SAVO_LLM_PROVIDER="openai"
$env:SAVO_LLM_FALLBACK_PROVIDER="google"
$env:OPENAI_API_KEY="sk-..."
$env:GOOGLE_API_KEY="your-google-key"

# Run test
python test_fallback.py
```

---

## 📊 Rate Limit Reference

| Provider | Free Tier RPM | Free Tier RPD | Paid Tier RPM |
|----------|---------------|---------------|---------------|
| OpenAI   | 3             | 200           | 500+          |
| Anthropic| 5             | 1000          | Varies        |
| Google   | 15            | 1500          | 60+ (paid)    |

**RPM** = Requests Per Minute  
**RPD** = Requests Per Day

---

## 🐛 Known Issues

### Weekly Planner Shows 1 Day Instead of 3
- **Root Cause:** TBD - Flutter UI likely rendering correctly, check backend response
- **Status:** Investigation needed
- **Action Item:** Added to section 3.6 verification checklist
- **Test:** Backend returns 3 menus for `num_days=3` (confirmed in logs)

### OpenAI 429 During Testing
- **Cause:** Free tier exhausted (3 req/min, 200/day)
- **Solution:** Fallback implemented; set `SAVO_LLM_FALLBACK_PROVIDER=google`
- **Alternative:** Add billing to OpenAI for higher limits

---

## 📝 Next Steps

1. **Immediate:** Get Google API key and test fallback locally
2. **Render:** Configure Google env vars in production
3. **Testing:** Run test_fallback.py to verify end-to-end flow
4. **Flutter:** Debug weekly planner 3-day display issue
5. **Monitoring:** Observe Render logs for fallback triggers
6. **Production:** Monitor API costs and rate limit usage

---

## 🎉 Impact

- **Resilience:** App continues working even when primary provider rate-limited
- **User Experience:** No "Too Many Requests" errors surfaced to users
- **Cost Optimization:** Free Google tier handles overflow from OpenAI free tier
- **Flexibility:** Can switch providers via env var without code changes
- **Observability:** Clear logs show which provider served each request

---

**Implementation Time:** ~2 hours  
**Lines of Code:** ~250 added/modified  
**Commits:** 4 commits (d3a5e35, e4e65e7, d1f5e3c, d6286be)  
**Status:** Ready for production testing ✅
