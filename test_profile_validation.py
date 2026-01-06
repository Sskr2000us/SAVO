"""
Test script to check profile validation logic
"""
import sys
import os

# Add the services directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'services', 'api'))

from app.core.safety_constraints import validate_profile_completeness, SAVOGoldenRule

# Test case 1: Members with allergens = []
test_profile_1 = {
    "household": {"name": "Test Family"},
    "members": [
        {"name": "John", "allergens": []},
        {"name": "Jane", "allergens": ["dairy"]}
    ]
}

# Test case 2: Members with allergens = None
test_profile_2 = {
    "household": {"name": "Test Family"},
    "members": [
        {"name": "John", "allergens": None},
        {"name": "Jane", "allergens": ["dairy"]}
    ]
}

# Test case 3: Members without allergens key
test_profile_3 = {
    "household": {"name": "Test Family"},
    "members": [
        {"name": "John"},
        {"name": "Jane", "allergens": ["dairy"]}
    ]
}

# Test case 4: Empty members list
test_profile_4 = {
    "household": {"name": "Test Family"},
    "members": []
}

print("=" * 60)
print("Testing Profile Validation")
print("=" * 60)

for i, profile in enumerate([test_profile_1, test_profile_2, test_profile_3, test_profile_4], 1):
    print(f"\nTest Case {i}:")
    print(f"Profile: {profile}")
    is_complete, missing = validate_profile_completeness(profile)
    result = SAVOGoldenRule.check_before_generate(profile)
    print(f"  Is Complete: {is_complete}")
    print(f"  Missing: {missing}")
    print(f"  Can Proceed: {result['can_proceed']}")
    print(f"  Action: {result['action']}")
    if result.get('message'):
        print(f"  Message: {result['message']}")
    print()
