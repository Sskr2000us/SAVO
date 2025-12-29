# 🚀 Deploy SAVO to Render - Step by Step

Your GitHub repo: https://github.com/Sskr2000us/SAVO

## Deploy Backend API (5 minutes)

### 1. Create Render Account
- Go to [render.com](https://render.com) and sign up (free)
- Connect your GitHub account

### 2. Create Web Service
- Click **"New +"** → **"Web Service"**
- Select **"Build and deploy from a Git repository"**
- Click **"Connect account"** if not already connected
- Find and select: **Sskr2000us/SAVO**

### 3. Configure Service
Fill in these settings:

**Basic Settings:**
- **Name:** `savo-api` (or whatever you prefer)
- **Region:** Oregon (or closest to you)
- **Branch:** `main`
- **Root Directory:** (leave empty)
- **Runtime:** Python 3

**Build Settings:**
- **Build Command:** 
  ```
  cd services/api && pip install -r requirements.txt
  ```
- **Start Command:**
  ```
  cd services/api && uvicorn app.main:app --host 0.0.0.0 --port $PORT
  ```

**Instance Type:**
- Select **"Free"** (for testing)

### 4. Add Environment Variables
Click **"Advanced"** → **"Add Environment Variable"**

**Required:**
```
SAVO_LLM_PROVIDER = mock
```

**Optional (for real LLM):**
```
SAVO_LLM_PROVIDER = openai
OPENAI_API_KEY = sk-your-api-key-here
OPENAI_MODEL = gpt-4
```

Or for Anthropic:
```
SAVO_LLM_PROVIDER = anthropic
ANTHROPIC_API_KEY = sk-ant-your-key-here
ANTHROPIC_MODEL = claude-3-sonnet-20240229
```

### 5. Deploy!
- Click **"Create Web Service"**
- Render will start building (takes 2-3 minutes)
- Watch the logs for any errors
- Once deployed, you'll get a URL like: `https://savo-api.onrender.com`

### 6. Test Your API
Visit: `https://your-app-name.onrender.com/health`

Should return:
```json
{
  "status": "ok",
  "llm_provider": "mock"
}
```

Also check API docs: `https://your-app-name.onrender.com/docs`

---

## Deploy Flutter Web (Choose One Option)

### Option A: Netlify (Recommended - Best for Flutter)

1. **Build locally:**
   ```powershell
   cd apps/mobile
   flutter build web --release
   ```

2. **Install Netlify CLI:**
   ```powershell
   npm install -g netlify-cli
   ```

3. **Deploy:**
   ```powershell
   netlify deploy --dir=build/web --prod
   ```

4. **Follow prompts:**
   - Create new site
   - Get your URL: `https://your-site-name.netlify.app`

### Option B: Render Static Site

1. In Render Dashboard: **"New +"** → **"Static Site"**
2. Select your GitHub repo: **Sskr2000us/SAVO**
3. Configure:
   - **Name:** `savo-web`
   - **Branch:** `main`
   - **Root Directory:** (leave empty)
   - **Build Command:** 
     ```
     cd apps/mobile && flutter build web --release
     ```
   - **Publish Directory:** `apps/mobile/build/web`
4. Click **"Create Static Site"**

**Note:** Render doesn't have Flutter pre-installed, so this might fail. Netlify is more reliable for Flutter web.

---

## Connect Frontend to Backend

### 1. Update API URL in Flutter
Edit `apps/mobile/lib/services/api_client.dart`:

```dart
static String _defaultBaseUrl() {
  if (kIsWeb) return 'https://savo-api.onrender.com'; // Your Render API URL
  if (defaultTargetPlatform == TargetPlatform.android) {
    return 'http://10.0.2.2:8000';
  }
  return 'http://localhost:8000';
}
```

### 2. Update CORS on Backend
Edit `services/api/app/main.py` line 17:

```python
allow_origins=[
    "http://localhost:52884",  # Local dev
    "https://savo-api.onrender.com",  # Your backend (for docs)
    "https://your-site-name.netlify.app",  # Your frontend
    # Or if using Render static site:
    # "https://savo-web.onrender.com",
],
```

### 3. Commit and Push
```powershell
git add .
git commit -m "Update API URLs for production"
git push origin main
```

Render will auto-deploy the backend changes!

### 4. Rebuild and Redeploy Flutter
```powershell
cd apps/mobile
flutter build web --release
netlify deploy --dir=build/web --prod
```

---

## 🎉 You're Live!

- **Backend API:** https://savo-api.onrender.com
- **API Docs:** https://savo-api.onrender.com/docs
- **Frontend:** https://your-site-name.netlify.app

---

## ⚠️ Important Notes

### Free Tier Limitations
- **Render Free Tier:** Backend sleeps after 15 min inactivity
- **First request:** Takes ~30 seconds to wake up
- **Good for:** Testing and demos
- **Not good for:** Production use

### Upgrade for Production
- **Render Starter:** $7/month (always-on, no sleep)
- **PostgreSQL:** $7/month (persistent data storage)
- **Custom domain:** Free to add

---

## 🐛 Troubleshooting

### Backend build fails
**Error:** `Could not find requirements.txt`

**Fix:** Make sure the build command is:
```
cd services/api && pip install -r requirements.txt
```

### CORS Error in Browser
**Error:** `Access blocked by CORS policy`

**Fix:** 
1. Add your frontend URL to `allow_origins` in `main.py`
2. Push changes to GitHub
3. Render will auto-redeploy

### Backend returns 500 errors
**Check:** 
1. Render logs (click on your service → "Logs")
2. Verify environment variables are set
3. Check Python version (should be 3.12)

### LLM requests timeout
**Fix:** Add environment variable:
```
LLM_TIMEOUT = 120
```

---

## 📊 Monitor Your Deployment

### Render Dashboard
- **Logs:** Real-time logs for debugging
- **Metrics:** CPU/Memory usage
- **Events:** Deployment history
- **Settings:** Environment variables, scaling

### Check Health
Set up a cron job or uptime monitor to ping:
```
https://savo-api.onrender.com/health
```

This keeps the free tier awake!

---

## 💰 Cost Breakdown

**Current Setup (Free):**
- Render Web Service: $0 (free tier)
- Netlify Static Site: $0 (free tier)
- Mock LLM: $0
- **Total: $0/month**

**Production Setup:**
- Render Starter: $7/month
- PostgreSQL: $7/month
- OpenAI API: ~$10-30/month
- **Total: ~$24-44/month**

---

## 🚀 Next Steps

1. **Deploy backend to Render** (follow steps above)
2. **Test the API** at your Render URL
3. **Deploy frontend to Netlify**
4. **Update URLs** and CORS
5. **Test the full app!**

Need help? The Render dashboard has great logs for debugging!
