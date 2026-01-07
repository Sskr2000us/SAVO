# Decision Intelligence API Test Plan

## 🎯 Overview
Test all 9 Decision Intelligence API endpoints deployed to Render.

**Base URL**: `https://savo-backend.onrender.com/api/decision`

## 📋 Prerequisites

1. Backend deployed successfully on Render (with numpy fix)
2. Valid Supabase auth token
3. API testing tool (Postman, curl, or Thunder Client)
4. Migration 007 applied (8 tables + 5 seed rules)

## 🔐 Authentication

All endpoints require Bearer token authentication.

### Get Auth Token:
```bash
# Login via Supabase
curl -X POST https://YOUR_SUPABASE_PROJECT.supabase.co/auth/v1/token?grant_type=password \
  -H "apikey: YOUR_ANON_KEY" \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "password123"}'

# Extract access_token from response
```

Set token in headers:
```
Authorization: Bearer YOUR_ACCESS_TOKEN
```

---

## 🧪 Test Cases

### 1. Health Check

**Endpoint**: `GET /api/decision/health`  
**Purpose**: Verify service is running

```bash
curl https://savo-backend.onrender.com/api/decision/health
```

**Expected Response**:
```json
{
  "status": "healthy",
  "service": "decision_intelligence",
  "timestamp": "2026-01-07T12:00:00Z"
}
```

**✅ Pass Criteria**:
- Status code: 200
- Response contains "status": "healthy"

---

### 2. Get Decision Rules

**Endpoint**: `GET /api/decision/rules`  
**Purpose**: List all active decision rules

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  https://savo-backend.onrender.com/api/decision/rules
```

**Expected Response**:
```json
{
  "rules": [
    {
      "id": "uuid",
      "rule_id": "DI_COOK_NOW_001",
      "rule_name": "Cook Immediately - Peak Freshness",
      "action": "cook_now",
      "confidence_min": 0.85,
      "auto_apply": true,
      "priority": 10,
      "times_applied": 0,
      "acceptance_rate": null
    },
    // ... 4 more rules
  ],
  "count": 5
}
```

**✅ Pass Criteria**:
- Status code: 200
- Returns 5 seeded rules
- Each rule has required fields
- Rules sorted by priority (ascending)

---

### 3. Evaluate Single Ingredient

**Endpoint**: `POST /api/decision/evaluate-ingredient`  
**Purpose**: Get action recommendation for one ingredient

```bash
curl -X POST \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "ingredient_id": "TOMATO_UUID",
    "context": {
      "freshness_score": 0.85,
      "days_to_expiry": 1,
      "recognition_confidence": 0.90,
      "in_user_inventory": true
    }
  }' \
  https://savo-backend.onrender.com/api/decision/evaluate-ingredient
```

**Expected Response**:
```json
{
  "ingredient_id": "TOMATO_UUID",
  "recommended_action": "cook_now",
  "confidence": 0.92,
  "explanation": "This ingredient is at peak freshness and should be used today to avoid waste.",
  "matched_rule": {
    "rule_id": "DI_COOK_NOW_001",
    "rule_name": "Cook Immediately - Peak Freshness"
  },
  "urgency": "high",
  "will_auto_apply": true
}
```

**Test Variations**:
1. High freshness + near expiry → "cook_now"
2. Low freshness → "store_better" or "discard"
3. Good condition + far expiry → "monitor"

**✅ Pass Criteria**:
- Status code: 200
- Returns valid action enum
- Confidence between 0-1
- Explanation not empty
- Urgency level present

---

### 4. Evaluate Inventory (Batch)

**Endpoint**: `POST /api/decision/evaluate-inventory`  
**Purpose**: Get prioritized actions for multiple ingredients

```bash
curl -X POST \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "inventory_items": [
      {
        "ingredient_id": "TOMATO_UUID",
        "freshness_score": 0.85,
        "days_to_expiry": 1
      },
      {
        "ingredient_id": "POTATO_UUID",
        "freshness_score": 0.95,
        "days_to_expiry": 10
      }
    ]
  }' \
  https://savo-backend.onrender.com/api/decision/evaluate-inventory
```

**Expected Response**:
```json
{
  "decisions": [
    {
      "ingredient_id": "TOMATO_UUID",
      "recommended_action": "cook_now",
      "confidence": 0.92,
      "urgency": "high",
      "explanation": "..."
    },
    {
      "ingredient_id": "POTATO_UUID",
      "recommended_action": "monitor",
      "confidence": 0.80,
      "urgency": "low",
      "explanation": "..."
    }
  ],
  "summary": {
    "total_items": 2,
    "high_urgency": 1,
    "medium_urgency": 0,
    "low_urgency": 1
  }
}
```

**✅ Pass Criteria**:
- Status code: 200
- Decisions sorted by urgency (high → low)
- Summary counts match decisions
- All items evaluated

---

### 5. Get Recommended Actions (History)

**Endpoint**: `GET /api/decision/recommended-actions`  
**Purpose**: Retrieve user's action history with filters

```bash
# Get all actions
curl -H "Authorization: Bearer YOUR_TOKEN" \
  "https://savo-backend.onrender.com/api/decision/recommended-actions"

# Filter by action type
curl -H "Authorization: Bearer YOUR_TOKEN" \
  "https://savo-backend.onrender.com/api/decision/recommended-actions?action=cook_now"

# Filter by response status
curl -H "Authorization: Bearer YOUR_TOKEN" \
  "https://savo-backend.onrender.com/api/decision/recommended-actions?pending=true"

# With pagination
curl -H "Authorization: Bearer YOUR_TOKEN" \
  "https://savo-backend.onrender.com/api/decision/recommended-actions?limit=10&offset=0"
```

**Expected Response**:
```json
{
  "actions": [
    {
      "id": "uuid",
      "ingredient_name": "Tomato",
      "recommended_action": "cook_now",
      "confidence": 0.92,
      "reason": "...",
      "was_auto_applied": true,
      "user_response": "accepted",
      "recommended_at": "2026-01-07T10:00:00Z",
      "responded_at": "2026-01-07T10:05:00Z"
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0
}
```

**Test Variations**:
1. No filters → All actions
2. Filter by action type → Only matching actions
3. Filter pending only → Actions without user response
4. Pagination → Correct limits applied

**✅ Pass Criteria**:
- Status code: 200
- Returns array of actions
- Filters work correctly
- Pagination metadata accurate

---

### 6. Apply Action / Provide Feedback

**Endpoint**: `POST /api/decision/apply-action`  
**Purpose**: Record user's response to recommendation

```bash
curl -X POST \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "action_id": "ACTION_UUID",
    "user_response": "accepted",
    "user_final_action": "cook_now",
    "feedback_notes": "Made pasta sauce"
  }' \
  https://savo-backend.onrender.com/api/decision/apply-action
```

**Expected Response**:
```json
{
  "success": true,
  "action_id": "ACTION_UUID",
  "message": "Feedback recorded successfully",
  "learning_triggered": true
}
```

**Test Variations**:
1. Accepted → user_response: "accepted"
2. Rejected → user_response: "rejected"
3. Modified → user_response: "modified" + different final_action
4. Ignored → user_response: "ignored"

**✅ Pass Criteria**:
- Status code: 200
- Feedback saved to database
- Rule statistics updated (times_applied, times_accepted)
- Learning feedback created if needed

---

### 7. Get User Statistics

**Endpoint**: `GET /api/decision/stats`  
**Purpose**: Retrieve user's decision intelligence metrics

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  https://savo-backend.onrender.com/api/decision/stats
```

**Expected Response**:
```json
{
  "user_id": "uuid",
  "total_recommendations": 45,
  "total_accepted": 32,
  "total_rejected": 8,
  "total_ignored": 5,
  "overall_acceptance_rate": 0.71,
  "acceptance_by_action": {
    "cook_now": 0.85,
    "store_better": 0.60,
    "monitor": 0.75,
    "substitute": 0.80,
    "discard": 0.70
  },
  "auto_applied_count": 20,
  "avg_response_time_seconds": 120,
  "period": "all_time"
}
```

**✅ Pass Criteria**:
- Status code: 200
- All metrics calculated correctly
- Acceptance rate = accepted / (accepted + rejected)
- Breakdown by action type present

---

### 8. Create Decision Rule (Admin)

**Endpoint**: `POST /api/decision/rules`  
**Purpose**: Add new decision rule

```bash
curl -X POST \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "rule_id": "DI_TEST_001",
    "rule_name": "Test Rule",
    "rule_description": "Test decision rule",
    "conditions": {
      "freshness_score_min": 0.70,
      "days_to_expiry_max": 3
    },
    "action": "cook_now",
    "explanation_template": "Test explanation",
    "confidence_min": 0.75,
    "auto_apply": false,
    "priority": 50
  }' \
  https://savo-backend.onrender.com/api/decision/rules
```

**Expected Response**:
```json
{
  "success": true,
  "rule_id": "uuid",
  "message": "Decision rule created successfully"
}
```

**✅ Pass Criteria**:
- Status code: 201
- Rule created in database
- Returns rule UUID
- Validation errors for invalid data

---

### 9. Error Handling Tests

Test error scenarios:

```bash
# 1. Invalid ingredient ID
curl -X POST \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"ingredient_id": "invalid-uuid"}' \
  https://savo-backend.onrender.com/api/decision/evaluate-ingredient

# Expected: 400 Bad Request

# 2. Missing required fields
curl -X POST \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}' \
  https://savo-backend.onrender.com/api/decision/evaluate-ingredient

# Expected: 422 Validation Error

# 3. Unauthorized access
curl https://savo-backend.onrender.com/api/decision/rules

# Expected: 401 Unauthorized
```

**✅ Pass Criteria**:
- Proper HTTP status codes
- Clear error messages
- Validation errors detailed

---

## 📊 Success Metrics

Track these metrics during testing:

| Metric | Target | Actual |
|--------|--------|--------|
| All endpoints responding | 9/9 | ___ |
| Average response time | <500ms | ___ |
| Error rate | <1% | ___ |
| Acceptance rate calculation | Correct | ___ |
| Auto-apply logic | Working | ___ |

---

## 🐛 Known Issues

- [ ] None yet

---

## ✅ Test Completion Checklist

- [ ] Health check passes
- [ ] Get rules returns 5 seeded rules
- [ ] Evaluate single ingredient works for 3 scenarios
- [ ] Batch evaluate handles multiple items
- [ ] Recommended actions history with filters
- [ ] Apply action records feedback
- [ ] User stats calculated correctly
- [ ] Create rule (admin) works
- [ ] Error handling appropriate
- [ ] Render deployment stable

---

## 📝 Test Results Log

**Date**: _________  
**Tester**: _________  
**Backend URL**: https://savo-backend.onrender.com

| Endpoint | Status | Response Time | Notes |
|----------|--------|---------------|-------|
| Health | ⏳ | | |
| Get Rules | ⏳ | | |
| Evaluate Ingredient | ⏳ | | |
| Evaluate Inventory | ⏳ | | |
| Get Actions | ⏳ | | |
| Apply Action | ⏳ | | |
| Get Stats | ⏳ | | |
| Create Rule | ⏳ | | |
| Error Handling | ⏳ | | |

**Overall Status**: ⏳ Pending Testing

---

**Next Steps After Testing**:
1. Document any bugs found
2. Integrate endpoints with Flutter app
3. Setup monitoring/alerting
4. Performance optimization if needed
