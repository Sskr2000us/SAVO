# Flutter Web Deployment Guide

## Overview
Deploy your SAVO Flutter web app to static hosting alongside the Render backend.

---

## Option 1: Render Static Site (Recommended)

### Step 1: Build Flutter Web
```bash
cd C:\Users\sskr2\SAVO\apps\mobile
flutter build web --release
```

### Step 2: Deploy to Render
1. Go to [Render Dashboard](https://dashboard.render.com)
2. Click **"New +" → "Static Site"**
3. Connect your GitHub repository (`Sskr2000us/SAVO`)
4. Configure:
   - **Name**: `savo-web`
   - **Branch**: `main`
   - **Build Command**: `cd apps/mobile && flutter build web --release`
   - **Publish Directory**: `apps/mobile/build/web`
5. Click **"Create Static Site"**

### Step 3: Update Backend URL
After deployment, update the Flutter app to point to your Render backend:

**File**: `apps/mobile/lib/services/api_client.dart`
```dart
static String _defaultBaseUrl() {
  // Production backend
  return 'https://savo-ynp1.onrender.com';
}
```

### Step 4: Redeploy
```bash
git add apps/mobile/lib/services/api_client.dart
git commit -m "Update Flutter to use production backend"
git push
```

Render will auto-deploy your Flutter web app!

**Result**: Your app will be live at `https://savo-web.onrender.com`

---

## Option 2: Netlify

### Step 1: Build Flutter Web
```bash
cd apps/mobile
flutter build web --release
```

### Step 2: Deploy to Netlify
```bash
# Install Netlify CLI
npm install -g netlify-cli

# Login
netlify login

# Deploy
cd build/web
netlify deploy --prod
```

**Result**: App live at `https://your-site.netlify.app`

---

## Option 3: Vercel

### Step 1: Build Flutter Web
```bash
cd apps/mobile
flutter build web --release
```

### Step 2: Deploy to Vercel
```bash
# Install Vercel CLI
npm install -g vercel

# Deploy
cd build/web
vercel --prod
```

**Result**: App live at `https://your-site.vercel.app`

---

## Option 4: Firebase Hosting

### Step 1: Install Firebase CLI
```bash
npm install -g firebase-tools
firebase login
```

### Step 2: Initialize Firebase
```bash
cd apps/mobile
firebase init hosting
```

- **Public directory**: `build/web`
- **Single-page app**: Yes
- **Overwrite index.html**: No

### Step 3: Build and Deploy
```bash
flutter build web --release
firebase deploy --only hosting
```

**Result**: App live at `https://your-project.web.app`

---

## Current Setup

### Backend (Already Deployed)
- **URL**: https://savo-ynp1.onrender.com
- **API Docs**: https://savo-ynp1.onrender.com/docs
- **Status**: ✅ Live and running

### Frontend (Needs Deployment)
- **Status**: ❌ Running locally only
- **Current URL**: http://localhost:55219 (changes on each run)
- **Need**: Static hosting for Flutter web build

---

## Testing Locally

### Start Backend
```bash
cd C:\Users\sskr2\SAVO\services\api
.\.venv\Scripts\Activate.ps1
$env:SAVO_VISION_PROVIDER='mock'
$env:SAVO_REASONING_PROVIDER='mock'
$env:SUPABASE_URL='your-supabase-url'
$env:SUPABASE_SERVICE_KEY='your-service-key'
uvicorn app.main:app --reload --port 8000
```

### Start Flutter Web
```bash
cd C:\Users\sskr2\SAVO\apps\mobile
flutter run -d chrome
```

---

## Fix Backend 500 Errors

### Issue
The screenshot shows **500 errors** when saving to `/profile/household`. This means:
- Backend is crashing when trying to save to database
- Supabase credentials are missing

### Solution: Add Supabase Env Vars

#### For Local Development:
Create `.env` file in `services/api/`:
```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=eyJhbGci...your-key...
```

#### For Render Production:
1. Go to [Render Dashboard](https://dashboard.render.com)
2. Select your `savo-api` service
3. Go to **Environment** tab
4. Add:
   - `SUPABASE_URL` = `https://xxxxx.supabase.co`
   - `SUPABASE_SERVICE_KEY` = `eyJhbGci...` (from Supabase dashboard)
5. Click **"Save Changes"**
6. Render will auto-redeploy

### Get Supabase Credentials
1. Go to [Supabase Dashboard](https://supabase.com/dashboard)
2. Select your project
3. Go to **Settings → API**
4. Copy:
   - **Project URL** → `SUPABASE_URL`
   - **service_role secret** → `SUPABASE_SERVICE_KEY`

---

## Recommended Deployment Flow

1. **Fix Backend First** (Add Supabase env vars to Render)
2. **Test Backend**: https://savo-ynp1.onrender.com/docs
3. **Build Flutter**: `flutter build web --release`
4. **Deploy to Render Static Site** (easiest, same platform as backend)
5. **Test Full Stack**: Flutter web → Backend → Database

---

## Why Deploy Flutter Separately?

### Current Setup:
- **Backend**: Python/FastAPI on Render (server-side)
- **Frontend**: Flutter web (static files)

### Separation Benefits:
- **Independent scaling**: Backend scales separately from frontend
- **CDN delivery**: Static files served fast globally
- **Cost effective**: Static hosting is free/cheap
- **Easy updates**: Push code → auto-deploy

### Integration:
```
User → Flutter Web App (Render Static Site)
         ↓ (API calls)
      Backend API (Render Web Service)
         ↓ (database queries)
      Supabase PostgreSQL
```

---

## Next Steps

1. **Add Supabase credentials to Render** (fixes 500 errors)
2. **Deploy Flutter web** (choose Option 1: Render Static Site)
3. **Test end-to-end** (web app → backend → database)
4. **Share production URL** with users

---

## Support

- **Backend logs**: Render Dashboard → savo-api → Logs
- **Database**: Supabase Dashboard → SQL Editor
- **Flutter build issues**: `flutter clean && flutter pub get`
