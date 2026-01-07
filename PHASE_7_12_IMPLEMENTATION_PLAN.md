# SAVO Intelligence Layer: Phases 7-12 Implementation Plan

**Version**: 1.0  
**Created**: 2026-01-06  
**Status**: Planning → Implementation  
**Foundation**: Phases 1-6 Complete (37 endpoints, 10 services, 10,946+ lines)

---

## 🎯 Strategic Vision

Transform SAVO from a **Visual Intelligence Platform** into a **Decision Intelligence System** that:

1. **Makes decisions automatically** based on confidence thresholds
2. **Builds daily habits** through calm, supportive nudges
3. **Learns continuously** from user feedback and behavior
4. **Provides value** across multiple market segments
5. **Earns trust** through explainability and conservative allergen handling
6. **Measures impact** with metrics that actually matter

---

## 📋 Foundation Status (Phases 1-6)

### ✅ Completed Components
- **Phase 1**: Foundation (37 ingredients, 222 aliases, 9 tables)
- **Phase 2**: Visual Intelligence (GPT-4 Vision, color/texture extraction)
- **Phase 3**: Search & Discovery (semantic, fuzzy, multi-language, voice)
- **Phase 4**: Graph Intelligence (substitutions, confusions, pairings)
- **Phase 5**: Regional Intelligence (42+ regional variants, 14 regions)
- **Phase 6**: Waste Prevention (spoilage prediction, storage alerts, analytics)

### 📊 Current Capabilities
- 37 API endpoints across 6 routers
- 10 services (5 Python, 5 Dart/Flutter)
- 10,946+ lines of code
- Multi-language support (6 languages)
- Real-time ingredient identification
- Context-aware substitutions
- Regional cuisine intelligence
- Waste prevention analytics

---

## 🚀 Phase 7: Decision Intelligence

### Strategic Goal
**Move from "here's information" to "here's what you should do"**

### Core Concept
```
Raw Data → Intelligence → Confidence → Decision → Auto-Action
```

### Confidence Thresholds
```json
{
  "auto_action_min": 0.85,      // Execute automatically
  "suggest_action_min": 0.60,   // Suggest to user
  "ask_user_below": 0.60        // Request confirmation
}
```

### Action Engine

#### Possible Actions
1. **cook_now** - Use ingredient immediately (high freshness, near expiry)
2. **store_better** - Improve storage conditions (extend shelf life)
3. **substitute** - Replace missing ingredient in recipe
4. **buy** - Purchase for planned meal
5. **do_not_buy** - Already have sufficient quantity
6. **discard** - Safety concern or spoiled

#### Decision Rules

**Rule 1: Cook Now**
```python
Rule: DI_COOK_NOW_001
Conditions:
  - freshness_score >= 0.80
  - days_to_expiry <= 1
  - recognition_confidence >= 0.85
Action: cook_now
Explanation: "This ingredient is at peak freshness and should be used today."
Auto-apply: True
```

**Rule 2: Store Better**
```python
Rule: DI_STORE_001
Conditions:
  - freshness_score >= 0.60
  - days_to_expiry >= 2
  - storage_quality < 0.70
Action: store_better
Explanation: "Storing this properly can extend its usability by 3-5 days."
Auto-apply: False (suggest)
```

**Rule 3: Smart Substitute**
```python
Rule: DI_SUBSTITUTE_001
Conditions:
  - ingredient_missing = true
  - substitution_confidence >= 0.70
  - substitution_available = true
Action: substitute
Explanation: "A suitable substitute is available with minimal taste impact."
Auto-apply: True (if confidence >= 0.85)
```

### Database Schema

#### decision_rules Table
```sql
CREATE TABLE decision_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_id TEXT UNIQUE NOT NULL,
    rule_name TEXT NOT NULL,
    
    -- Conditions (JSONB for flexibility)
    conditions JSONB NOT NULL,
    
    -- Action
    action TEXT NOT NULL, -- cook_now, store_better, substitute, buy, do_not_buy, discard
    explanation_template TEXT NOT NULL,
    
    -- Thresholds
    confidence_min NUMERIC(3,2) DEFAULT 0.85,
    auto_apply BOOLEAN DEFAULT false,
    
    -- Learning
    times_applied INTEGER DEFAULT 0,
    times_accepted INTEGER DEFAULT 0,
    acceptance_rate NUMERIC(3,2),
    
    -- Status
    is_active BOOLEAN DEFAULT true,
    priority INTEGER DEFAULT 100,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_decision_rules_action ON decision_rules(action);
CREATE INDEX idx_decision_rules_active ON decision_rules(is_active);
```

#### ingredient_actions Table
```sql
CREATE TABLE ingredient_actions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- Ingredient context
    ingredient_id UUID REFERENCES master_ingredients(id),
    inventory_item_id UUID, -- If from user inventory
    
    -- Decision
    decision_rule_id UUID REFERENCES decision_rules(id),
    recommended_action TEXT NOT NULL,
    confidence NUMERIC(3,2) NOT NULL,
    reason TEXT,
    
    -- Auto-action
    was_auto_applied BOOLEAN DEFAULT false,
    
    -- User feedback
    user_response TEXT, -- accepted, rejected, ignored, modified
    user_final_action TEXT, -- What user actually did
    feedback_notes TEXT,
    
    -- Timing
    recommended_at TIMESTAMPTZ DEFAULT NOW(),
    responded_at TIMESTAMPTZ,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_actions_user ON ingredient_actions(user_id);
CREATE INDEX idx_actions_ingredient ON ingredient_actions(ingredient_id);
CREATE INDEX idx_actions_response ON ingredient_actions(user_response);
```

### API Endpoints

```python
# Decision Intelligence Router
POST   /api/decision/evaluate-ingredient
POST   /api/decision/evaluate-inventory
GET    /api/decision/recommended-actions/{user_id}
POST   /api/decision/apply-action
POST   /api/decision/feedback
GET    /api/decision/rules
POST   /api/decision/rules (admin)
GET    /api/decision/health
```

### Service Implementation

```python
# services/api/app/services/decision_intelligence_service.py

class DecisionIntelligenceService:
    def __init__(self):
        self.confidence_thresholds = {
            "auto_action": 0.85,
            "suggest_action": 0.60,
            "ask_user": 0.60
        }
    
    async def evaluate_ingredient(
        self,
        user_id: UUID,
        ingredient_id: UUID,
        context: dict
    ) -> DecisionResult:
        """
        Evaluate ingredient and recommend action
        
        Steps:
        1. Gather ingredient data (freshness, expiry, storage)
        2. Apply decision rules in priority order
        3. Calculate confidence score
        4. Determine if auto-apply or suggest
        5. Log decision for learning
        """
        
        # Get ingredient intelligence
        ingredient_data = await self._gather_ingredient_intelligence(
            ingredient_id, context
        )
        
        # Apply decision rules
        matching_rules = await self._find_matching_rules(ingredient_data)
        
        if not matching_rules:
            return DecisionResult(
                action="monitor",
                confidence=0.50,
                auto_apply=False,
                reason="No specific action needed at this time."
            )
        
        # Select best rule
        best_rule = matching_rules[0]
        confidence = self._calculate_confidence(ingredient_data, best_rule)
        
        # Auto-apply decision
        auto_apply = (
            confidence >= self.confidence_thresholds["auto_action"] 
            and best_rule.auto_apply
        )
        
        # Log decision
        await self._log_decision(
            user_id, ingredient_id, best_rule, confidence, auto_apply
        )
        
        return DecisionResult(
            ingredient_id=ingredient_id,
            action=best_rule.action,
            confidence=confidence,
            reason=best_rule.explanation_template,
            auto_apply=auto_apply,
            details=ingredient_data
        )
    
    async def evaluate_inventory(
        self,
        user_id: UUID,
        limit: int = 10
    ) -> List[DecisionResult]:
        """Evaluate all ingredients in user's inventory"""
        
        inventory = await self._get_user_inventory(user_id)
        decisions = []
        
        for item in inventory[:limit]:
            decision = await self.evaluate_ingredient(
                user_id, item.ingredient_id, {"inventory_item": item}
            )
            decisions.append(decision)
        
        # Sort by urgency (confidence + days_to_expiry)
        decisions.sort(key=lambda d: d.urgency_score, reverse=True)
        
        return decisions
    
    async def apply_action(
        self,
        action_id: UUID,
        user_response: str
    ) -> ActionResult:
        """Apply user response to recommended action"""
        
        # Update action record
        await self._update_action_response(action_id, user_response)
        
        # Trigger learning update
        await self._update_rule_statistics(action_id)
        
        return ActionResult(success=True)
```

### Flutter Integration

```dart
// waste_prevention_service.dart (extend existing)

class DecisionResult {
  final String ingredientId;
  final String ingredientName;
  final String action;
  final double confidence;
  final String reason;
  final bool autoApply;
  final Map<String, dynamic> details;
  
  String get actionEmoji {
    switch (action) {
      case 'cook_now': return '🍳';
      case 'store_better': return '📦';
      case 'substitute': return '🔄';
      case 'buy': return '🛒';
      case 'do_not_buy': return '❌';
      case 'discard': return '🗑️';
      default: return '📋';
    }
  }
  
  Color get confidenceColor {
    if (confidence >= 0.85) return Colors.green;
    if (confidence >= 0.60) return Colors.orange;
    return Colors.red;
  }
}

Future<List<DecisionResult>> getRecommendedActions() async {
  final response = await _supabase.functions.invoke(
    'decision-evaluate-inventory',
    body: {'user_id': _userId, 'limit': 10},
  );
  
  return (response.data as List)
    .map((item) => DecisionResult.fromJson(item))
    .toList();
}
```

---

## 🔄 Phase 8: Daily Habit Loop

### Strategic Goal
**Build a calm, supportive daily habit that reduces decision fatigue**

### Core Concept
```
Daily Trigger → Answer 3 Questions → Small Action → Positive Reinforcement
```

### Three Core Questions

1. **"What can I cook now?"**
   - Show 1-2 recipes using ingredients user already has
   - Prioritize expiring items
   - Match user's skill level and time availability

2. **"What will go bad soon?"**
   - Show top 2 expiring ingredients
   - Include days remaining and storage tips
   - Suggest specific recipes

3. **"What did I waste last week?"**
   - Show waste analytics (quantity, cost, impact)
   - Celebrate improvements
   - Suggest prevention strategies

### Daily Digest Format

**Morning Digest (8:00 AM)**
```
🌅 Good morning!

🍳 Cook today:
• Spinach (expires today) → Palak Paneer recipe
• Tomatoes (2 days left) → Fresh salsa

📦 Expiring soon:
• Ginger (3 days) - Store in freezer to extend

✅ Streak: 5 days without waste! 
```

**Evening Check (6:00 PM)**
```
🌙 Quick check-in

❓ Did you use that spinach today?
   [Yes, cooked it] [No, stored it] [Discarded]

📊 This week: Saved $12 worth of food!
```

### Database Schema

#### daily_digests Table
```sql
CREATE TABLE daily_digests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- Content
    digest_type TEXT NOT NULL, -- morning, evening
    content JSONB NOT NULL,
    
    -- Personalization
    expiring_ingredients UUID[],
    recommended_recipes UUID[],
    waste_summary JSONB,
    
    -- Engagement
    was_sent BOOLEAN DEFAULT false,
    sent_at TIMESTAMPTZ,
    was_opened BOOLEAN DEFAULT false,
    opened_at TIMESTAMPTZ,
    was_actioned BOOLEAN DEFAULT false,
    actioned_at TIMESTAMPTZ,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_digests_user ON daily_digests(user_id);
CREATE INDEX idx_digests_type ON daily_digests(digest_type);
CREATE INDEX idx_digests_sent ON daily_digests(was_sent, sent_at);
```

#### user_streaks Table
```sql
CREATE TABLE user_streaks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- Streak definition
    streak_type TEXT NOT NULL, -- no_waste, daily_scan, weekly_cook
    
    -- Current streak
    current_count INTEGER DEFAULT 0,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Records
    longest_count INTEGER DEFAULT 0,
    longest_started_at TIMESTAMPTZ,
    longest_ended_at TIMESTAMPTZ,
    
    -- Status
    is_active BOOLEAN DEFAULT true,
    last_activity_at TIMESTAMPTZ DEFAULT NOW(),
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_streaks_user ON user_streaks(user_id);
CREATE INDEX idx_streaks_type ON user_streaks(streak_type);
CREATE INDEX idx_streaks_active ON user_streaks(is_active);
```

#### passive_learning_signals Table
```sql
CREATE TABLE passive_learning_signals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- Signal context
    signal_type TEXT NOT NULL, -- digest_opened, item_clicked, recipe_cooked, item_ignored
    entity_type TEXT, -- ingredient, recipe, action
    entity_id UUID,
    
    -- Metadata
    context JSONB,
    session_id TEXT,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_signals_user ON passive_learning_signals(user_id);
CREATE INDEX idx_signals_type ON passive_learning_signals(signal_type);
CREATE INDEX idx_signals_entity ON passive_learning_signals(entity_type, entity_id);
```

### Service Implementation

```python
# services/api/app/services/daily_habit_service.py

class DailyHabitService:
    async def generate_morning_digest(
        self,
        user_id: UUID
    ) -> DailyDigest:
        """Generate personalized morning digest"""
        
        # Get expiring ingredients (top 2)
        expiring = await self.waste_prevention.get_expiring_items(
            user_id, days_threshold=3
        )
        
        # Get recipe recommendations
        recipes = await self._get_matching_recipes(
            user_id, expiring[:2]
        )
        
        # Get streak status
        streak = await self._get_active_streak(user_id, "no_waste")
        
        # Build digest
        digest = {
            "greeting": self._get_time_appropriate_greeting(),
            "cook_today": [
                {
                    "ingredient": ing.name,
                    "days_left": ing.days_to_expiry,
                    "recipe": recipes.get(ing.id)
                }
                for ing in expiring[:2]
            ],
            "expiring_soon": [
                {
                    "ingredient": ing.name,
                    "days_left": ing.days_to_expiry,
                    "storage_tip": ing.storage_tip
                }
                for ing in expiring[2:4]
            ],
            "streak": {
                "type": "no_waste",
                "count": streak.current_count if streak else 0
            }
        }
        
        # Log digest
        await self._save_digest(user_id, "morning", digest)
        
        return DailyDigest(**digest)
    
    async def track_passive_signal(
        self,
        user_id: UUID,
        signal_type: str,
        entity_type: str,
        entity_id: UUID,
        context: dict = None
    ):
        """Track user behavior passively for learning"""
        
        await self.db.insert("passive_learning_signals", {
            "user_id": user_id,
            "signal_type": signal_type,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "context": context
        })
        
        # Update relevant metrics
        if signal_type == "digest_opened":
            await self._increment_engagement_metric(user_id, "digest_opens")
        elif signal_type == "recipe_cooked":
            await self._update_streak(user_id, "daily_cook")
```

---

## 🧠 Phase 9: Self-Learning Intelligence Loop

### Strategic Goal
**Improve accuracy and personalization without manual intervention**

### Core Concept
```
User Feedback → Update Weights → Retrain Models → Measure Improvement
```

### Feedback Sources

1. **User Confirmation**
   - "Yes, this is turmeric" → Reinforce CV model confidence
   
2. **User Correction**
   - "No, this is ginger, not garlic" → Penalize confusion, update disambiguation

3. **Action Acceptance**
   - User accepts substitution → Increase substitution weight

4. **Action Rejection**
   - User rejects substitution → Decrease weight, flag for review

### Learning Updates

#### CV Model Reinforcement
```python
async def reinforce_identification(
    self,
    scan_result_id: UUID,
    confirmed_ingredient_id: UUID,
    was_correct: bool
):
    """Update CV model confidence based on user feedback"""
    
    # Get scan details
    scan = await self._get_scan_result(scan_result_id)
    
    if was_correct:
        # Increase confidence threshold for this visual signature
        await self._update_visual_confidence(
            visual_features=scan.visual_features,
            ingredient_id=confirmed_ingredient_id,
            adjustment=+0.05
        )
    else:
        # Decrease confidence, flag for retraining
        await self._update_visual_confidence(
            visual_features=scan.visual_features,
            ingredient_id=scan.detected_ingredient_id,
            adjustment=-0.10
        )
        
        # Add to confusion graph if misidentified
        if scan.detected_ingredient_id:
            await self._add_confusion_pair(
                scan.detected_ingredient_id,
                confirmed_ingredient_id,
                reason="cv_misidentification"
            )
```

#### Substitution Ranking Updates
```python
async def update_substitution_ranking(
    self,
    substitution_id: UUID,
    user_response: str  # accepted, rejected, modified
):
    """Adjust substitution similarity scores based on acceptance"""
    
    if user_response == "accepted":
        # Increase similarity score
        await self._adjust_substitution_score(
            substitution_id,
            adjustment=+0.05,
            max_score=0.95
        )
        
        # Increment acceptance count
        await self._increment_acceptance_count(substitution_id)
        
    elif user_response == "rejected":
        # Decrease similarity score
        await self._adjust_substitution_score(
            substitution_id,
            adjustment=-0.10,
            min_score=0.30
        )
        
        # Flag for review if acceptance rate < 50%
        substitution = await self._get_substitution(substitution_id)
        if substitution.acceptance_rate < 0.50:
            await self._flag_for_review(substitution_id, "low_acceptance")
```

### Key Learning Metrics

#### Human Confirmation Rate
```python
metric = "human_confirmation_rate"
definition = "Percentage of AI decisions that require human confirmation"
expected_trend = "decreasing"

# Target: Start at 40%, reduce to <15% within 6 months

async def calculate_confirmation_rate(
    self,
    user_id: UUID,
    days_lookback: int = 30
) -> float:
    """Calculate how often user confirms vs corrects"""
    
    actions = await self.db.query("""
        SELECT 
            COUNT(*) FILTER (WHERE user_response = 'accepted') as confirmed,
            COUNT(*) FILTER (WHERE user_response = 'rejected') as rejected,
            COUNT(*) as total
        FROM ingredient_actions
        WHERE user_id = $1
        AND recommended_at >= NOW() - INTERVAL '%s days'
    """, user_id, days_lookback)
    
    if actions.total == 0:
        return 1.0  # No data = assume all need confirmation
    
    return (actions.confirmed + actions.rejected) / actions.total
```

### Database Schema

#### model_performance_metrics Table
```sql
CREATE TABLE model_performance_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Model identification
    model_type TEXT NOT NULL, -- cv_identification, substitution_ranking, decision_rules
    model_version TEXT,
    
    -- Metrics
    metric_name TEXT NOT NULL, -- accuracy, precision, recall, acceptance_rate
    metric_value NUMERIC(5,4) NOT NULL,
    
    -- Context
    calculated_for_date DATE NOT NULL,
    sample_size INTEGER,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_metrics_model ON model_performance_metrics(model_type, metric_name);
CREATE INDEX idx_metrics_date ON model_performance_metrics(calculated_for_date DESC);
```

---

## 🏢 Phase 10: Productization & Differentiation

### Market Paths

#### Path 1: SmartChef Home (Consumer B2C)
**Target**: Home cooks, families, meal planners

**Features**:
- ✅ Ingredient scanning and identification
- ✅ Waste prevention and expiry alerts
- ✅ Recipe recommendations
- 🆕 Family member profiles (dietary preferences, allergies)
- 🆕 Meal planning calendar
- 🆕 Nutrition overlays (calories, macros, allergens)
- 🆕 Premium subscription ($4.99/month)

**Monetization**:
- Freemium model (5 scans/week free)
- Premium: Unlimited scans, advanced analytics, meal planning
- Recipe partnerships (affiliate links)

#### Path 2: SAVO B2B (Restaurant/Food Service)
**Target**: Restaurants, catering, institutional kitchens

**Features**:
- 🆕 POS integration (track ingredient usage)
- 🆕 Multi-location inventory management
- 🆕 Waste cost dashboard ($$$ impact)
- 🆕 Supplier ordering suggestions
- 🆕 Health inspection readiness reports

**Monetization**:
- Per-location license ($99-299/month)
- API usage fees
- Integration services

#### Path 3: Ingredient Intelligence API (B2B SaaS)
**Target**: Recipe apps, grocery delivery, smart appliances

**Exposed APIs**:
- Ingredient Recognition API
- Substitution Recommendation API
- Visual Intelligence API
- Regional Cuisine Intelligence API

**Monetization**:
- API call pricing (tiered)
- White-label licensing
- Data insights packages

---

## 🔒 Phase 11: Trust, Compliance & Explainability

### Explainability Templates

#### Ingredient Identification
```
"Identified as [INGREDIENT] based on:
• Color: [DOMINANT_COLORS]
• Texture: [TEXTURE_DESCRIPTION]
• Shape: [SHAPE_FEATURES]
• Regional context: [REGION]
Confidence: [XX]%"
```

#### Substitution
```
"Suggested [SUBSTITUTE] because:
• Similar taste profile ([SIMILARITY]% match)
• Compatible cooking behavior
• Available in your region
• Used in [X] similar recipes
Confidence: [XX]%"
```

#### Decision
```
"Recommended action: [ACTION]
Reason: [EXPLANATION]
Based on:
• Freshness: [SCORE]
• Days to expiry: [DAYS]
• Storage quality: [SCORE]
Confidence: [XX]%"
```

### Confidence Handling

```python
class ConfidenceHandler:
    def get_user_prompt(self, confidence: float) -> str:
        if confidence >= 0.85:
            return "High confidence"  # Auto-apply
        elif confidence >= 0.60:
            return "Does this look correct?"  # Suggest
        else:
            return "Please confirm or correct"  # Ask user
    
    def should_show_alternatives(self, confidence: float) -> bool:
        return confidence < 0.85  # Show top 3 alternatives
```

### Allergen Policy

**Default Behavior**: Conservative

```python
async def check_allergen_safety(
    self,
    ingredient_id: UUID,
    user_allergens: List[str]
) -> AllergenCheck:
    """Conservative allergen checking"""
    
    # Get ingredient allergen data
    allergens = await self._get_allergen_data(ingredient_id)
    
    # Check for direct matches
    direct_matches = set(allergens) & set(user_allergens)
    
    if direct_matches:
        return AllergenCheck(
            safe=False,
            warning_level="high",
            message=f"⚠️ Contains: {', '.join(direct_matches)}",
            require_confirmation=True
        )
    
    # Check for cross-contamination risk
    cross_risk = await self._check_cross_contamination(ingredient_id)
    
    if cross_risk:
        return AllergenCheck(
            safe=False,
            warning_level="medium",
            message="⚠️ May contain traces of allergens",
            require_confirmation=True
        )
    
    return AllergenCheck(safe=True, warning_level="none")
```

### Disclaimers

```
⚠️ AI-Assisted Recommendations

Identification and recommendations are AI-assisted and may require 
user verification. Always use your best judgment, especially for:
• Allergen information
• Food safety decisions  
• Expiry date assessments

SAVO is a tool to assist, not replace, your expertise.
```

---

## 📊 Phase 12: Metrics That Actually Matter

### Core Metrics (Track These)

#### 1. Scan-to-Action Rate
```sql
-- Percentage of scans that result in a meaningful action
SELECT 
    DATE(s.created_at) as scan_date,
    COUNT(DISTINCT s.id) as total_scans,
    COUNT(DISTINCT a.id) as scans_with_action,
    ROUND(
        COUNT(DISTINCT a.id)::NUMERIC / 
        COUNT(DISTINCT s.id)::NUMERIC * 100, 
        2
    ) as scan_to_action_rate
FROM visual_scan_results s
LEFT JOIN ingredient_actions a 
    ON s.user_confirmed_ingredient_id = a.ingredient_id
    AND a.created_at BETWEEN s.created_at AND s.created_at + INTERVAL '1 hour'
GROUP BY DATE(s.created_at)
ORDER BY scan_date DESC;
```

**Target**: >60% (currently ~30% industry average)

#### 2. Food Waste Reduction
```sql
-- Reduction in discarded ingredients over time
WITH weekly_waste AS (
    SELECT 
        user_id,
        DATE_TRUNC('week', created_at) as week,
        COUNT(*) as items_discarded,
        SUM(quantity * estimated_value) as waste_value
    FROM ingredient_actions
    WHERE user_final_action = 'discard'
    GROUP BY user_id, week
)
SELECT 
    user_id,
    week,
    items_discarded,
    waste_value,
    LAG(items_discarded) OVER (PARTITION BY user_id ORDER BY week) as prev_week_discarded,
    ROUND(
        (LAG(items_discarded) OVER (PARTITION BY user_id ORDER BY week) - items_discarded)::NUMERIC / 
        LAG(items_discarded) OVER (PARTITION BY user_id ORDER BY week)::NUMERIC * 100,
        2
    ) as reduction_percentage
FROM weekly_waste
ORDER BY user_id, week DESC;
```

**Target**: 20% reduction within 3 months

#### 3. Time Saved (Minutes per User)
```python
async def calculate_time_saved(user_id: UUID) -> TimeSaved:
    """
    Calculate time saved through:
    - Auto-identification (vs manual entry): 30 sec/ingredient
    - Smart substitutions (vs store trip): 15 min
    - Recipe suggestions (vs searching): 5 min
    """
    
    # Get user activity
    scans = await self._count_confirmed_scans(user_id)
    substitutions = await self._count_accepted_substitutions(user_id)
    recipes = await self._count_recipes_cooked(user_id)
    
    time_saved = (
        scans * 0.5 +  # 30 seconds per scan
        substitutions * 15 +  # 15 minutes per substitution
        recipes * 5  # 5 minutes per recipe suggestion
    )
    
    return TimeSaved(
        total_minutes=time_saved,
        breakdown={
            "scanning": scans * 0.5,
            "substitutions": substitutions * 15,
            "recipes": recipes * 5
        }
    )
```

**Target**: Save users 30+ minutes per week

#### 4. Confidence Improvement Curve
```sql
-- Track improvement in model confidence over time
SELECT 
    DATE_TRUNC('week', created_at) as week,
    AVG(confidence) as avg_confidence,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY confidence) as median_confidence,
    COUNT(*) FILTER (WHERE confidence >= 0.85) as high_confidence_count,
    COUNT(*) as total_decisions
FROM ingredient_actions
GROUP BY week
ORDER BY week DESC;
```

**Target**: Median confidence >0.80 within 6 months

#### 5. Weekly Active Return Rate
```sql
-- Users who return each week after first use
SELECT 
    user_id,
    MIN(DATE(created_at)) as first_use_date,
    COUNT(DISTINCT DATE_TRUNC('week', created_at)) as weeks_active,
    ROUND(
        COUNT(DISTINCT DATE_TRUNC('week', created_at))::NUMERIC / 
        (EXTRACT(DAYS FROM NOW() - MIN(created_at)) / 7)::NUMERIC * 100,
        2
    ) as weekly_return_rate
FROM visual_scan_results
GROUP BY user_id
HAVING COUNT(DISTINCT DATE_TRUNC('week', created_at)) > 1;
```

**Target**: >40% weekly return rate

### Anti-Vanity Metrics (Ignore These)

❌ **Total Scans**: Doesn't indicate value  
❌ **Total Logins**: Doesn't indicate engagement  
❌ **Page Views**: Doesn't indicate impact  
❌ **Total Users**: Doesn't indicate retention  
❌ **Time in App**: Doesn't indicate efficiency  

**Why?** These metrics can be gamed and don't correlate with actual user value.

---

## 📅 Next 30-Day Execution Priorities

### Week 1 (Jan 6-12): Foundation Expansion
- [ ] **Priority 1**: Expand ingredient database to 100+ ingredients
  - Add 30 vegetables, 20 proteins, 10 dairy, 10 grains
  - Include visual features, aliases, storage data
  
- [ ] **Priority 2**: Upload reference images to Supabase Storage
  - Execute: `python services/api/scripts/setup_storage_buckets.py`
  - Apply: `006_storage_buckets_policies.sql`
  - Upload seed images for 37 existing ingredients
  
- [ ] **Priority 3**: Generate embeddings
  - Set OPENAI_API_KEY environment variable
  - Execute: `python services/api/scripts/generate_embeddings.py`
  - Verify: Semantic search functionality

### Week 2 (Jan 13-19): Decision Intelligence
- [ ] **Priority 1**: Create database schema
  - Apply: `007_decision_intelligence.sql`
  - Tables: decision_rules, ingredient_actions
  
- [ ] **Priority 2**: Implement DecisionIntelligenceService
  - Confidence thresholds
  - Rule evaluation engine
  - Auto-action logic
  
- [ ] **Priority 3**: Create FastAPI endpoints
  - POST /api/decision/evaluate-ingredient
  - POST /api/decision/evaluate-inventory
  - POST /api/decision/feedback
  
- [ ] **Priority 4**: Flutter integration
  - DecisionResult model
  - Action UI components
  - Feedback mechanism

### Week 3 (Jan 20-26): Daily Habit Loop
- [ ] **Priority 1**: Create database schema
  - Apply: `008_daily_habit_loop.sql`
  - Tables: daily_digests, user_streaks, passive_learning_signals
  
- [ ] **Priority 2**: Implement DailyHabitService
  - Morning digest generation
  - Evening check-in
  - Streak tracking
  
- [ ] **Priority 3**: Push notification setup
  - Configure Firebase Cloud Messaging
  - Schedule daily digests (8 AM, 6 PM)
  
- [ ] **Priority 4**: Flutter UI
  - Digest display screen
  - Streak visualization
  - Quick action buttons

### Week 4 (Jan 27-Feb 2): Self-Learning Loop
- [ ] **Priority 1**: Create database schema
  - Apply: `009_self_learning_loop.sql`
  - Tables: model_performance_metrics, learning_feedback
  
- [ ] **Priority 2**: Implement feedback processors
  - CV reinforcement logic
  - Substitution ranking updates
  - Decision rule adjustments
  
- [ ] **Priority 3**: Metrics dashboard
  - Confirmation rate tracking
  - Confidence improvement curve
  - Model performance visualization
  
- [ ] **Priority 4**: Automated retraining pipeline
  - Weekly batch updates
  - A/B testing framework
  - Rollback mechanism

---

## 🎯 Success Criteria

### Phase 7: Decision Intelligence
✅ **80%+ of high-confidence decisions** (>0.85) are auto-applied  
✅ **<10% of auto-applied decisions** are reversed by users  
✅ **60%+ acceptance rate** for suggested actions

### Phase 8: Daily Habit Loop
✅ **40%+ digest open rate** within 1 hour of delivery  
✅ **20%+ users engage** with digest content daily  
✅ **30%+ users maintain streak** for >7 days

### Phase 9: Self-Learning Loop
✅ **Human confirmation rate decreases** from 40% → 20% in 60 days  
✅ **Model confidence increases** from 0.75 → 0.82 median  
✅ **Substitution acceptance rate** improves by 15%

### Phase 10: Productization
✅ **Consumer path**: 1,000 active users, 10% conversion to premium  
✅ **B2B path**: 5 pilot restaurants, $500 MRR  
✅ **API path**: 2 integration partners, 100K API calls/month

### Phase 11: Trust & Explainability
✅ **95%+ of decisions include explanation**  
✅ **Zero allergen-related incidents**  
✅ **<5% user trust complaints**

### Phase 12: Impact Metrics
✅ **Scan-to-action rate >60%**  
✅ **Food waste reduction >20%**  
✅ **Time saved >30 min/user/week**  
✅ **Weekly return rate >40%**

---

## 📚 Technical Dependencies

### New Python Packages
```bash
pip install apscheduler  # Daily job scheduling
pip install firebase-admin  # Push notifications
pip install numpy pandas  # Learning calculations
pip install scikit-learn  # Model updates
```

### New Flutter Packages
```yaml
dependencies:
  firebase_messaging: ^14.7.0  # Push notifications
  fl_chart: ^0.66.0  # Metrics visualization
  animations: ^2.0.0  # Smooth transitions
```

### Infrastructure
- **Cron Jobs**: Daily digest generation (8 AM, 6 PM)
- **Background Workers**: Learning loop updates (nightly)
- **Analytics Pipeline**: Metrics calculation (hourly)
- **Monitoring**: Sentry for error tracking

---

## 🚀 Deployment Checklist

### Pre-Launch
- [ ] All 9 new database tables created and tested
- [ ] All 15+ new API endpoints functional
- [ ] All Flutter services integrated and tested
- [ ] Push notifications configured
- [ ] Metrics dashboard deployed
- [ ] Explainability templates finalized
- [ ] Allergen policy reviewed by legal
- [ ] Privacy policy updated
- [ ] Terms of service updated

### Launch
- [ ] Deploy to production environment
- [ ] Enable daily digest scheduling
- [ ] Activate learning loop
- [ ] Monitor error rates
- [ ] Track core metrics
- [ ] Gather user feedback

### Post-Launch (First 7 Days)
- [ ] Daily metric review
- [ ] User feedback analysis
- [ ] Bug fixes and hotfixes
- [ ] Confidence threshold tuning
- [ ] Digest content optimization

---

## 📖 Additional Resources

- [Decision Intelligence Service Documentation](docs/DECISION_INTELLIGENCE.md)
- [Daily Habit Loop Guide](docs/DAILY_HABIT_LOOP.md)
- [Self-Learning Pipeline](docs/SELF_LEARNING_PIPELINE.md)
- [Metrics Dashboard](docs/METRICS_DASHBOARD.md)
- [API Documentation](docs/API_REFERENCE.md)

---

## 🎓 Key Learnings & Philosophy

### Design Principles

1. **Calm Technology**
   - Don't interrupt unnecessarily
   - Provide information at the right time
   - Let users opt-out gracefully

2. **Progressive Disclosure**
   - Show simple decisions first
   - Provide details on demand
   - Don't overwhelm with options

3. **Trust Through Transparency**
   - Always explain why
   - Show confidence levels
   - Admit uncertainty

4. **Learn, Don't Annoy**
   - Track passively when possible
   - Ask for feedback strategically
   - Improve silently in background

5. **Measure Impact, Not Activity**
   - Focus on waste reduction, not scans
   - Track time saved, not time spent
   - Celebrate outcomes, not outputs

---

**Status**: Ready for implementation  
**Next Step**: Create database migration 007 (Decision Intelligence)  
**Estimated Completion**: 4 weeks (Feb 2, 2026)
