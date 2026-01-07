"""
Decision Intelligence API Test Suite
Tests all 9 Decision API endpoints following DECISION_API_TEST_PLAN.md
"""
import os
import sys
import requests
import json
from datetime import datetime
from typing import Dict, Any, List
from dotenv import load_dotenv

load_dotenv()

# Configuration
# Note: decision router already has /api/decision prefix, so we access it without duplication
BASE_URL = "https://savo-backend.onrender.com"
DECISION_PREFIX = "/api/decision"
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

# Test results
test_results = []
total_tests = 0
passed_tests = 0
failed_tests = 0


def log_result(test_name: str, passed: bool, details: str = "", response_time: float = 0):
    """Log test result"""
    global total_tests, passed_tests, failed_tests
    
    total_tests += 1
    if passed:
        passed_tests += 1
        status = "✅ PASS"
    else:
        failed_tests += 1
        status = "❌ FAIL"
    
    result = {
        "test": test_name,
        "status": status,
        "response_time_ms": round(response_time * 1000, 2),
        "details": details,
        "timestamp": datetime.now().isoformat()
    }
    test_results.append(result)
    
    print(f"{status} - {test_name} ({result['response_time_ms']}ms)")
    if details:
        print(f"   {details}")


def get_auth_token() -> str:
    """Get Supabase auth token for testing"""
    # Try to get from environment first
    token = os.getenv("SUPABASE_TEST_TOKEN")
    if token:
        return token
    
    # Otherwise, try to login
    email = os.getenv("TEST_USER_EMAIL", "test@example.com")
    password = os.getenv("TEST_USER_PASSWORD", "testpassword123")
    
    try:
        response = requests.post(
            f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
            headers={
                "apikey": SUPABASE_ANON_KEY,
                "Content-Type": "application/json"
            },
            json={
                "email": email,
                "password": password
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            return data.get("access_token")
        else:
            print(f"⚠️  Auth failed: {response.status_code}")
            print(f"Response: {response.text}")
            return None
    except Exception as e:
        print(f"⚠️  Auth error: {e}")
        return None


def test_health_check():
    """Test 1: Health Check"""
    try:
        start = datetime.now()
        response = requests.get(f"{BASE_URL}{DECISION_PREFIX}/health", timeout=10)
        elapsed = (datetime.now() - start).total_seconds()
        
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "healthy":
                log_result("Health Check", True, "Service is healthy", elapsed)
                return True
            else:
                log_result("Health Check", False, f"Unexpected status: {data.get('status')}", elapsed)
        else:
            log_result("Health Check", False, f"Status code: {response.status_code}", elapsed)
        return False
    except Exception as e:
        log_result("Health Check", False, f"Error: {str(e)}", 0)
        return False


def test_get_rules(token: str):
    """Test 2: Get Decision Rules"""
    try:
        start = datetime.now()
        response = requests.get(
            f"{BASE_URL}{DECISION_PREFIX}/rules",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        elapsed = (datetime.now() - start).total_seconds()
        
        if response.status_code == 200:
            data = response.json()
            rules_count = data.get("count", 0)
            if rules_count >= 5:
                log_result("Get Decision Rules", True, f"Found {rules_count} rules", elapsed)
                return True
            else:
                log_result("Get Decision Rules", False, f"Expected 5+ rules, got {rules_count}", elapsed)
        else:
            log_result("Get Decision Rules", False, f"Status code: {response.status_code}", elapsed)
        return False
    except Exception as e:
        log_result("Get Decision Rules", False, f"Error: {str(e)}", 0)
        return False


def test_evaluate_ingredient(token: str, ingredient_id: str = None):
    """Test 3: Evaluate Single Ingredient"""
    # Use a dummy UUID if no ingredient ID provided
    if not ingredient_id:
        ingredient_id = "00000000-0000-0000-0000-000000000001"
    
    try:
        start = datetime.now()
        response = requests.post(
            f"{BASE_URL}/evaluate-ingredient",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            json={
                "ingredient_id": ingredient_id,
                "context": {
                    "freshness_score": 0.85,
                    "days_to_expiry": 1,
                    "recognition_confidence": 0.90,
                    "in_user_inventory": True
                }
            },
            timeout=10
        )
        elapsed = (datetime.now() - start).total_seconds()
        
        if response.status_code == 200:
            data = response.json()
            if "recommended_action" in data and "confidence" in data:
                action = data.get("recommended_action")
                confidence = data.get("confidence")
                log_result("Evaluate Ingredient", True, 
                          f"Action: {action}, Confidence: {confidence}", elapsed)
                return True
            else:
                log_result("Evaluate Ingredient", False, "Missing required fields", elapsed)
        else:
            log_result("Evaluate Ingredient", False, 
                      f"Status code: {response.status_code} - {response.text[:100]}", elapsed)
        return False
    except Exception as e:
        log_result("Evaluate Ingredient", False, f"Error: {str(e)}", 0)
        return False


def test_evaluate_inventory(token: str):
    """Test 4: Evaluate Inventory (Batch)"""
    try:
        start = datetime.now()
        response = requests.post(
            f"{BASE_URL}{DECISION_PREFIX}/evaluate-inventory",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            json={
                "inventory_items": [
                    {
                        "ingredient_id": "00000000-0000-0000-0000-000000000001",
                        "freshness_score": 0.85,
                        "days_to_expiry": 1
                    },
                    {
                        "ingredient_id": "00000000-0000-0000-0000-000000000002",
                        "freshness_score": 0.95,
                        "days_to_expiry": 10
                    }
                ]
            },
            timeout=15
        )
        elapsed = (datetime.now() - start).total_seconds()
        
        if response.status_code == 200:
            data = response.json()
            if "decisions" in data and "summary" in data:
                count = len(data["decisions"])
                log_result("Evaluate Inventory", True, f"Evaluated {count} items", elapsed)
                return True
            else:
                log_result("Evaluate Inventory", False, "Missing required fields", elapsed)
        else:
            log_result("Evaluate Inventory", False, 
                      f"Status code: {response.status_code} - {response.text[:100]}", elapsed)
        return False
    except Exception as e:
        log_result("Evaluate Inventory", False, f"Error: {str(e)}", 0)
        return False


def test_get_recommended_actions(token: str):
    """Test 5: Get Recommended Actions (History)"""
    try:
        start = datetime.now()
        response = requests.get(
            f"{BASE_URL}{DECISION_PREFIX}/recommended-actions",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        elapsed = (datetime.now() - start).total_seconds()
        
        if response.status_code == 200:
            data = response.json()
            if "actions" in data:
                count = len(data["actions"])
                log_result("Get Recommended Actions", True, f"Found {count} actions", elapsed)
                return True
            else:
                log_result("Get Recommended Actions", False, "Missing 'actions' field", elapsed)
        else:
            log_result("Get Recommended Actions", False, 
                      f"Status code: {response.status_code}", elapsed)
        return False
    except Exception as e:
        log_result("Get Recommended Actions", False, f"Error: {str(e)}", 0)
        return False


def test_get_stats(token: str):
    """Test 7: Get User Statistics"""
    try:
        start = datetime.now()
        response = requests.get(
            f"{BASE_URL}{DECISION_PREFIX}/stats",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        elapsed = (datetime.now() - start).total_seconds()
        
        if response.status_code == 200:
            data = response.json()
            if "total_recommendations" in data:
                total = data.get("total_recommendations", 0)
                rate = data.get("overall_acceptance_rate", 0)
                log_result("Get User Stats", True, 
                          f"Total: {total}, Acceptance: {rate:.2%}", elapsed)
                return True
            else:
                log_result("Get User Stats", False, "Missing required fields", elapsed)
        else:
            log_result("Get User Stats", False, 
                      f"Status code: {response.status_code}", elapsed)
        return False
    except Exception as e:
        log_result("Get User Stats", False, f"Error: {str(e)}", 0)
        return False


def test_error_handling(token: str):
    """Test 9: Error Handling"""
    tests_passed = 0
    
    # Test 1: Invalid ingredient ID
    try:
        start = datetime.now()
        response = requests.post(
            f"{BASE_URL}{DECISION_PREFIX}/evaluate-ingredient",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            json={"ingredient_id": "invalid-uuid"},
            timeout=10
        )
        elapsed = (datetime.now() - start).total_seconds()
        
        if response.status_code in [400, 422]:
            log_result("Error Handling - Invalid ID", True, 
                      f"Correctly returned {response.status_code}", elapsed)
            tests_passed += 1
        else:
            log_result("Error Handling - Invalid ID", False, 
                      f"Expected 400/422, got {response.status_code}", elapsed)
    except Exception as e:
        log_result("Error Handling - Invalid ID", False, f"Error: {str(e)}", 0)
    
    # Test 2: Missing fields
    try:
        start = datetime.now()
        response = requests.post(
            f"{BASE_URL}{DECISION_PREFIX}/evaluate-ingredient",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            json={},
            timeout=10
        )
        elapsed = (datetime.now() - start).total_seconds()
        
        if response.status_code == 422:
            log_result("Error Handling - Missing Fields", True, 
                      "Correctly returned 422", elapsed)
            tests_passed += 1
        else:
            log_result("Error Handling - Missing Fields", False, 
                      f"Expected 422, got {response.status_code}", elapsed)
    except Exception as e:
        log_result("Error Handling - Missing Fields", False, f"Error: {str(e)}", 0)
    
    # Test 3: Unauthorized access
    try:
        start = datetime.now()
        response = requests.get(f"{BASE_URL}{DECISION_PREFIX}/rules", timeout=10)
        elapsed = (datetime.now() - start).total_seconds()
        
        if response.status_code == 401:
            log_result("Error Handling - Unauthorized", True, 
                      "Correctly returned 401", elapsed)
            tests_passed += 1
        else:
            log_result("Error Handling - Unauthorized", False, 
                      f"Expected 401, got {response.status_code}", elapsed)
    except Exception as e:
        log_result("Error Handling - Unauthorized", False, f"Error: {str(e)}", 0)
    
    return tests_passed == 3


def print_summary():
    """Print test summary"""
    print("\n" + "="*70)
    print("DECISION API TEST SUMMARY")
    print("="*70)
    print(f"Total Tests: {total_tests}")
    print(f"✅ Passed: {passed_tests}")
    print(f"❌ Failed: {failed_tests}")
    print(f"Success Rate: {(passed_tests/total_tests*100) if total_tests > 0 else 0:.1f}%")
    print("="*70)
    
    # Calculate average response time
    response_times = [r["response_time_ms"] for r in test_results if r["response_time_ms"] > 0]
    if response_times:
        avg_time = sum(response_times) / len(response_times)
        print(f"Average Response Time: {avg_time:.2f}ms")
    
    # Save results to file
    with open("decision_api_test_results.json", "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total": total_tests,
                "passed": passed_tests,
                "failed": failed_tests,
                "success_rate": round(passed_tests/total_tests*100, 2) if total_tests > 0 else 0
            },
            "tests": test_results
        }, f, indent=2)
    
    print("\n✅ Test results saved to: decision_api_test_results.json")


def main():
    """Run all tests"""
    print("🧪 DECISION INTELLIGENCE API TEST SUITE")
    print("="*70)
    print(f"Base URL: {BASE_URL}{DECISION_PREFIX}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70 + "\n")
    
    # Get auth token
    print("🔐 Authenticating...")
    token = get_auth_token()
    
    if not token:
        print("❌ Failed to get auth token. Tests requiring auth will be skipped.")
        print("Please set SUPABASE_TEST_TOKEN, or TEST_USER_EMAIL and TEST_USER_PASSWORD in .env")
    else:
        print("✅ Authentication successful\n")
    
    # Run tests
    print("Running tests...\n")
    
    # Test 1: Health Check (no auth needed)
    test_health_check()
    
    if token:
        # Tests requiring authentication
        test_get_rules(token)
        test_evaluate_ingredient(token)
        test_evaluate_inventory(token)
        test_get_recommended_actions(token)
        test_get_stats(token)
        test_error_handling(token)
    else:
        print("\n⚠️  Skipping authenticated tests (no token)")
    
    # Print summary
    print_summary()
    
    # Exit code based on results
    sys.exit(0 if failed_tests == 0 else 1)


if __name__ == "__main__":
    main()
