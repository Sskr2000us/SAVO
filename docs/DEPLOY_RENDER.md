# SAVO Deployment Guide - Render

## 🚀 Backend Deployment (FastAPI)

### Option 1: Using Render Blueprint (Recommended)

1. **Push to GitHub:**
   ```bash
   git add .
   git commit -m "Add Render deployment config"
   git push origin main
   ```

2. **Connect to Render:**
   - Go to [render.com](https://render.com) and sign up/login
   - Click "New +" → "Blueprint"
   - Connect your GitHub repository
   - Render will automatically detect `render.yaml`

3. **Configure Environment Variables:**
   In Render dashboard, add these secret environment variables:
   
   **LLM Provider Configuration:**
   - `SAVO_LLM_PROVIDER` = `mock` (or `openai`/`anthropic`/`google`)
   - `SAVO_LLM_FALLBACK_PROVIDER` = `google` (optional, fallback on rate limits)
   - `LLM_TIMEOUT` = `60` (optional, defaults to 60 seconds)
   
   **OpenAI (if using):**
   - `OPENAI_API_KEY` = `sk-...` (get from https://platform.openai.com/api-keys)
   - `OPENAI_MODEL` = `gpt-4` (optional, defaults to gpt-4-turbo-preview)
   
   **Anthropic (if using):**
   - `ANTHROPIC_API_KEY` = `sk-ant-...` (get from https://console.anthropic.com/account/keys)
   - `ANTHROPIC_MODEL` = `claude-3-5-sonnet-20241022` (optional)
   
   **Google Gemini (if using or as fallback):**
   - `GOOGLE_API_KEY` = `your-google-api-key` (get from https://makersuite.google.com/app/apikey)
   - `GOOGLE_MODEL` = `gemini-1.5-pro` (optional, or `gemini-1.5-flash` for faster/cheaper)
   
   **Recommended Setup for Production:**
   - Primary: `SAVO_LLM_PROVIDER=openai` or `anthropic`
   - Fallback: `SAVO_LLM_FALLBACK_PROVIDER=google` (handles rate limits automatically)

4. **Deploy:**
   - Click "Apply" and Render will build and deploy
   - Your API will be live at: `https://savo-api.onrender.com`
   - Test health endpoint: `https://savo-api.onrender.com/health`

### Option 2: Manual Setup

1. **Create Web Service:**
   - Go to Render Dashboard → "New +" → "Web Service"
   - Connect GitHub repository
   - Configure:
     - **Name:** savo-api
     - **Region:** Oregon (US West)
     - **Branch:** main
     - **Root Directory:** (leave empty)
     - **Runtime:** Python 3
     - **Build Command:** `cd services/api && pip install -r requirements.txt`
     - **Start Command:** `cd services/api && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
     - **Plan:** Free

2. **Add Environment Variables** (same as above)

3. **Deploy!**

---

## 📱 Flutter Web Deployment

### Option 1: Build Locally + Deploy to Render Static Site

1. **Build Flutter Web:**
   ```powershell
   cd apps/mobile
   flutter build web --release
   ```

2. **Create Static Site on Render:**
   - Go to Render Dashboard → "New +" → "Static Site"
   - Connect repository
   - Configure:
     - **Name:** savo-web
     - **Build Command:** `cd apps/mobile && flutter build web --release`
     - **Publish Directory:** `apps/mobile/build/web`

3. **Update API Base URL:**
   After deployment, update Flutter app to use Render API URL:
   ```dart
   // In apps/mobile/lib/services/api_client.dart
   static String _defaultBaseUrl() {
     return 'https://savo-api.onrender.com'; // Your Render API URL
   }
   ```

### Option 2: Deploy Flutter Web to Netlify/Vercel (Recommended)

Flutter web apps work better on Netlify or Vercel:

**Netlify:**
1. Install Netlify CLI: `npm install -g netlify-cli`
2. Build: `flutter build web --release`
3. Deploy: `netlify deploy --dir=apps/mobile/build/web --prod`

**Vercel:**
1. Install Vercel CLI: `npm install -g vercel`
2. Build: `flutter build web --release`
3. Deploy: `vercel --prod`

---

## 🔧 Post-Deployment Configuration

### Update CORS for Production

In `services/api/app/main.py`, update CORS origins:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:52884",  # Local dev
        "https://savo-web.onrender.com",  # Your frontend URL
        "https://your-domain.com",  # Custom domain if you have one
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Enable Persistence (Optional)

For production, consider adding PostgreSQL:

1. **Add Postgres Database:**
   - In Render Dashboard: "New +" → "PostgreSQL"
   - Name: savo-db
   - Plan: Free (expires after 90 days) or Starter ($7/month)

2. **Update Backend:**
   - Add `DATABASE_URL` environment variable (auto-set by Render)
   - Implement database models (SQLAlchemy/Tortoise ORM)
   - Migrate from in-memory storage

---

## 🔐 Production Checklist

- [ ] Set `SAVO_LLM_PROVIDER` to `openai` or `anthropic` (not `mock`)
- [ ] Add real API keys as secret environment variables
- [ ] Update CORS origins to include your frontend URL
- [ ] Enable HTTPS (automatic on Render)
- [ ] Set up custom domain (optional)
- [ ] Configure logging (Render provides automatic logs)
- [ ] Add error tracking (Sentry recommended)
- [ ] Monitor costs (OpenAI/Anthropic API usage)

---

## 💰 Cost Estimate

**Free Tier (Testing):**
- Render Web Service (Backend): **Free** (sleeps after 15 min inactivity)
- Render Static Site (Frontend): **Free**
- Mock LLM: **$0**
- **Total: $0/month**

**Paid Tier (Production):**
- Render Web Service (Backend): **$7/month** (always on)
- Render Static Site (Frontend): **Free**
- PostgreSQL (optional): **$7/month**
- OpenAI API: **~$10-50/month** (depending on usage)
- **Total: ~$24-64/month**

---

## 🐛 Troubleshooting

**Backend not starting:**
- Check Render logs for errors
- Verify Python version (3.12)
- Ensure requirements.txt has all dependencies

**CORS errors:**
- Update allowed origins in main.py
- Redeploy backend after CORS changes

**Free tier sleeps:**
- Render free tier sleeps after 15 min inactivity
- First request after sleep takes ~30 seconds
- Upgrade to paid tier ($7/month) for always-on service

**Rate Limit Errors (HTTP 429):**
- **OpenAI Free Tier:** 3 requests/minute, 200/day
- **OpenAI Paid:** 500+ requests/day (increases with usage history)
- **Google Gemini Free:** 15 requests/minute, 1500/day
- **Solution 1:** Set `SAVO_LLM_FALLBACK_PROVIDER=google` to auto-fallback on 429
- **Solution 2:** Add billing to OpenAI account for higher limits
- **Solution 3:** Wait 1-2 minutes between requests on free tier
- Check logs for: `Rate limit exceeded for provider: openai` → `Falling back to google`

**LLM returns invalid JSON:**
- Check Render logs for schema validation errors
- Verify prompt pack is loading correctly (SAVO_PROMPT_PACK_PATH)
- Schema validation errors trigger 1 retry automatically
- If still failing, check `error_message` in response

**Fallback not working:**
- Verify `SAVO_LLM_FALLBACK_PROVIDER=google` is set
- Ensure `GOOGLE_API_KEY` is configured
- Check logs for "Fallback provider google also failed"
- Fallback only triggers on 429, not timeouts/5xx errors
- First request after sleep takes ~30 seconds to wake up
- Upgrade to paid tier for always-on service

**LLM timeout:**
- Increase `LLM_TIMEOUT` environment variable
- Default is 60 seconds, try 120 for complex requests

---

## 📚 Resources

- [Render Docs](https://render.com/docs)
- [FastAPI Deployment Guide](https://fastapi.tiangolo.com/deployment/)
- [Flutter Web Deployment](https://docs.flutter.dev/deployment/web)
