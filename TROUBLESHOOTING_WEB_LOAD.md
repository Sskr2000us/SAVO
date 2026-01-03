# Troubleshooting "Initializing SAVO..." Stuck Issue

## Problem
The Flutter web app shows "Initializing SAVO..." spinner forever and never loads.

## Root Causes & Solutions

### 1. **Browser Cache (Most Common)**
**Symptoms:** App worked before, now stuck loading
**Solution:**
```
1. Open browser console (F12 → Console tab)
2. Look for CORS errors or old cached code
3. Hard refresh: Ctrl+Shift+R (Windows) or Cmd+Shift+R (Mac)
4. Or clear cache: Ctrl+Shift+Delete → "Cached images and files"
```

### 2. **Backend Server Timeout**
**Symptoms:** Console shows timeout errors
**Check backend status:**
```powershell
Invoke-WebRequest https://savo-ynp1.onrender.com/health
```
**Expected:** `{"status":"ok","llm_provider":"openai",...}`

**If backend is sleeping (Render free tier):**
```powershell
.\wake_backend.ps1
# Wait 30-60 seconds for cold start
```

### 3. **No Supabase Session**
**Symptoms:** Console shows "🔐 No session found - navigating to login"
**Solution:** 
- This is normal behavior - app should redirect to login screen
- If stuck, manually navigate to `/login`: `https://savo-web.vercel.app/login`

### 4. **API Call Hanging**
**Fixed in commit 8fa9f9f** - Added 10-second timeout to prevent infinite hang

**Debug in console:**
```javascript
// Check what's happening
// Look for these debug messages:
// "===== SAVO AUTH CHECK ====="
// "🔐 Session exists: true/false"
// "🔐 Session found - checking onboarding status"
```

### 5. **CORS Errors**
**Symptoms:** Console shows "No 'Access-Control-Allow-Origin' header"
**Solution:** Already fixed in backend (commit 8fe259e)
- Clear browser cache (Ctrl+Shift+R)
- Backend adds CORS headers to all responses including errors

### 6. **Network Connectivity**
**Test:**
```powershell
# Test Vercel frontend
curl https://savo-web.vercel.app

# Test Render backend
curl https://savo-ynp1.onrender.com/health

# Test Supabase
curl https://sskr2000.supabase.co
```

## Quick Diagnostic Steps

1. **Open Browser Console (F12)**
   - Look for red errors
   - Look for debug messages starting with 🔐
   - Check Network tab for failed requests

2. **Check Backend Health**
   ```powershell
   Invoke-WebRequest https://savo-ynp1.onrender.com/health
   ```

3. **Clear Cache and Hard Refresh**
   ```
   Ctrl+Shift+Delete → Clear cached images/files
   Ctrl+Shift+R → Hard refresh
   ```

4. **Try Incognito/Private Window**
   - Ctrl+Shift+N (Chrome)
   - Ctrl+Shift+P (Firefox)
   - Tests if cache is the issue

5. **Check Vercel Deployment**
   - Visit: https://vercel.com/dashboard
   - Ensure latest commit deployed
   - Check build logs for errors

## Expected Console Output (Normal Flow)

```
===== SAVO AUTH CHECK =====
🔐 Session exists: true
🔐 User ID: 8c423f04-043d-49a5-8cdd-818a5d1c6bb7
🔐 User Email: sureshvidh@gmail.com
==========================
🔐 Session found - checking onboarding status
```

Then navigates to either:
- `/home` (if onboarding complete)
- `/onboarding` (if onboarding incomplete)
- `/login` (if no session)

## Recent Fixes

| Commit | Fix | Date |
|--------|-----|------|
| 8fa9f9f | Added 10s timeout to prevent infinite hang | 2026-01-03 |
| 8fe259e | Fixed CORS headers on error responses | 2026-01-03 |
| fa5b46c | Added HTTP client timeouts (120s planning, 30s default) | 2026-01-03 |

## Still Stuck?

1. **Copy console output** (F12 → Console → right-click → "Save as...")
2. **Check Network tab** (F12 → Network → filter by "Fetch/XHR")
3. **Look for:**
   - Red/failed requests
   - Requests taking >10 seconds
   - 401/403/500 status codes
   - CORS errors

## Advanced: Force Fresh Session

If you need to completely reset:

```javascript
// In browser console
localStorage.clear();
sessionStorage.clear();
location.reload(true);
```

Or logout and login again to create fresh session.
