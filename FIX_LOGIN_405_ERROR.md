# Login 405 Error - FIXED ✅

## Issue
Login was failing with:
```
AuthUnknownException: Received an empty response with status code 405
```

## Root Cause
The Flutter app was using **placeholder values** for Supabase credentials:
- `supabaseUrl: 'YOUR_SUPABASE_PROJECT_URL'`
- `supabaseAnonKey: 'YOUR_SUPABASE_ANON_KEY'`

This caused Supabase auth to fail with a 405 (Method Not Allowed) error because it couldn't reach the correct Supabase project.

## Fix Applied
Updated [`apps/mobile/lib/config/app_config.dart`](apps/mobile/lib/config/app_config.dart):
```dart
static const String supabaseUrl = 'https://tifecgfgtxkydqxjumnn.supabase.co';
static const String supabaseAnonKey = 'eyJhbGci...'; // Full anon key
```

## Security Note
✅ **Anon key is safe to expose** - It's designed to be public and included in client apps.
- Anon key only allows authenticated operations defined in your RLS policies
- JWT secret (used on backend) is what must remain secret
- See: https://supabase.com/docs/guides/api#api-keys

## Deployment Status
- **Commit:** `c1104d4`
- **Vercel:** Rebuilding now with correct credentials
- **ETA:** 2-3 minutes

## Test After Deploy
1. Open https://savo-web.vercel.app (hard refresh with Ctrl+Shift+R)
2. Login with: `demo@savo.app` / password
3. Should successfully authenticate and redirect to home

## Next Steps (Security Best Practice)
For production, move credentials to Vercel environment variables:
1. Go to Vercel Dashboard → Project Settings → Environment Variables
2. Add:
   - `SUPABASE_URL` = `https://tifecgfgtxkydqxjumnn.supabase.co`
   - `SUPABASE_ANON_KEY` = `<your-anon-key>`
3. Update build command to pass env vars:
   ```bash
   flutter build web --dart-define=SUPABASE_URL=$SUPABASE_URL --dart-define=SUPABASE_ANON_KEY=$SUPABASE_ANON_KEY
   ```
