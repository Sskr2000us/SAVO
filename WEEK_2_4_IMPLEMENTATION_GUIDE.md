# Weeks 2-4 Implementation Roadmap

**Timeline**: Days 8-28  
**Prerequisites**: Week 1 complete (100+ ingredients, Storage setup)

---

## 🎯 Week 2: Decision Intelligence API (Days 8-14)

### **Day 8: Apply Migration 007**

**Task**: Deploy decision intelligence database schema

```powershell
# Via Supabase Dashboard SQL Editor
# 1. Open: services/api/migrations/007_decision_intelligence.sql
# 2. Copy entire file
# 3. Paste into SQL Editor
# 4. Click Run
```

**Verify**:
```sql
-- Check tables created (should return 8)
SELECT COUNT(*) FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name IN (
    'decision_rules', 'ingredient_actions', 'daily_digests',
    'user_streaks', 'passive_learning_signals',
    'model_performance_metrics', 'learning_feedback', 'success_metrics_daily'
);

-- Check seed rules (should return 5)
SELECT rule_id, rule_name, action FROM decision_rules;
```

---

### **Day 9-10: Create FastAPI Decision Router**

**File**: `services/api/app/api/decision.py`

```python
"""
Decision Intelligence API Router
7 endpoints for auto-action recommendations
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel

from ..services.decision_intelligence_service import (
    DecisionIntelligenceService,
    DecisionResult,
    ActionFeedback
)
from ..dependencies import get_supabase_client, get_current_user

router = APIRouter(prefix="/api/decision", tags=["decision"])

# ===== REQUEST/RESPONSE MODELS =====

class EvaluateIngredientRequest(BaseModel):
    ingredient_id: str
    context: Optional[dict] = None

class EvaluateInventoryRequest(BaseModel):
    limit: int = 10

class ActionFeedbackRequest(BaseModel):
    action_id: str
    user_response: str  # accepted, rejected, ignored, modified
    user_final_action: Optional[str] = None
    feedback_notes: Optional[str] = None

# ===== ENDPOINTS =====

@router.post("/evaluate-ingredient", response_model=dict)
async def evaluate_ingredient(
    request: EvaluateIngredientRequest,
    current_user: dict = Depends(get_current_user),
    supabase = Depends(get_supabase_client)
):
    """
    Evaluate a single ingredient and recommend action
    
    Returns:
        DecisionResult with recommended action, confidence, urgency
    """
    service = DecisionIntelligenceService(supabase)
    
    result = await service.evaluate_ingredient(
        user_id=UUID(current_user["id"]),
        ingredient_id=UUID(request.ingredient_id),
        context=request.context
    )
    
    return result.to_dict()


@router.post("/evaluate-inventory", response_model=List[dict])
async def evaluate_inventory(
    request: EvaluateInventoryRequest,
    current_user: dict = Depends(get_current_user),
    supabase = Depends(get_supabase_client)
):
    """
    Evaluate all ingredients in user's inventory
    Returns sorted by urgency
    """
    service = DecisionIntelligenceService(supabase)
    
    results = await service.evaluate_inventory(
        user_id=UUID(current_user["id"]),
        limit=request.limit
    )
    
    return [r.to_dict() for r in results]


@router.get("/recommended-actions", response_model=List[dict])
async def get_recommended_actions(
    action_types: Optional[str] = None,
    limit: int = 10,
    current_user: dict = Depends(get_current_user),
    supabase = Depends(get_supabase_client)
):
    """
    Get recent recommended actions for user
    """
    service = DecisionIntelligenceService(supabase)
    
    types = action_types.split(",") if action_types else None
    
    actions = await service.get_recommended_actions(
        user_id=UUID(current_user["id"]),
        action_types=types,
        limit=limit
    )
    
    return actions


@router.post("/apply-action")
async def apply_action(
    request: ActionFeedbackRequest,
    current_user: dict = Depends(get_current_user),
    supabase = Depends(get_supabase_client)
):
    """
    Record user feedback on recommended action
    """
    service = DecisionIntelligenceService(supabase)
    
    feedback = ActionFeedback(
        action_id=UUID(request.action_id),
        user_response=request.user_response,
        user_final_action=request.user_final_action,
        feedback_notes=request.feedback_notes
    )
    
    success = await service.apply_action_feedback(feedback)
    
    return {"success": success, "message": "Feedback recorded"}


@router.get("/rules", response_model=List[dict])
async def get_decision_rules(
    is_active: bool = True,
    supabase = Depends(get_supabase_client)
):
    """
    Get all decision rules (for debugging/admin)
    """
    response = supabase.table("decision_rules").select("*").eq(
        "is_active", is_active
    ).order("priority").execute()
    
    return response.data


@router.post("/rules")
async def create_decision_rule(
    rule_data: dict,
    current_user: dict = Depends(get_current_user),
    supabase = Depends(get_supabase_client)
):
    """
    Create new decision rule (admin only)
    """
    # TODO: Check if user is admin
    
    response = supabase.table("decision_rules").insert(rule_data).execute()
    
    return response.data[0]


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "decision_intelligence"}
```

**Register Router**: Update `services/api/app/api/router.py`:

```python
from .decision import router as decision_router

# Add to router registration
api_router.include_router(decision_router)
```

---

### **Day 11-12: Build Flutter Decision UI**

**File**: `apps/mobile/lib/services/decision_intelligence_service.dart`

```dart
import 'package:supabase_flutter/supabase_flutter.dart';

class DecisionIntelligenceService {
  final _supabase = Supabase.instance.client;
  
  Future<DecisionResult> evaluateIngredient(
    String ingredientId,
    {Map<String, dynamic>? context}
  ) async {
    final response = await _supabase.functions.invoke(
      'decision-evaluate-ingredient',
      body: {
        'ingredient_id': ingredientId,
        'context': context,
      },
    );
    
    return DecisionResult.fromJson(response.data);
  }
  
  Future<List<DecisionResult>> evaluateInventory({int limit = 10}) async {
    final response = await _supabase.functions.invoke(
      'decision-evaluate-inventory',
      body: {'limit': limit},
    );
    
    return (response.data as List)
      .map((item) => DecisionResult.fromJson(item))
      .toList();
  }
  
  Future<void> provideFeedback({
    required String actionId,
    required String userResponse,
    String? userFinalAction,
    String? feedbackNotes,
  }) async {
    await _supabase.functions.invoke(
      'decision-apply-action',
      body: {
        'action_id': actionId,
        'user_response': userResponse,
        'user_final_action': userFinalAction,
        'feedback_notes': feedbackNotes,
      },
    );
  }
}

class DecisionResult {
  final String ingredientId;
  final String ingredientName;
  final String recommendedAction;
  final double confidence;
  final String reason;
  final bool autoApply;
  final double urgencyScore;
  
  DecisionResult({
    required this.ingredientId,
    required this.ingredientName,
    required this.recommendedAction,
    required this.confidence,
    required this.reason,
    required this.autoApply,
    required this.urgencyScore,
  });
  
  factory DecisionResult.fromJson(Map<String, dynamic> json) {
    return DecisionResult(
      ingredientId: json['ingredient_id'],
      ingredientName: json['ingredient_name'],
      recommendedAction: json['recommended_action'],
      confidence: (json['confidence'] as num).toDouble(),
      reason: json['reason'],
      autoApply: json['auto_apply'] ?? false,
      urgencyScore: (json['urgency_score'] as num?)?.toDouble() ?? 0.0,
    );
  }
  
  String get actionEmoji {
    switch (recommendedAction) {
      case 'cook_now': return '🍳';
      case 'store_better': return '📦';
      case 'substitute': return '🔄';
      case 'buy': return '🛒';
      case 'do_not_buy': return '❌';
      case 'discard': return '🗑️';
      default: return '📋';
    }
  }
  
  String get actionLabel {
    switch (recommendedAction) {
      case 'cook_now': return 'Cook Now';
      case 'store_better': return 'Store Better';
      case 'substitute': return 'Substitute';
      case 'buy': return 'Buy';
      case 'do_not_buy': return 'Don\'t Buy';
      case 'discard': return 'Discard';
      default: return 'Monitor';
    }
  }
  
  Color get confidenceColor {
    if (confidence >= 0.85) return Colors.green;
    if (confidence >= 0.60) return Colors.orange;
    return Colors.red;
  }
  
  String get confidenceLabel {
    if (confidence >= 0.85) return 'High';
    if (confidence >= 0.60) return 'Medium';
    return 'Low';
  }
  
  String get urgencyLabel {
    if (urgencyScore >= 70) return 'Critical';
    if (urgencyScore >= 50) return 'High';
    if (urgencyScore >= 30) return 'Medium';
    return 'Low';
  }
}
```

**UI Screen**: `apps/mobile/lib/screens/smart_actions_screen.dart`

```dart
import 'package:flutter/material.dart';

class SmartActionsScreen extends StatefulWidget {
  @override
  _SmartActionsScreenState createState() => _SmartActionsScreenState();
}

class _SmartActionsScreenState extends State<SmartActionsScreen> {
  final _service = DecisionIntelligenceService();
  List<DecisionResult> _actions = [];
  bool _loading = true;
  
  @override
  void initState() {
    super.initState();
    _loadActions();
  }
  
  Future<void> _loadActions() async {
    setState(() => _loading = true);
    
    try {
      final actions = await _service.evaluateInventory(limit: 10);
      setState(() {
        _actions = actions;
        _loading = false;
      });
    } catch (e) {
      setState(() => _loading = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error loading actions: $e')),
      );
    }
  }
  
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text('Smart Actions'),
        actions: [
          IconButton(
            icon: Icon(Icons.refresh),
            onPressed: _loadActions,
          ),
        ],
      ),
      body: _loading
        ? Center(child: CircularProgressIndicator())
        : ListView.builder(
            itemCount: _actions.length,
            itemBuilder: (context, index) {
              final action = _actions[index];
              return ActionCard(
                action: action,
                onFeedback: (response) => _handleFeedback(action, response),
              );
            },
          ),
    );
  }
  
  void _handleFeedback(DecisionResult action, String response) async {
    // Provide feedback to service
    // ...implementation
  }
}
```

---

### **Day 13-14: Testing & Integration**

**Test Decision API**:

```powershell
# Test evaluate ingredient
curl -X POST "http://localhost:8000/api/decision/evaluate-ingredient" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"ingredient_id": "UUID_HERE"}'

# Test evaluate inventory
curl -X POST "http://localhost:8000/api/decision/evaluate-inventory" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"limit": 10}'
```

**Week 2 Success Criteria**:
- [ ] Migration 007 applied successfully
- [ ] 7 decision API endpoints functional
- [ ] Flutter service integration complete
- [ ] Decision UI displaying recommendations
- [ ] Feedback mechanism working

---

## 🔄 Week 3: Daily Habit Loop (Days 15-21)

### **Day 15-16: Implement DailyHabitService**

**File**: `services/api/app/services/daily_habit_service.py`

```python
"""
Daily Habit Service
Generates morning digests, tracks streaks, monitors passive signals
"""

from typing import List, Dict, Optional
from uuid import UUID
from datetime import datetime, time
import asyncio

class DailyHabitService:
    def __init__(self, supabase_client):
        self.db = supabase_client
    
    async def generate_morning_digest(self, user_id: UUID) -> Dict:
        """
        Generate personalized morning digest
        
        Answers 3 core questions:
        1. What can I cook now?
        2. What will go bad soon?
        3. What did I waste last week?
        """
        
        # Get expiring ingredients (top 2)
        expiring = await self._get_expiring_ingredients(user_id, limit=2)
        
        # Get recipe recommendations
        recipes = await self._get_recipe_recommendations(user_id, expiring)
        
        # Get waste summary
        waste_summary = await self._get_waste_summary(user_id, days=7)
        
        # Get streak status
        streak = await self._get_streak(user_id, "no_waste")
        
        digest = {
            "greeting": self._get_greeting(),
            "cook_today": [
                {
                    "ingredient": ing["name"],
                    "days_left": ing["days_to_expiry"],
                    "recipe": recipes.get(ing["id"])
                }
                for ing in expiring
            ],
            "expiring_soon": await self._get_expiring_ingredients(user_id, limit=2, skip=2),
            "waste_summary": waste_summary,
            "streak": {
                "type": "no_waste",
                "count": streak["current_count"] if streak else 0
            }
        }
        
        # Save digest
        await self._save_digest(user_id, "morning", digest)
        
        return digest
    
    # Implement remaining methods...
```

### **Day 17-18: Firebase Push Notifications**

1. **Setup Firebase Cloud Messaging**:
   - Create Firebase project
   - Add Android/iOS apps
   - Download `google-services.json` / `GoogleService-Info.plist`

2. **Configure Flutter**:
```yaml
# pubspec.yaml
dependencies:
  firebase_messaging: ^14.7.0
  firebase_core: ^2.24.0
```

3. **Initialize Notifications**:
```dart
// lib/services/notification_service.dart
class NotificationService {
  final FirebaseMessaging _messaging = FirebaseMessaging.instance;
  
  Future<void> initialize() async {
    await _messaging.requestPermission();
    
    String? token = await _messaging.getToken();
    print('FCM Token: $token');
    
    // Save token to database
    await _saveTokenToDatabase(token);
    
    // Handle foreground messages
    FirebaseMessaging.onMessage.listen(_handleMessage);
  }
}
```

4. **Schedule Daily Digests**:
```python
# Use APScheduler
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

# Schedule morning digest (8 AM)
scheduler.add_job(
    send_morning_digests,
    'cron',
    hour=8,
    minute=0
)

# Schedule evening check (6 PM)
scheduler.add_job(
    send_evening_checks,
    'cron',
    hour=18,
    minute=0
)

scheduler.start()
```

### **Day 19-21: Build Digest UI**

```dart
// lib/screens/digest_screen.dart
class DigestScreen extends StatelessWidget {
  final DailyDigest digest;
  
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Daily Digest')),
      body: SingleChildScrollView(
        padding: EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _buildGreeting(),
            SizedBox(height: 24),
            _buildCookTodaySection(),
            SizedBox(height: 24),
            _buildExpiringSoonSection(),
            SizedBox(height: 24),
            _buildWasteSummarySection(),
            SizedBox(height: 24),
            _buildStreakSection(),
          ],
        ),
      ),
    );
  }
}
```

**Week 3 Success Criteria**:
- [ ] DailyHabitService implemented
- [ ] Firebase notifications configured
- [ ] Morning/evening digests scheduled
- [ ] Digest UI functional
- [ ] Streak tracking working

---

## 🧠 Week 4: Self-Learning Loop (Days 22-28)

### **Day 22-23: Implement SelfLearningService**

**File**: `services/api/app/services/self_learning_service.py`

```python
"""
Self-Learning Service
Processes user feedback and updates model confidence
"""

class SelfLearningService:
    async def process_cv_feedback(
        self,
        scan_result_id: UUID,
        confirmed_ingredient_id: UUID,
        was_correct: bool
    ):
        """Update CV model confidence based on user confirmation"""
        
        scan = await self._get_scan_result(scan_result_id)
        
        if was_correct:
            # Reinforce positive identification
            await self._adjust_confidence(
                scan["visual_features"],
                confirmed_ingredient_id,
                adjustment=+0.05
            )
        else:
            # Penalize incorrect identification
            await self._adjust_confidence(
                scan["visual_features"],
                scan["detected_ingredient_id"],
                adjustment=-0.10
            )
            
            # Add to confusion graph
            await self._add_confusion_pair(
                scan["detected_ingredient_id"],
                confirmed_ingredient_id
            )
    
    async def process_substitution_feedback(
        self,
        substitution_id: UUID,
        was_accepted: bool
    ):
        """Update substitution rankings based on acceptance"""
        
        if was_accepted:
            await self._adjust_substitution_score(
                substitution_id,
                adjustment=+0.05,
                max_score=0.95
            )
        else:
            await self._adjust_substitution_score(
                substitution_id,
                adjustment=-0.10,
                min_score=0.30
            )
    
    async def calculate_performance_metrics(self, days=30):
        """Calculate model performance metrics"""
        
        # Human confirmation rate
        confirmation_rate = await self._calc_confirmation_rate(days)
        
        # Model confidence trend
        confidence_trend = await self._calc_confidence_trend(days)
        
        # Acceptance rates
        acceptance_rates = await self._calc_acceptance_rates(days)
        
        # Save metrics
        await self._save_metrics({
            "human_confirmation_rate": confirmation_rate,
            "avg_confidence": confidence_trend["avg"],
            "substitution_acceptance": acceptance_rates["substitution"],
            "decision_acceptance": acceptance_rates["decision"]
        })
```

### **Day 24-25: Build Metrics Dashboard**

```dart
// lib/screens/metrics_dashboard.dart
class MetricsDashboard extends StatefulWidget {
  @override
  _MetricsDashboardState createState() => _MetricsDashboardState();
}

class _MetricsDashboardState extends State<MetricsDashboard> {
  Map<String, dynamic> _metrics = {};
  
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Performance Metrics')),
      body: GridView.count(
        crossAxisCount: 2,
        padding: EdgeInsets.all(16),
        children: [
          MetricCard(
            title: 'Scan-to-Action Rate',
            value: '${(_metrics["scan_to_action_rate"] * 100).toStringAsFixed(1)}%',
            target: '60%',
            icon: Icons.touch_app,
          ),
          MetricCard(
            title: 'Waste Reduction',
            value: '${(_metrics["waste_reduction"] * 100).toStringAsFixed(1)}%',
            target: '20%',
            icon: Icons.trending_down,
          ),
          MetricCard(
            title: 'Time Saved',
            value: '${_metrics["time_saved_minutes"]} min/week',
            target: '30 min',
            icon: Icons.access_time,
          ),
          MetricCard(
            title: 'Weekly Return Rate',
            value: '${(_metrics["weekly_return_rate"] * 100).toStringAsFixed(1)}%',
            target: '40%',
            icon: Icons.replay,
          ),
        ],
      ),
    );
  }
}
```

### **Day 26-28: Testing & Optimization**

**Test Self-Learning**:

```python
# test_self_learning.py
import pytest
from services.self_learning_service import SelfLearningService

async def test_cv_feedback_reinforcement():
    service = SelfLearningService(supabase)
    
    # Submit positive feedback
    await service.process_cv_feedback(
        scan_result_id=scan_id,
        confirmed_ingredient_id=ingredient_id,
        was_correct=True
    )
    
    # Check confidence increased
    # ...assertions

async def test_confirmation_rate_calculation():
    service = SelfLearningService(supabase)
    
    rate = await service._calc_confirmation_rate(days=30)
    
    assert 0 <= rate <= 1
    print(f"Confirmation rate: {rate * 100}%")
```

**Week 4 Success Criteria**:
- [ ] SelfLearningService implemented
- [ ] Feedback processing working
- [ ] Metrics calculated correctly
- [ ] Dashboard displaying trends
- [ ] Automated retraining pipeline tested

---

## ✅ 4-Week Completion Checklist

- [ ] **Week 1**: 100+ ingredients, Storage setup
- [ ] **Week 2**: Decision API (7 endpoints), Flutter UI
- [ ] **Week 3**: Daily digests, Firebase notifications
- [ ] **Week 4**: Self-learning, Metrics dashboard

---

**Next**: Deploy to production and monitor metrics!
