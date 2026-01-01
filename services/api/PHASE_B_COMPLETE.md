# Phase B Implementation Complete ✅

## What Changed

### 1. Created JWT Authentication Middleware
**File:** `services/api/app/middleware/auth.py`

- `get_current_user()` - Validates Supabase JWT tokens and extracts user_id
- `get_current_user_optional()` - Optional auth for flexible routes
- `verify_user_owns_resource()` - Helper for resource ownership checks

### 2. Added JWT Library Dependency
**File:** `services/api/requirements.txt`

Added: `python-jose[cryptography]>=3.3.0`

### 3. Refactored All Profile Routes
**File:** `services/api/app/api/routes/profile.py`

**Before:** Used custom headers
```python
async def get_household(
    x_user_id: str = Header(...),
    x_user_email: str = Header(...)
):
```

**After:** Uses JWT Bearer tokens
```python
async def get_household(
    user_id: str = Depends(get_current_user)
):
```

All endpoints now require `Authorization: Bearer <token>` header.

---

## Environment Setup

### Required Environment Variable

Add to `.env` or Render dashboard:

```bash
SUPABASE_JWT_SECRET=your-jwt-secret-here
```

**Where to find it:**
1. Go to Supabase Dashboard
2. Settings → API → JWT Settings
3. Copy the "JWT Secret" (starts with `eyJh...`)

---

## Installation

Install the new dependency:

```bash
cd services/api
pip install python-jose[cryptography]
# or
pip install -r requirements.txt
```

---

## Testing with Bearer Tokens

### 1. Get a JWT Token (Supabase Auth)

In your Flutter app after login:
```dart
final token = Supabase.instance.client.auth.currentSession?.accessToken;
```

Or use Supabase JavaScript to get a token for testing:
```javascript
const { data } = await supabase.auth.signInWithPassword({
  email: 'test@example.com',
  password: 'password'
});
const token = data.session.access_token;
```

### 2. Call Protected Endpoints

```bash
# Old way (will fail with 401)
curl -X GET http://localhost:8000/profile/household \
  -H "X-User-Id: 00000000-0000-0000-0000-000000000001"

# New way (with Bearer token)
curl -X GET http://localhost:8000/profile/household \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

### 3. Response Codes

| Code | Meaning |
|------|---------|
| 200 | Success - valid token |
| 401 | Unauthorized - missing or invalid token |
| 403 | Forbidden - valid token but wrong resource |
| 500 | Server error |

---

## Migration Guide for Flutter

### Before (Hardcoded Headers)
```dart
final response = await apiClient.get(
  '/profile/household',
  headers: {
    'X-User-Id': '00000000-0000-0000-0000-000000000001',
    'X-User-Email': 'demo@savo.app',
  },
);
```

### After (Bearer Token)
```dart
final token = Supabase.instance.client.auth.currentSession?.accessToken;

final response = await apiClient.get(
  '/profile/household',
  headers: {
    'Authorization': 'Bearer $token',
  },
);
```

---

## Security Benefits

✅ **No Trust in Client:** Server validates JWT signature  
✅ **Auto-Expiry:** Tokens expire (typically 1 hour)  
✅ **Cryptographic:** HMAC-SHA256 signature verification  
✅ **Row-Level Security:** User ID extracted from trusted JWT  
✅ **Production-Ready:** Industry standard authentication

---

## Troubleshooting

### "Missing authorization header"
- Ensure `Authorization: Bearer <token>` header is sent
- Check token is not empty

### "Invalid token"
- Verify `SUPABASE_JWT_SECRET` is set correctly
- Token might be expired (default: 1 hour)
- Refresh token via Supabase SDK

### "Server configuration error"
- `SUPABASE_JWT_SECRET` not set in environment
- Add to `.env` or Render environment variables

---

## Next Steps

- ✅ Phase A: Database migration complete
- ✅ Phase B: JWT authentication complete
- ⏳ Phase C: Implement new API endpoints (`GET /profile/full`, etc.)
- ⏳ Phase D: Update Flutter to use Supabase SDK + Bearer tokens
