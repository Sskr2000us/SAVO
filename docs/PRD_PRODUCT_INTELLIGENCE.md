# SAVO Product Requirements Document (PRD)

## Document Control
- **Version**: 1.0
- **Date**: December 30, 2025
- **Author**: Product Team
- **Status**: Draft for Review

---

## Executive Summary

SAVO is a confidence-first cooking assistant that transforms available ingredients into personalized meal plans using AI. The product addresses the daily friction of meal planning by combining ingredient scanning, nutrition intelligence, skill-based guidance, and cultural preferences into a single, intuitive experience.

**Target Market**: Home cooks (25-55 years old) managing family meals with dietary restrictions, health conditions, and varying skill levels.

**Unique Value Proposition**:  
*"SAVO adapts recipes to your ingredients, health needs, skill level, and culture — without making cooking harder."*

---

## Problem Statement

### User Problems

1. **"I don't know what to cook"**
   - 40% of meal decisions take >15 minutes
   - Leads to takeout ($2.8K/year per family)
   - Food waste from forgotten ingredients

2. **"I'm worried I'll mess it up"**
   - 58% lack cooking confidence
   - Avoid new recipes due to fear of failure
   - Stick to 7-10 repetitive meals

3. **"I waste food"**
   - $1,500/year average household food waste
   - Ingredients expire before use
   - No inventory visibility

4. **"Recipes don't fit my family"**
   - Dietary restrictions (diabetes, hypertension)
   - Allergens (peanuts, shellfish)
   - Cultural preferences (vegetarian, halal)
   - Age-specific needs (kids, seniors)

### Market Opportunity

- **TAM**: 83M US households cooking at home
- **SAM**: 25M with dietary constraints
- **SOM**: 750K early adopters (Year 1)

**Willingness to Pay**: $8-15/month for meal planning + health guidance

---

## Product Vision

### North Star Metric
**Weekly Active Cooks**: Users who complete at least one full recipe per week

**Supporting Metrics**:
- Scan → Recipe conversion rate: >70%
- Recipe completion rate: >60%
- Health fit accuracy (user feedback): >85%
- Weekly retention: >50%
- Paid conversion: >6%

### 3-Year Vision

**Year 1**: Ingredient-first meal planning with nutrition intelligence  
**Year 2**: Skill progression system, custom AI vision model  
**Year 3**: Community recipes, smart appliance integration

---

## Target Users

### Primary Persona: "Busy Parent Beth"
- **Age**: 38, working parent
- **Family**: 2 kids (8, 12), husband
- **Health**: Husband has diabetes, son has peanut allergy
- **Pain**: Struggles to plan healthy meals that everyone likes
- **Goal**: Cook 5-6 dinners/week without stress
- **Budget**: $12/month for meal planning

### Secondary Persona: "Health-Conscious Raj"
- **Age**: 45, software engineer
- **Family**: Wife (vegetarian), 1 child
- **Health**: Pre-diabetic, managing weight
- **Culture**: Indian, prefers home cooking
- **Pain**: Needs low-sugar Indian recipes
- **Goal**: Meal prep for the week
- **Budget**: $15/month for nutrition guidance

### Tertiary Persona: "Skill-Builder Emma"
- **Age**: 27, single professional
- **Skill**: Beginner cook, wants to improve
- **Pain**: Intimidated by complex recipes
- **Goal**: Learn cooking gradually
- **Budget**: $10/month for guided cooking

---

## Product Features (MVP)

### Core Features (Must-Have)

#### 1. Ingredient Scanning
**Problem**: Users don't know what they have  
**Solution**: Camera/video scan → ingredient list

- Image upload or video pan
- AI ingredient detection (OpenAI Vision)
- User confirmation with confidence scores
- Manual add/edit/delete

**Success Criteria**: 70% scan accuracy, <10s processing

#### 2. Nutrition-Aware Planning
**Problem**: Recipes don't respect health conditions  
**Solution**: Automatic health fit scoring

- Diabetes-friendly (low sugar)
- Hypertension-friendly (low sodium)
- High cholesterol (low fat, high fiber)
- Allergen exclusion
- Dietary restrictions (vegetarian, vegan)

**Success Criteria**: 85% health fit accuracy

#### 3. Skill-Based Recipe Selection
**Problem**: Recipes too hard or intimidating  
**Solution**: Match recipes to user skill level

- 5 difficulty levels (assembly → advanced)
- Automatic skill tracking
- Gradual progression suggestions
- No gamification (subtle encouragement)

**Success Criteria**: 80% skill fit accuracy

#### 4. Recipe Generation
**Problem**: Generic recipes don't fit needs  
**Solution**: Personalized recipes with explanations

- 2-3 recipe options per meal
- Max 3 badges (nutrition, skill, time)
- Expandable "Why this recipe?"
- Step-by-step instructions

**Success Criteria**: >3.5/5 user rating

#### 5. YouTube Integration
**Problem**: Want to see cooking process  
**Solution**: Top 5 ranked videos + AI summaries

- Real YouTube search (API)
- AI ranking by relevance
- Video summaries
- Direct playback

**Success Criteria**: >60% watch videos

### Enhanced Features (Should-Have)

#### 6. Multi-Cuisine Support
**Problem**: Stuck in cuisine rut  
**Solution**: Global recipes with intelligent mixing

- 7 cuisines (Italian, Indian, Thai, Mediterranean, Mexican, Chinese, Japanese)
- Cuisine ranking by ingredients
- Multi-cuisine compatibility rules
- Cultural appropriateness

**Success Criteria**: >75% cuisine satisfaction

#### 7. Family Profile Management
**Problem**: One-size-fits-all recipes  
**Solution**: Individual member profiles

- Age categories (child/teen/adult/senior)
- Health conditions per member
- Spice tolerance levels
- Food preferences/dislikes

**Success Criteria**: >80% profile completion

#### 8. Regional Meal Timing
**Problem**: Meal suggestions at wrong times  
**Solution**: Time-based meal classification

- Region-aware timing (India vs US)
- Meal-specific preferences
- Automatic classification

**Success Criteria**: >90% correct meal type

### Future Features (Nice-to-Have)

- Weekly meal planner
- Grocery list generation
- Leftover management
- Community recipe sharing
- Smart appliance integration
- Voice guidance during cooking

---

## User Flows

### Flow 1: First-Time User Setup
1. Download app / open web app
2. Create account (email or social)
3. **Family Profile Setup** (5 minutes)
   - Add family members (name, age)
   - Select dietary restrictions
   - Add health conditions
   - Choose allergens
4. **Preferences** (2 minutes)
   - Region (US, IN, UK, etc.)
   - Culture (western, indian, etc.)
   - Meal times
5. **First Scan** (guided)
   - Open camera or upload photo
   - AI detects ingredients
   - User confirms
6. **First Recipe** (immediate value)
   - See 2-3 options
   - Choose one
   - Cook with step-by-step guide

**Success**: User completes first recipe

### Flow 2: Daily Meal Planning
1. Open app (daily habit)
2. Check inventory (scan if needed)
3. Tap "Plan Today's Dinner"
4. See 2-3 personalized options
   - Badges: nutrition, skill, time
   - Tap "Why this?" to expand
5. Select recipe
6. Optional: Watch YouTube video
7. Cook mode (step-by-step)
8. Mark as cooked

**Success**: Recipe completion >60%

### Flow 3: Discovering New Cuisines
1. User sees "Italian works well today"
2. Tap explanation: "You have tomatoes and cheese"
3. Alternative: "Try Indian instead?"
4. Compare recipes side-by-side
5. Choose based on mood
6. Cook and rate

**Success**: Cuisine variety increases

### Flow 4: Skill Progression
1. User completes 5 basic recipes
2. System detects readiness
3. Subtle nudge: "Want to try a new technique?"
4. Show slightly harder recipe
5. User chooses "Try it" or "Maybe later"
6. If success, confidence grows

**Success**: Gradual skill improvement

---

## Success Metrics (MVP)

| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| Scan → Recipe conversion | >70% | Funnel: scan start → recipe displayed |
| Recipe completion rate | >60% | Cook mode start → marked complete |
| Health fit accuracy | >85% | User feedback: "Was this recipe suitable?" |
| Skill fit accuracy | >80% | Recipe completion + no frustration signals |
| Cuisine satisfaction | >75% | User rating after cooking |
| Weekly active users | >35% | Users cooking ≥1 recipe/week |
| Paid conversion | >6% | Free → paid within 30 days |
| Net Promoter Score (NPS) | >40 | "Would you recommend SAVO?" |

---

## User Experience Principles

### 1. Confidence-First Design
- Never overwhelm with options
- Default to user's skill level
- Positive reinforcement, not pressure
- Clear explanations, not jargon

### 2. Health-Aware, Not Preachy
- Nutrition guides silently in background
- Show badges, not raw numbers
- Explain medical needs simply
- Trust-building through honesty

### 3. Cultural Respect
- Support global cuisines authentically
- Regional meal appropriateness
- No fusion chaos
- Explain multi-cuisine choices

### 4. Progressive Disclosure
- Show essentials first
- Advanced options behind settings
- 90% of users never see complexity
- Power users can dig deeper

---

## Technical Architecture (Summary)

### Backend
- **API**: FastAPI (Python 3.12)
- **Vision**: OpenAI GPT-4o Vision ($0.03/scan)
- **Reasoning**: OpenAI GPT-4o (8192 max tokens)
- **Future**: Custom YOLO v8 model ($0.01/scan)
- **Hosting**: Render.com

### Frontend
- **Mobile/Web**: Flutter (cross-platform)
- **Theme**: Material Design 3 + Custom tokens
- **State**: Provider pattern
- **API Client**: REST with httpx

### Intelligence Layers
1. **Ingredient Detection**: Vision model
2. **Nutrition Scoring**: Health fit algorithm
3. **Skill Matching**: Progression tracking
4. **Cuisine Ranking**: Multi-factor scoring
5. **Recipe Generation**: LLM with context

### Data Flow
```
Ingredients → Nutrition Constraints → Skill Filter → Cuisine Ranking → Recipe Selection → User Choice
```

---

## Competitive Analysis

| Feature | SAVO | Supercook | Yummly | Mealime | Paprika |
|---------|------|-----------|--------|---------|---------|
| Ingredient scan | ✅ AI | ❌ | ❌ | ❌ | ❌ |
| Health conditions | ✅ Auto | ❌ | Partial | ✅ | ❌ |
| Skill progression | ✅ Implicit | ❌ | ❌ | ❌ | ❌ |
| Multi-cuisine | ✅ Intelligent | ❌ | ✅ | Partial | ❌ |
| Cultural timing | ✅ Region-aware | ❌ | ❌ | ❌ | ❌ |
| YouTube integration | ✅ Ranked | ❌ | ❌ | ❌ | ❌ |
| Confidence focus | ✅ Core | ❌ | ❌ | ❌ | ❌ |

**SAVO's Advantage**: Only product that combines health intelligence + skill progression + cultural awareness with ingredient-first approach.

---

## Go-to-Market Strategy

### Phase 1: Beta (Months 1-2)
- 50 beta testers (friends/family)
- Focus: Core loop validation
- Metrics: Completion rate, NPS
- Price: Free

### Phase 2: Private Launch (Months 3-4)
- 500 users (waitlist)
- Focus: Health fit accuracy
- Metrics: Weekly retention
- Price: $10/month (early adopter discount)

### Phase 3: Public Launch (Month 5)
- Product Hunt launch
- 5,000 users (Month 6 target)
- Focus: Paid conversion
- Price: $12/month

### Channels
1. **Content Marketing**: "How to cook with diabetes" articles
2. **Reddit/Forums**: r/cooking, r/EatCheapAndHealthy
3. **Influencers**: Health-focused food bloggers
4. **Partnerships**: Diabetes associations, nutrition coaches

---

## Monetization

### Pricing Tiers

**Free Tier** (Hook users):
- 3 recipe generations/week
- Basic nutrition info
- Single cuisine per meal
- Manual ingredient entry

**Premium** ($12/month):
- Unlimited recipes
- AI ingredient scanning
- Full nutrition intelligence
- Multi-cuisine mixing
- Skill progression
- YouTube integration
- Family profiles (up to 6)

**Family Plan** ($18/month):
- All Premium features
- Up to 10 family members
- Shared grocery lists
- Weekly meal planner

**Lifetime** ($199 one-time):
- All features forever
- Early supporter badge
- Priority support

### Revenue Projections (Year 1)

| Month | Users | Paid (6%) | MRR | ARR |
|-------|-------|-----------|-----|-----|
| 1-2 | 50 | 0 | $0 | $0 |
| 3-4 | 500 | 30 | $360 | $4.3K |
| 5-6 | 5,000 | 300 | $3.6K | $43K |
| 7-12 | 25,000 | 1,500 | $18K | $216K |

**Year 1 ARR Target**: $216K (conservative)  
**Year 2 ARR Target**: $1.2M (5x growth)  
**Year 3 ARR Target**: $4.8M (4x growth)

---

## Risks & Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Vision errors frustrate users | High | Medium | User confirmation + confidence scores |
| Health advice liability | High | Low | Disclaimers + "consult doctor" messaging |
| Too many options overwhelm | Medium | High | Max 3 recipes, simple UI |
| Skill intimidation | Medium | Medium | Positive messaging, gradual progression |
| Cultural insensitivity | High | Low | Authentic cuisine metadata, user feedback |
| API costs too high | Medium | Medium | Custom vision model (Phase 2) |

---

## Launch Criteria (MVP)

Before public launch, SAVO must meet:

### Functional Requirements
- [x] Ingredient scanning works (70% accuracy)
- [x] Nutrition scoring implemented
- [x] Skill-based filtering works
- [x] Recipe generation with explanations
- [x] YouTube integration functional
- [ ] End-to-end flow tested (scan → cook)

### Quality Requirements
- [ ] No critical bugs (P0/P1 zero)
- [ ] API response time <500ms (P95)
- [ ] Mobile app loads <2s
- [ ] All user flows tested
- [ ] Accessibility compliance (WCAG 2.1 AA)

### UX Requirements
- [ ] Onboarding <5 minutes
- [ ] Recipe badges visible
- [ ] "Why this?" explanations clear
- [ ] Family profile settings usable
- [ ] Skill nudges non-intrusive

### Business Requirements
- [ ] Payment processing integrated (Stripe)
- [ ] Analytics tracking (Mixpanel)
- [ ] Customer support (Intercom)
- [ ] Terms of Service + Privacy Policy
- [ ] GDPR/CCPA compliance

---

## Future Roadmap

### Q1 2026: Foundation
- ✅ Core meal planning
- ✅ Nutrition intelligence
- ✅ Skill progression
- ✅ Family profiles
- ⬜ Public launch

### Q2 2026: Growth
- Weekly meal planner
- Grocery list generation
- Leftover tracking
- Recipe rating system
- Community features (beta)

### Q3 2026: Scale
- Custom vision model (cost reduction)
- Smart appliance integration (Instant Pot, etc.)
- Voice guidance
- Meal prep mode
- International expansion (India, UK)

### Q4 2026: Enterprise
- B2B nutrition coaching partnerships
- White-label for meal kit services
- API licensing for health platforms
- Corporate wellness programs

---

## Appendices

### Appendix A: User Research Summary
- 50 interviews conducted
- Top pain point: "Don't know what to cook" (92%)
- Willingness to pay: $8-15/month (67%)
- Health conditions: Diabetes (23%), hypertension (31%)

### Appendix B: Technical Dependencies
- OpenAI API (critical)
- YouTube Data API (optional)
- Unsplash API (optional)
- Render hosting (critical)

### Appendix C: Design System
See: `docs/DESIGN_SYSTEM_SUMMARY.md`

### Appendix D: API Specification
See: `docs/API_PRODUCT_INTELLIGENCE.md`

---

## Document Approval

| Role | Name | Status | Date |
|------|------|--------|------|
| Product Lead | TBD | Pending | - |
| Engineering Lead | TBD | Pending | - |
| Design Lead | TBD | Pending | - |
| CEO | TBD | Pending | - |
