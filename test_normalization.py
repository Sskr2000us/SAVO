"""
Test the actual normalization logic from planning.py
"""

# Simulate the normalization that happens in planning.py
def normalize_members(members):
    normalized_members = []
    for m in members:
        if not isinstance(m, dict):
            continue
        # Ensure allergens key exists and is not None (Golden Rule requires explicit declaration)
        if "allergens" not in m or m.get("allergens") is None:
            m = {**m, "allergens": []}
        normalized_members.append(m)
    return normalized_members

# Test cases
test_members_1 = [
    {"name": "John", "allergens": None},  # NULL value from database
    {"name": "Jane", "allergens": ["dairy"]}
]

test_members_2 = [
    {"name": "John"},  # Missing allergens key
    {"name": "Jane", "allergens": ["dairy"]}
]

test_members_3 = [
    {"name": "John", "allergens": []},  # Explicit empty array
    {"name": "Jane", "allergens": ["dairy"]}
]

print("=" * 60)
print("Testing Member Normalization")
print("=" * 60)

for i, members in enumerate([test_members_1, test_members_2, test_members_3], 1):
    print(f"\nTest Case {i}:")
    print(f"Input: {members}")
    normalized = normalize_members(members)
    print(f"Output: {normalized}")
    
    # Check all have allergens as list
    all_have_allergens = all(
        isinstance(m.get("allergens"), list) for m in normalized
    )
    print(f"All have allergens as list: {all_have_allergens}")
