# 🚀 Quick Deploy to Render

## Prerequisites
- GitHub account
- Render account (free at render.com)
- OpenAI or Anthropic API key (optional, can use mock mode)

## Step-by-Step Deployment

### 1. Push Code to GitHub

```powershell
# Initialize git if not already done
git init
git add .
git commit -m "Initial commit - SAVO MVP"

# Create new GitHub repo and push
git remote add origin https://github.com/YOUR_USERNAME/savo.git
git branch -M main
git push -u origin main
```

### 2. Deploy Backend to Render

1. Go to [dashboard.render.com](https://dashboard.render.com)
2. Click **"New +"** → **"Web Service"**
3. Connect your GitHub repository
4. Configure:
   - **Name:** `savo-api`
   - **Region:** Oregon (or closest to you)
   - **Branch:** `main`
   - **Root Directory:** (leave empty)
   - **Runtime:** Python 3
   - **Build Command:** `cd services/api && pip install -r requirements.txt`
   - **Start Command:** `cd services/api && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Instance Type:** Free

5. **Add Environment Variables:**
   Click "Advanced" → "Add Environment Variable":
   ```
   SAVO_LLM_PROVIDER = mock
   SAVO_PROMPT_PACK_PATH = ../../docs/spec/prompt-pack.gpt-5.2.json
   ```
   
   **(Optional) For real LLM:**
   ```
   SAVO_LLM_PROVIDER = openai
   OPENAI_API_KEY = sk-your-key-here
   OPENAI_MODEL = gpt-4
   ```

6. Click **"Create Web Service"**
7. Wait for deployment (2-3 minutes)
8. Your API will be live at: `https://savo-api.onrender.com`

### 3. Test Backend

Visit: `https://savo-api.onrender.com/health`

Should return:
```json
{
  "status": "ok",
  "llm_provider": "mock"
}
```

### 4. Deploy Flutter Web

**Option A: Netlify (Recommended for Flutter)**

```powershell
# Install Netlify CLI
npm install -g netlify-cli

# Build Flutter web
cd apps/mobile
flutter build web --release

# Deploy
netlify deploy --dir=build/web --prod
```

**Option B: Render Static Site**

1. In Render Dashboard: **"New +"** → **"Static Site"**
2. Configure:
   - **Name:** `savo-web`
   - **Build Command:** `cd apps/mobile && flutter build web --release`
   - **Publish Directory:** `apps/mobile/build/web`
3. Deploy

### 5. Update Flutter API URL

Edit `apps/mobile/lib/services/api_client.dart`:

```dart
static String _defaultBaseUrl() {
  if (kIsWeb) return 'https://savo-api.onrender.com'; // Your Render URL
  // ... rest of code
}
```

Rebuild and redeploy Flutter app.

### 6. Update CORS (Important!)

Edit `services/api/app/main.py` line 17:

```python
allow_origins=[
    "http://localhost:52884",  # Local dev
    "https://savo-web.onrender.com",  # Add your frontend URL
],
```

Commit and push - Render will auto-redeploy.

## 🎉 You're Live!

- **Backend API:** https://savo-api.onrender.com
- **Frontend:** https://savo-web.onrender.com (or your Netlify URL)
- **API Docs:** https://savo-api.onrender.com/docs

## ⚠️ Important Notes

**Free Tier Limitations:**
- Backend sleeps after 15 min inactivity
- First request takes ~30 seconds to wake up
- Good for testing, not production

**For Production:**
- Upgrade to paid tier ($7/month) for always-on
- Add PostgreSQL for persistent storage
- Use real LLM (OpenAI/Anthropic)
- Set up custom domain
- Enable monitoring

## 🐛 Common Issues

**CORS Error:**
```
Access to fetch at 'https://savo-api.onrender.com' from origin 'https://savo-web.onrender.com' has been blocked by CORS policy
```
→ Add your frontend URL to `allow_origins` in main.py

**Backend Not Starting:**
- Check Render logs for errors
- Verify Python version (3.12)
- Check requirements.txt has all dependencies

**LLM Timeout:**
- Increase `LLM_TIMEOUT` env variable to 120

Need help? Check [docs/DEPLOY_RENDER.md](DEPLOY_RENDER.md) for detailed troubleshooting.
