"""
Test script for family member creation E2E flow
Tests the complete flow from API request to database storage
"""

import asyncio
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

# Configuration
BASE_URL = os.getenv("BACKEND_URL", "https://savo-ynp1.onrender.com")
TEST_USER_ID = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"  # Replace with actual test user
TEST_TOKEN = os.getenv("TEST_JWT_TOKEN")  # Set in .env for testing

async def test_family_member_creation():
    """Test the complete family member creation flow"""
    
    if not TEST_TOKEN:
        print("❌ TEST_JWT_TOKEN not set in environment")
        print("   Please set TEST_JWT_TOKEN with a valid Supabase JWT token")
        return
    
    headers = {
        "Authorization": f"Bearer {TEST_TOKEN}",
        "Content-Type": "application/json"
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        
        # Step 1: Check if household profile exists
        print("\n📋 Step 1: Checking household profile...")
        try:
            response = await client.get(f"{BASE_URL}/profile/household", headers=headers)
            print(f"   Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                if data.get("exists"):
                    print("   ✅ Household profile exists")
                else:
                    print("   ⚠️  Household profile does not exist")
                    print("   Creating household profile...")
                    
                    # Create household profile
                    household_data = {
                        "region": "US",
                        "culture": "western",
                        "primary_language": "en-US",
                        "measurement_system": "imperial"
                    }
                    
                    create_response = await client.post(
                        f"{BASE_URL}/profile/household",
                        headers=headers,
                        json=household_data
                    )
                    
                    if create_response.status_code in [200, 201]:
                        print("   ✅ Household profile created")
                    else:
                        print(f"   ❌ Failed to create household: {create_response.status_code}")
                        print(f"      {create_response.text}")
                        return
            else:
                print(f"   ❌ Failed to check household: {response.status_code}")
                print(f"      {response.text}")
                return
                
        except Exception as e:
            print(f"   ❌ Error: {e}")
            return
        
        # Step 2: Create a test family member
        print("\n👤 Step 2: Creating test family member...")
        
        member_data = {
            "name": "Test Member",
            "age": 30,
            "age_category": "adult",
            "dietary_restrictions": ["vegetarian"],
            "allergens": ["peanuts"],
            "health_conditions": [],
            "medical_dietary_needs": ["low_sodium"],
            "spice_tolerance": "medium",
            "food_preferences": ["pasta"],
            "food_dislikes": ["mushrooms"],
            "display_order": 0
        }
        
        try:
            response = await client.post(
                f"{BASE_URL}/profile/family-members",
                headers=headers,
                json=member_data
            )
            
            print(f"   Status: {response.status_code}")
            
            if response.status_code in [200, 201]:
                result = response.json()
                print("   ✅ Family member created successfully")
                print(f"      Member ID: {result.get('member', {}).get('id')}")
                print(f"      Name: {result.get('member', {}).get('name')}")
                member_id = result.get('member', {}).get('id')
            else:
                print(f"   ❌ Failed to create family member: {response.status_code}")
                print(f"      {response.text}")
                return
                
        except Exception as e:
            print(f"   ❌ Error: {e}")
            return
        
        # Step 3: Retrieve family members
        print("\n📖 Step 3: Retrieving all family members...")
        
        try:
            response = await client.get(
                f"{BASE_URL}/profile/family-members",
                headers=headers
            )
            
            print(f"   Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                members = data.get('members', [])
                print(f"   ✅ Found {len(members)} family member(s)")
                
                for member in members:
                    print(f"      - {member.get('name')} (age {member.get('age')})")
                    print(f"        Allergens: {member.get('allergens', [])}")
                    print(f"        Dietary: {member.get('dietary_restrictions', [])}")
            else:
                print(f"   ❌ Failed to retrieve members: {response.status_code}")
                print(f"      {response.text}")
                
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        # Step 4: Get full profile
        print("\n🔍 Step 4: Getting full profile...")
        
        try:
            response = await client.get(
                f"{BASE_URL}/profile/full",
                headers=headers
            )
            
            print(f"   Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print("   ✅ Full profile retrieved")
                profile_data = data.get('data', {})
                
                # Check members in full profile
                members = profile_data.get('members', [])
                print(f"      Members in full profile: {len(members)}")
                
                # Check aggregated allergens
                allergens = profile_data.get('allergens', {})
                print(f"      Aggregated allergens: {allergens.get('declared_allergens', [])}")
            else:
                print(f"   ❌ Failed to get full profile: {response.status_code}")
                print(f"      {response.text}")
                
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        # Step 5: Clean up (delete test member)
        if member_id:
            print(f"\n🧹 Step 5: Cleaning up (deleting test member {member_id})...")
            
            try:
                response = await client.delete(
                    f"{BASE_URL}/profile/family-members/{member_id}",
                    headers=headers
                )
                
                print(f"   Status: {response.status_code}")
                
                if response.status_code == 200:
                    print("   ✅ Test member deleted successfully")
                else:
                    print(f"   ⚠️  Could not delete test member: {response.status_code}")
                    
            except Exception as e:
                print(f"   ❌ Error: {e}")
    
    print("\n" + "="*60)
    print("✅ E2E Test Complete")
    print("="*60)

if __name__ == "__main__":
    print("="*60)
    print("SAVO Family Member E2E Test")
    print("="*60)
    print(f"Backend URL: {BASE_URL}")
    
    asyncio.run(test_family_member_creation())
