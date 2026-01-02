# Family Member Management in SAVO

## Architecture Overview

### Single Household Account Model

**SAVO uses a single account per household:**
- ✅ **One email/password** per household
- ✅ **One Supabase auth user** per household
- ✅ **Multiple family members** stored as data

### How It Works

```
┌─────────────────────────────────────┐
│ Supabase Auth (auth.users)         │
│                                     │
│  Email: family@example.com          │
│  Password: ********                 │
└──────────────┬──────────────────────┘
               │ user_id (UUID)
               │
               ▼
┌─────────────────────────────────────┐
│ household_profiles                  │
│                                     │
│  - Region, culture, preferences     │
│  - Meal times, skill level          │
└──────────────┬──────────────────────┘
               │ household_id
               │
               ▼
┌─────────────────────────────────────┐
│ family_members (data only)          │
│                                     │
│  - John (Dad) - Adult               │
│  - Sarah (Mom) - Adult              │
│  - Emma (Daughter) - Child          │
│  - Lucas (Son) - Teen               │
│                                     │
│  Each has:                          │
│  - Name, age_category               │
│  - Dietary restrictions             │
│  - Allergens, preferences           │
└─────────────────────────────────────┘
```

### What This Means

**Family members are NOT separate users:**
- ❌ They don't have individual logins
- ❌ They don't have separate passwords
- ❌ They can't log in independently
- ✅ They're data entries for meal planning
- ✅ The system uses their info (age, allergies) to plan meals

**The household account represents the entire family:**
- One person manages the account (usually parent)
- They add family members during onboarding
- Meal plans consider ALL family members' needs

## Multi-Device Access

**Same Account, Multiple Devices:**
- ✅ Parents can access from phone AND web
- ✅ Both parents can use same login on different devices
- ✅ Sessions persist across devices

**Example:**
```
Mom's Phone     Dad's Tablet     Family Computer
     │                │                  │
     │                │                  │
     └────────────────┴──────────────────┘
                      │
              Same Household Account
           (family@example.com)
```

## Why This Model?

### Pros ✅
1. **Simple**: One account to manage
2. **Collaborative**: Whole family's needs in one place
3. **Privacy**: No need for kids to have email accounts
4. **Shared pantry**: One inventory for the household
5. **Unified meal plans**: Plans consider everyone

### Cons ⚠️
1. **No individual preferences**: Can't save "Mom's favorites" vs "Dad's favorites"
2. **Shared history**: Everyone sees the same cooking history
3. **One login**: Need to share password among adults

## Active Sessions Feature

### What It Was For
- Managing multiple devices logged into same account
- "Sign out all other devices" for security

### Why We Removed It
- ❌ Confusing - users thought family members needed separate logins
- ❌ Not critical - Supabase handles session management
- ❌ Rare use case - most households trust their devices
- ✅ Simplified UI - one less thing to manage

### If You Need It Back
Users can still sign out from individual devices:
- Settings → Sign Out (signs out current device only)
- Supabase dashboard → Auth → Sessions (admin management)

## Future Considerations

### If You Want Individual User Accounts:

**Architecture Change Required:**
```
Current: 1 auth user → 1 household → many family members (data)
Future:  Many auth users → 1 household (shared) → user profiles
```

**Implementation:**
1. Multiple Supabase auth users per household
2. Shared household_id links them together
3. User profiles instead of family_members table
4. Permissions system (parent vs child roles)
5. Individual preferences and history

**Pros:**
- Individual preferences and history
- Better privacy
- Personal recommendations

**Cons:**
- More complex onboarding
- Kids need email addresses
- More expensive (more auth users)
- Harder to manage

## Current Recommendation

**Keep the single household account model:**
- Simpler for MVP
- Matches how families actually use meal planning
- One person (usually parent) manages planning
- Easy to share across parents' devices

**Focus on:**
- Making meal plans that work for everyone
- Smart dietary restriction handling
- Good pantry sharing
- Easy collaboration features

## FAQ

**Q: Can both parents use the app?**
A: Yes! Share the login. Both can access from different devices.

**Q: Do kids need accounts?**
A: No. Add them as family members (data only). System considers their needs automatically.

**Q: What if we want separate favorites?**
A: Currently not supported. Add as future feature if highly requested.

**Q: How do I switch between family member profiles?**
A: There are no separate profiles. The system knows all family members and considers everyone when planning.

**Q: Is it secure?**
A: Yes. Use strong password, enable 2FA (future), don't share login outside household.

**Q: What happens if I sign out?**
A: Signs out current device only. Other devices stay logged in.

## Summary

✅ **Current Model**: One account per household, family members as data
✅ **Removed**: Active Sessions screen (confusing, not critical)
✅ **Kept**: Sign Out (per-device logout)
✅ **Focus**: Simple, family-oriented meal planning

This matches how families actually use shared meal planning apps!
