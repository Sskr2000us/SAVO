# Comprehensive Fix for All Profile Endpoints

## Problem
Every profile endpoint needs to ensure the user exists in the database before any write operations.

## Solution Applied
Added `await get_or_create_user(user_id)` to ALL write endpoints:

1. POST /profile/household ✅ (already fixed in commit 134d37b)
2. PATCH /profile/household - NEEDS FIX
3. POST /profile/family-members - NEEDS FIX  
4. PATCH /profile/family-members/{member_id} - NEEDS FIX
5. DELETE /profile/family-members/{member_id} - NEEDS FIX
6. PATCH /profile/allergens - NEEDS FIX
7. PATCH /profile/dietary - NEEDS FIX
8. PATCH /profile/preferences - NEEDS FIX
9. PATCH /profile/language - NEEDS FIX
10. PATCH /profile/complete - NEEDS FIX

## Implementation Pattern

```python
@router.patch("/endpoint")
async def update_something(
    data: SomeModel,
    user_id: str = Depends(get_current_user)
):
    try:
        # ALWAYS ensure user exists first
        await get_or_create_user(user_id)
        
        # Then proceed with operation
        # ...
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

## Status
- Created this fix plan
- Will apply to all remaining endpoints in next commit
