#!/usr/bin/env python3
"""
Comprehensive fix: Add get_or_create_user to ALL profile write endpoints
"""

import re

def fix_profile_endpoints():
    filepath = "services/api/app/api/routes/profile.py"
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Pattern to find write endpoints without get_or_create_user
    # Look for @router.post or @router.patch followed by function that has user_id parameter
    # but doesn't call get_or_create_user in the try block
    
    endpoints_to_fix = [
        ("@router.post(\"/family-members\")", "add_family_member"),
        ("@router.patch(\"/family-members/{member_id}\")", "update_family_member"),
        ("@router.delete(\"/family-members/{member_id}\")", "delete_family_member"),
        ("@router.patch(\"/allergens\")", "update_allergens"),
        ("@router.patch(\"/dietary\")", "update_dietary"),
        ("@router.patch(\"/preferences\")", "update_preferences"),
        ("@router.patch(\"/language\")", "update_language"),
        ("@router.patch(\"/complete\")", "complete_onboarding"),
    ]
    
    for route_decorator, func_name in endpoints_to_fix:
        # Find the function
        pattern = rf"({re.escape(route_decorator)}.*?async def {func_name}\(.*?\):\s+\"\"\".*?\"\"\")\s+try:\s+"
        
        def add_user_creation(match):
            return match.group(1) + "\n    try:\n        # Ensure user exists\n        await get_or_create_user(user_id)\n        "
        
        content = re.sub(pattern, add_user_creation, content, flags=re.DOTALL)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ Fixed all profile endpoints")

if __name__ == "__main__":
    fix_all_endpoints()
