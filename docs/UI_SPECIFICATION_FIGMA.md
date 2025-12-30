# SAVO UI Specification - Figma-Ready Annotations

## Document Control
- **Version**: 1.0 for Figma Implementation
- **Last Updated**: December 30, 2025
- **Design Tool**: Figma
- **Design System**: Material Design 3 + SAVO Custom Tokens

---

## Overview

This document provides pixel-perfect specifications for all UI components related to SAVO's product intelligence features. Designers can use these annotations to create high-fidelity mockups in Figma.

**Design Principles**:
1. **Confidence-First**: Never overwhelm users
2. **Progressive Disclosure**: Show essentials, hide complexity
3. **Cultural Respect**: Global cuisines with authenticity
4. **Health-Aware**: Guide silently, explain clearly

---

## Color Tokens

### Core Colors
```
Primary:
  - primary-50: #E8F5E9
  - primary-100: #C8E6C9
  - primary-500: #4CAF50 (Main)
  - primary-700: #388E3C (Dark)
  - primary-900: #1B5E20

Secondary (Warm Orange):
  - secondary-50: #FFF3E0
  - secondary-500: #FF9800
  - secondary-700: #F57C00

Background:
  - surface: #FFFFFF
  - surface-variant: #F5F5F5
  - background: #FAFAFA

Text:
  - text-primary: #212121 (87% opacity)
  - text-secondary: #757575 (60% opacity)
  - text-disabled: #BDBDBD (38% opacity)

Status Colors:
  - success: #4CAF50
  - warning: #FFC107
  - error: #F44336
  - info: #2196F3

Badge Colors:
  - nutrition-bg: #E8F5E9 (light green)
  - nutrition-text: #2E7D32
  - skill-bg: #FFF3E0 (light orange)
  - skill-text: #E65100
  - time-bg: #E3F2FD (light blue)
  - time-text: #1565C0
```

### Semantic Colors
```
Health Conditions:
  - diabetes-alert: #FFF3E0 (warning tint)
  - hypertension-alert: #E3F2FD (info tint)
  - allergen-alert: #FFEBEE (error tint)

Skill Levels:
  - beginner: #4CAF50 (green)
  - intermediate: #2196F3 (blue)
  - advanced: #9C27B0 (purple)
```

---

## Typography

### Font Family
**Primary**: Roboto (Material Design standard)  
**Fallback**: System UI fonts (San Francisco on iOS, Roboto on Android)

### Type Scale
```
Display Large:
  - Size: 57px
  - Weight: 400 (Regular)
  - Line Height: 64px
  - Use: Hero text (rare)

Headline Medium:
  - Size: 28px
  - Weight: 400
  - Line Height: 36px
  - Use: Screen titles

Headline Small:
  - Size: 24px
  - Weight: 400
  - Line Height: 32px
  - Use: Section headers

Title Large:
  - Size: 22px
  - Weight: 500 (Medium)
  - Line Height: 28px
  - Use: Recipe titles

Title Medium:
  - Size: 16px
  - Weight: 500
  - Line Height: 24px
  - Use: Card titles

Body Large:
  - Size: 16px
  - Weight: 400
  - Line Height: 24px
  - Use: Primary body text

Body Medium:
  - Size: 14px
  - Weight: 400
  - Line Height: 20px
  - Use: Secondary text, instructions

Label Large:
  - Size: 14px
  - Weight: 500
  - Line Height: 20px
  - Use: Button text

Label Medium:
  - Size: 12px
  - Weight: 500
  - Line Height: 16px
  - Use: Badge labels

Label Small:
  - Size: 11px
  - Weight: 500
  - Line Height: 16px
  - Use: Captions, metadata
```

---

## Spacing System

**8px Base Unit** (consistent with Material Design)

```
spacing-1: 4px
spacing-2: 8px
spacing-3: 12px
spacing-4: 16px
spacing-5: 20px
spacing-6: 24px
spacing-8: 32px
spacing-10: 40px
spacing-12: 48px
spacing-16: 64px
```

**Common Usage**:
- Card padding: 16px
- Between elements: 8px
- Section margins: 24px
- Screen edge margin: 16px (mobile), 24px (tablet)

---

## Component Library

### 1. Recipe Badge Component

**Purpose**: Display max 3 badges (nutrition, skill, time) on recipe cards.

**Anatomy**:
```
┌─────────────────────┐
│ 🟢 Balanced         │  ← Badge
└─────────────────────┘

Components:
  - Icon (16x16px emoji or icon)
  - Label (Label Medium, 12px)
  - Background (rounded pill)
```

**Specifications**:
```
Container:
  - Height: 24px
  - Padding: 4px 8px
  - Border Radius: 12px (pill shape)
  - Background: badge-specific color (see color tokens)

Icon:
  - Size: 16x16px
  - Margin Right: 4px
  - Use emoji for simplicity

Label:
  - Font: Label Medium (12px, weight 500)
  - Color: badge-specific text color
  - Max Width: 80px (truncate with ellipsis)

Spacing:
  - Between badges: 8px horizontal
  - From recipe image: 12px top
```

**Badge Types**:
```
Nutrition Badges:
  🟢 Balanced           (green bg, dark green text)
  💪 High Protein       (green bg, dark green text)
  🫀 Heart Healthy      (blue bg, dark blue text)
  🧠 Brain Food         (purple bg, dark purple text)
  🦴 Bone Health        (orange bg, dark orange text)
  ⚡ Energy Boost       (yellow bg, dark yellow text)

Skill Badges:
  ⭐ Easy               (orange bg, dark orange text)
  📚 Learn Something    (orange bg, dark orange text)
  🎯 Perfect Match      (orange bg, dark orange text)

Time Badges:
  ⏱ 20 min             (blue bg, dark blue text)
  ⏱ 30 min             (blue bg, dark blue text)
  ⏱ 45 min             (blue bg, dark blue text)
```

**Badge Priority (Max 3)**:
1. Nutrition (most important)
2. Skill
3. Time

**Example Layout**:
```
┌────────────────────────────────────────┐
│  [Recipe Image]                        │
│                                        │
│  🟢 Balanced  ⭐ Easy  ⏱ 30 min        │ ← Max 3 badges
│                                        │
│  Chicken Tikka Masala                  │
│  Indian · 4 servings                   │
└────────────────────────────────────────┘
```

**Figma Frame Name**: `Badge/RecipeBadge`  
**Auto Layout**: Yes (horizontal, 8px gap)  
**Variants**: nutrition | skill | time

---

### 2. "Why This Recipe?" Expandable Card

**Purpose**: Show simple explanation of why recipe was chosen.

**Anatomy**:
```
┌────────────────────────────────────────┐
│  Why this recipe?              [▼]     │  ← Collapsed header
└────────────────────────────────────────┘

↓ Taps to expand ↓

┌────────────────────────────────────────┐
│  Why this recipe?              [▲]     │  ← Expanded header
├────────────────────────────────────────┤
│                                        │
│  ✅ Health: Balanced nutrition         │
│  You have diabetes, and this recipe    │
│  has low sugar (8g per serving).       │
│                                        │
│  🍳 Skill: Easy for you                │
│  Matches your current level. Uses      │
│  pan-frying, which you've done before. │
│                                        │
│  🌍 Cuisine: Indian                    │
│  Uses cumin and turmeric you have.     │
│  Fits your family's preferences.       │
│                                        │
└────────────────────────────────────────┘
```

**Specifications**:
```
Container:
  - Background: surface-variant (#F5F5F5)
  - Border Radius: 12px
  - Padding: 16px
  - Margin: 16px (from screen edges)

Header:
  - Font: Title Medium (16px, weight 500)
  - Color: text-primary
  - Icon: chevron-down (collapsed) / chevron-up (expanded)
  - Icon Size: 24x24px
  - Icon Color: text-secondary

Content (Expanded):
  - Padding Top: 12px
  - Border Top: 1px solid #E0E0E0

Section Format:
  - Icon: 16x16px emoji
  - Title: Label Large (14px, weight 500)
  - Description: Body Medium (14px, weight 400, color: text-secondary)
  - Spacing Between Sections: 16px

Interaction:
  - Tap anywhere on header to expand/collapse
  - Animation: 300ms ease-in-out
  - Expand: Fade in content + slide down
  - Collapse: Fade out content + slide up
```

**Content Rules**:
- Always show 2-4 sections (Health, Skill, Cuisine, Time)
- Each section: 1-2 sentences max
- Use simple language (6th-grade reading level)
- Never show raw numbers unless critical

**Figma Frame Name**: `Card/WhyThisRecipe`  
**States**: collapsed | expanded  
**Auto Layout**: Yes (vertical, 12px gap)

---

### 3. Skill Nudge Toast

**Purpose**: Non-intrusive suggestion to try slightly harder recipe.

**Anatomy**:
```
┌────────────────────────────────────────────────────┐
│  🎯 Want to try a slightly new technique?          │
│                                                    │
│  [Try It]              [Maybe Later]               │
└────────────────────────────────────────────────────┘
```

**Specifications**:
```
Container:
  - Position: Bottom of screen, above navigation bar
  - Height: auto (min 80px)
  - Width: Screen width - 32px (16px margins)
  - Background: #FFFFFF
  - Border Radius: 12px
  - Elevation: 8dp (Material shadow)
  - Padding: 16px

Message:
  - Font: Body Large (16px)
  - Color: text-primary
  - Icon: 24x24px emoji (🎯, ⭐, 📚)
  - Icon Position: Left of text, margin-right 8px

Buttons:
  - Layout: Horizontal, aligned right
  - Spacing: 8px between buttons
  - Height: 40px
  - Border Radius: 20px (pill)

  Primary Button ("Try It"):
    - Background: primary-500
    - Text: #FFFFFF
    - Padding: 12px 24px
    - Font: Label Large (14px, weight 500)

  Secondary Button ("Maybe Later"):
    - Background: transparent
    - Text: primary-700
    - Border: 1px solid primary-500
    - Padding: 12px 24px
    - Font: Label Large (14px, weight 500)

Animation:
  - Slide up from bottom: 400ms ease-out
  - Auto-dismiss after 10s (fade out + slide down)
  - User can swipe down to dismiss

When to Show:
  - After 3-5 successful meals at same level
  - Never more than once per week
  - Only during recipe browsing (not while cooking)
```

**Copy Examples**:
```
✅ Good:
  "Want to try a slightly new technique?"
  "Ready to explore something new?"
  "You've got this! Try a new skill?"

❌ Bad:
  "Level up to Intermediate!" (too gamified)
  "Master these 5 skills!" (too intimidating)
  "Unlock Advanced Recipes!" (too pushy)
```

**Figma Frame Name**: `Toast/SkillNudge`  
**Position**: Overlay, bottom-aligned  
**Auto Layout**: Yes (vertical, 12px gap)

---

### 4. Multi-Cuisine Indicator

**Purpose**: Show when multiple cuisines are combined in a meal.

**Anatomy**:
```
┌────────────────────────────────────────┐
│  🌍 Balanced Meal                [?]   │  ← Badge with info icon
└────────────────────────────────────────┘

↓ Taps info icon ↓

┌────────────────────────────────────────┐
│  Multi-Cuisine Meal                    │
│                                        │
│  We mixed cuisines to match your       │
│  health needs, ingredients, and effort.│
│                                        │
│  Starter: Mediterranean (salad)        │
│  Main: Indian (curry)                  │
│                                        │
│  These cuisines work well together     │
│  because they share prep steps and     │
│  don't have conflicting flavors.       │
│                                        │
│                       [Got It]         │
└────────────────────────────────────────┘
```

**Specifications**:
```
Badge:
  - Height: 28px
  - Padding: 6px 12px
  - Border Radius: 14px
  - Background: #E8F5E9 (light green)
  - Border: 1px solid #4CAF50

Badge Label:
  - Icon: 🌍 (16x16px)
  - Text: "Balanced Meal"
  - Font: Label Medium (12px, weight 500)
  - Color: #2E7D32 (dark green)

Info Icon:
  - Size: 16x16px
  - Color: text-secondary
  - Margin Left: 4px
  - Tap area: 44x44px (accessible)

Modal (Info Expanded):
  - Type: Bottom sheet
  - Height: auto (min 200px, max 60% screen)
  - Background: #FFFFFF
  - Border Radius Top: 20px
  - Padding: 24px

Modal Title:
  - Font: Title Large (22px, weight 500)
  - Color: text-primary
  - Margin Bottom: 16px

Modal Body:
  - Font: Body Large (16px)
  - Color: text-secondary
  - Line Height: 24px
  - Spacing Between Paragraphs: 12px

Course List:
  - Format: "Course: Cuisine (dish type)"
  - Font: Body Medium (14px, weight 500)
  - Color: text-primary
  - Bullet: None (use line breaks)
  - Spacing: 8px between courses

Button ("Got It"):
  - Height: 48px
  - Width: 100%
  - Background: primary-500
  - Text: #FFFFFF
  - Font: Label Large (14px, weight 500)
  - Border Radius: 24px
  - Margin Top: 24px
```

**When to Show**:
- Only when 2+ cuisines are mixed
- Display prominently on recipe card
- Auto-show explanation on first multi-cuisine meal
- After that, user can tap "?" to see details

**Figma Frame Name**: `Badge/MultiCuisine` + `Modal/MultiCuisineInfo`  
**Interaction**: Badge → Bottom Sheet Modal

---

### 5. Recipe Card (Enhanced)

**Purpose**: Display recipe with all intelligence features.

**Anatomy**:
```
┌────────────────────────────────────────┐
│                                        │
│        [Recipe Image 16:9]             │  ← Hero image
│                                        │
│  🟢 Balanced  ⭐ Easy  ⏱ 30 min        │  ← Max 3 badges
│                                        │
│  Chicken Tikka Masala                  │  ← Title
│  Indian · 4 servings · 450 cal         │  ← Metadata
│                                        │
│  ❤️ Saved by 342 users                 │  ← Social proof (optional)
│                                        │
│  [Why this recipe?]            [▼]     │  ← Expandable explanation
│                                        │
└────────────────────────────────────────┘
```

**Specifications**:
```
Container:
  - Width: Screen width - 32px (16px margins)
  - Background: #FFFFFF
  - Border Radius: 16px
  - Elevation: 2dp (subtle shadow)
  - Padding: 0 (image full-bleed)

Recipe Image:
  - Aspect Ratio: 16:9
  - Border Radius Top: 16px
  - Object Fit: cover
  - Lazy Load: Yes
  - Fallback: Gradient placeholder

Badge Container:
  - Position: Over image, bottom-left
  - Background: rgba(0,0,0,0.3) (dark overlay)
  - Padding: 8px 12px
  - Border Radius Bottom Left: 16px
  - Max Badges: 3 (priority: nutrition > skill > time)

Content Padding:
  - Padding: 16px (all sides except top)

Title:
  - Font: Title Large (22px, weight 500)
  - Color: text-primary
  - Max Lines: 2 (ellipsis)
  - Margin Top: 12px

Metadata:
  - Font: Body Medium (14px)
  - Color: text-secondary
  - Format: "Cuisine · Servings · Calories"
  - Separator: " · " (middle dot with spaces)
  - Margin Top: 4px

Social Proof (Optional):
  - Font: Label Medium (12px)
  - Color: text-secondary
  - Icon: ❤️ 16x16px
  - Margin Top: 8px
  - Display: Only if >100 saves

Expandable Section:
  - See "Why This Recipe?" component above
  - Margin Top: 16px
  - Margin Bottom: 16px

Interaction:
  - Tap card → Recipe detail screen
  - Tap "Why this?" → Expand explanation
  - Long press → Add to favorites (haptic feedback)
```

**Responsive Behavior**:
```
Mobile (< 600px):
  - Width: Screen width - 32px
  - Single column

Tablet (600px - 1024px):
  - Width: 50% - 24px (2 columns)
  - Gap: 16px

Desktop (> 1024px):
  - Width: 33.33% - 24px (3 columns)
  - Max Width: 400px
```

**Figma Frame Name**: `Card/RecipeCard`  
**Auto Layout**: Yes (vertical, 12px gap)  
**Variants**: default | expanded | favorited

---

### 6. Recipe Detail Screen

**Purpose**: Full recipe with step-by-step instructions.

**Layout Structure**:
```
┌────────────────────────────────────────┐
│  [← Back]         Chicken Tikka        │  ← Header (sticky)
├────────────────────────────────────────┤
│                                        │
│        [Hero Image 1:1]                │  ← Square image
│                                        │
│  🟢 Balanced  ⭐ Easy  ⏱ 30 min        │
│                                        │
├────────────────────────────────────────┤
│  Chicken Tikka Masala                  │  ← Title
│  Indian · 4 servings · 450 cal         │
│                                        │
│  [Why this recipe?]            [▼]     │  ← Expandable
│                                        │
├────────────────────────────────────────┤
│  Ingredients                           │  ← Section
│  ☐ 1 lb chicken breast                 │
│  ☐ 1 cup yogurt                        │
│  ☐ 2 tbsp garam masala                 │
│  ...                                   │
│                                        │
├────────────────────────────────────────┤
│  Instructions                          │  ← Section
│                                        │
│  Step 1: Marinate chicken              │
│  In a bowl, mix yogurt and spices...   │
│                                        │
│  Step 2: Cook onions                   │
│  Heat oil in pan, add onions...        │
│  ...                                   │
│                                        │
├────────────────────────────────────────┤
│  YouTube Videos (Top 5)                │  ← Section
│  [Video Thumbnail 1]                   │
│  "Best Tikka Masala" - 2M views        │
│  ...                                   │
│                                        │
├────────────────────────────────────────┤
│  [Start Cooking]                       │  ← CTA button (sticky bottom)
└────────────────────────────────────────┘
```

**Specifications**:
```
Header (Sticky):
  - Height: 56px
  - Background: #FFFFFF
  - Border Bottom: 1px solid #E0E0E0
  - Padding: 0 16px
  - Z-Index: 10

  Back Button:
    - Icon: arrow-left
    - Size: 24x24px
    - Tap Area: 48x48px
    - Color: text-primary

  Title (Header):
    - Font: Title Medium (16px, weight 500)
    - Color: text-primary
    - Max Width: 70% (truncate)
    - Center-aligned

Hero Image:
  - Aspect Ratio: 1:1 (square)
  - Width: 100%
  - Object Fit: cover
  - Parallax Scroll: Optional

Content Padding:
  - Padding: 16px (horizontal)
  - Padding: 24px (vertical between sections)

Section Title:
  - Font: Headline Small (24px, weight 400)
  - Color: text-primary
  - Margin Bottom: 16px

Ingredients List:
  - Font: Body Large (16px)
  - Color: text-primary
  - Checkbox: 24x24px (Material Design)
  - Checkbox Color: primary-500
  - Spacing: 12px between items
  - Tap checkbox to mark as checked

Instructions:
  - Font: Body Large (16px)
  - Color: text-primary
  - Line Height: 24px
  - Step Number: Label Large (14px, weight 500, color: primary-700)
  - Spacing: 20px between steps

YouTube Videos:
  - See "YouTube Video Card" component below
  - Display: Top 5 videos
  - Spacing: 16px between cards

CTA Button (Sticky Bottom):
  - Height: 56px
  - Width: Screen width - 32px
  - Background: primary-500
  - Text: "Start Cooking"
  - Font: Label Large (14px, weight 500)
  - Color: #FFFFFF
  - Border Radius: 28px
  - Shadow: 4dp elevation
  - Padding: 0 24px
  - Margin: 16px (all sides)
  - Position: Fixed bottom

Interaction:
  - Tap checkbox → Mark ingredient checked
  - Tap step → Expand to full-screen (cooking mode)
  - Tap video → Open YouTube player (in-app)
  - Tap "Start Cooking" → Full-screen cooking mode
```

**Figma Frame Name**: `Screen/RecipeDetail`  
**Scroll Behavior**: Vertical scroll, sticky header + sticky CTA

---

### 7. YouTube Video Card

**Purpose**: Display ranked YouTube video with AI summary.

**Anatomy**:
```
┌────────────────────────────────────────┐
│  [Thumbnail 16:9]            [▶]       │  ← Thumbnail + play icon
│                                        │
│  Best Chicken Tikka Masala Recipe      │  ← Video title
│  Chef John · 2.3M views · 2 years ago  │  ← Metadata
│                                        │
│  ⭐ 92% match · Clear instructions      │  ← AI ranking + summary
│                                        │
└────────────────────────────────────────┘
```

**Specifications**:
```
Container:
  - Width: 100%
  - Background: surface-variant (#F5F5F5)
  - Border Radius: 12px
  - Padding: 12px
  - Margin Bottom: 12px

Thumbnail:
  - Aspect Ratio: 16:9
  - Width: 100%
  - Border Radius: 8px
  - Object Fit: cover

Play Icon:
  - Position: Absolute, center of thumbnail
  - Size: 48x48px
  - Background: rgba(0,0,0,0.7)
  - Border Radius: 50% (circle)
  - Icon: play-arrow (24x24px, white)

Video Title:
  - Font: Title Medium (16px, weight 500)
  - Color: text-primary
  - Max Lines: 2 (ellipsis)
  - Margin Top: 8px

Metadata:
  - Font: Body Medium (14px)
  - Color: text-secondary
  - Format: "Channel · Views · Age"
  - Separator: " · "
  - Margin Top: 4px

AI Ranking:
  - Font: Label Medium (12px, weight 500)
  - Color: primary-700
  - Icon: ⭐ (16x16px)
  - Format: "XX% match"
  - Margin Top: 8px

AI Summary:
  - Font: Body Medium (14px)
  - Color: text-secondary
  - Max Lines: 2 (ellipsis)
  - Examples: "Clear instructions", "Beginner-friendly", "Fast version"

Interaction:
  - Tap anywhere → Open YouTube player (in-app)
  - Long press → Open in YouTube app
```

**Ranking Badges** (Optional):
```
High Match (>85%):
  🟢 Highly Recommended

Good Match (70-84%):
  🟡 Good Option

Lower Match (<70%):
  (No badge)
```

**Figma Frame Name**: `Card/YouTubeVideo`  
**Auto Layout**: Yes (vertical, 8px gap)

---

### 8. Family Member Profile Card (Settings)

**Purpose**: Configure individual family member profiles.

**Anatomy**:
```
┌────────────────────────────────────────┐
│  👤 Sarah (Mom)                 [Edit] │  ← Name + avatar
├────────────────────────────────────────┤
│  Age: Adult (35)                       │
│  Health: Diabetes                      │
│  Allergies: None                       │
│  Spice Tolerance: Medium               │
│                                        │
│  [Remove Member]                       │
└────────────────────────────────────────┘
```

**Specifications**:
```
Container:
  - Width: 100%
  - Background: #FFFFFF
  - Border Radius: 12px
  - Elevation: 1dp
  - Padding: 16px
  - Margin Bottom: 16px

Header:
  - Layout: Horizontal, space-between
  - Avatar: 40x40px circle
  - Name: Title Medium (16px, weight 500)
  - Edit Button: text-button (primary-700)

Content:
  - Font: Body Medium (14px)
  - Color: text-secondary
  - Spacing: 8px between rows
  - Format: "Label: Value"

Remove Button:
  - Width: 100%
  - Height: 40px
  - Background: transparent
  - Border: 1px solid error
  - Text: error color
  - Font: Label Large (14px, weight 500)
  - Border Radius: 20px
  - Margin Top: 16px

Interaction:
  - Tap "Edit" → Open edit modal
  - Tap "Remove" → Confirmation dialog
```

**Figma Frame Name**: `Card/FamilyMemberProfile`  
**Auto Layout**: Yes (vertical, 8px gap)

---

## Screen Layouts

### 1. Recipe Browse Screen (Home)

**Purpose**: Main discovery screen with personalized recipes.

**Layout**:
```
┌────────────────────────────────────────┐
│  Good evening, Sarah            [⚙️]   │  ← Header (greeting + settings)
├────────────────────────────────────────┤
│                                        │
│  🍽 What's for dinner?                 │  ← Prompt
│                                        │
│  [Scan Ingredients] [Manual Entry]     │  ← Action buttons
│                                        │
├────────────────────────────────────────┤
│  Today's Recommendations               │  ← Section title
│                                        │
│  [Recipe Card 1]                       │  ← Recipe cards
│  [Recipe Card 2]                       │
│  [Recipe Card 3]                       │
│                                        │
├────────────────────────────────────────┤
│  Explore Cuisines                      │  ← Section
│  [Italian] [Indian] [Thai] [More]      │  ← Chips
│                                        │
└────────────────────────────────────────┘
```

**Specifications**:
- Screen Padding: 16px (horizontal)
- Section Spacing: 32px (vertical)
- Greeting: Headline Medium (28px)
- Recipe Cards: Stacked vertically, 16px gap
- Max Recipes Per Screen: 10 (infinite scroll)

**Figma Frame Name**: `Screen/RecipeBrowse`

---

### 2. Settings Screen (Family Profile)

**Purpose**: Configure family profiles and preferences.

**Layout**:
```
┌────────────────────────────────────────┐
│  [← Back]         Settings             │  ← Header
├────────────────────────────────────────┤
│                                        │
│  Family Members                        │  ← Section
│                                        │
│  [Family Member Card: Sarah]           │
│  [Family Member Card: John]            │
│  [Family Member Card: Emma]            │
│                                        │
│  [+ Add Family Member]                 │
│                                        │
├────────────────────────────────────────┤
│  Regional Settings                     │  ← Section
│  Region: United States                 │
│  Culture: Western                      │
│  Meal Times: Customize                 │
│                                        │
├────────────────────────────────────────┤
│  Preferences                           │  ← Section
│  Favorite Cuisines: Italian, Indian    │
│  Avoid: Seafood                        │
│                                        │
└────────────────────────────────────────┘
```

**Specifications**:
- Screen Padding: 16px
- Section Spacing: 24px
- Section Titles: Headline Small (24px)
- Settings already implemented in `settings_screen.dart`

**Figma Frame Name**: `Screen/Settings`

---

### 3. Cooking Mode (Full-Screen)

**Purpose**: Step-by-step cooking guidance.

**Layout**:
```
┌────────────────────────────────────────┐
│  Step 2 of 8                    [X]    │  ← Progress + exit
├────────────────────────────────────────┤
│                                        │
│  Cook onions until golden              │  ← Step title (large)
│                                        │
│  Heat 2 tbsp oil in a large pan over  │  ← Step details
│  medium heat. Add sliced onions and    │
│  cook for 5-7 minutes, stirring        │
│  occasionally, until golden brown.     │
│                                        │
│  [Start Timer: 7 min]                  │  ← Optional timer
│                                        │
├────────────────────────────────────────┤
│  [← Previous]           [Next →]       │  ← Navigation
└────────────────────────────────────────┘
```

**Specifications**:
```
Background: #FFFFFF
Screen Padding: 24px

Progress Bar:
  - Height: 4px
  - Background: #E0E0E0
  - Progress: primary-500
  - Position: Top of screen

Step Counter:
  - Font: Label Large (14px, weight 500)
  - Color: text-secondary
  - Position: Top-left

Exit Button:
  - Icon: close (24x24px)
  - Tap Area: 48x48px
  - Position: Top-right

Step Title:
  - Font: Headline Medium (28px)
  - Color: text-primary
  - Margin Top: 32px

Step Details:
  - Font: Body Large (16px)
  - Color: text-secondary
  - Line Height: 24px
  - Margin Top: 16px

Timer Button (Optional):
  - Height: 48px
  - Background: secondary-500
  - Text: #FFFFFF
  - Border Radius: 24px
  - Margin Top: 24px

Navigation Buttons:
  - Position: Bottom of screen
  - Layout: Horizontal, space-between
  - Height: 56px
  - Width: 48%
  - Border Radius: 28px

  Previous:
    - Background: surface-variant
    - Text: text-primary
    - Icon: arrow-left

  Next:
    - Background: primary-500
    - Text: #FFFFFF
    - Icon: arrow-right

Interaction:
  - Swipe left → Next step
  - Swipe right → Previous step
  - Tap timer → Start countdown
  - Tap exit → Confirmation dialog
```

**Figma Frame Name**: `Screen/CookingMode`

---

## Interaction Patterns

### 1. Expand/Collapse Animation

**Trigger**: Tap "Why this recipe?" header

**Animation**:
```
Duration: 300ms
Easing: ease-in-out

Expand:
  1. Rotate chevron icon 180° (0ms-150ms)
  2. Fade in content opacity 0 → 1 (150ms-300ms)
  3. Slide content down translate-y(-20px → 0) (150ms-300ms)

Collapse:
  1. Fade out content opacity 1 → 0 (0ms-150ms)
  2. Slide content up translate-y(0 → -20px) (0ms-150ms)
  3. Rotate chevron icon 0° (150ms-300ms)
```

### 2. Badge Reveal Animation

**Trigger**: Recipe card appears on screen

**Animation**:
```
Duration: 600ms
Easing: ease-out
Stagger: 100ms between badges

Per Badge:
  1. Scale from 0.8 → 1.0 (0ms-300ms)
  2. Fade in opacity 0 → 1 (0ms-300ms)
  3. Slide in from left translate-x(-20px → 0) (0ms-300ms)
```

### 3. Recipe Card Press

**Trigger**: Tap recipe card

**Animation**:
```
Duration: 200ms
Easing: ease-in

Press:
  - Scale: 0.98
  - Opacity: 0.9
  - Shadow: Reduce from 2dp → 1dp

Release:
  - Scale: 1.0
  - Opacity: 1.0
  - Shadow: Restore to 2dp
  - Navigate to detail screen (slide-up transition)
```

### 4. Skill Nudge Toast

**Trigger**: After 3-5 successful meals

**Animation**:
```
Enter:
  Duration: 400ms
  Easing: ease-out
  1. Slide up from bottom translate-y(100px → 0)
  2. Fade in opacity 0 → 1

Auto-Dismiss (10s):
  Duration: 400ms
  Easing: ease-in
  1. Fade out opacity 1 → 0
  2. Slide down translate-y(0 → 100px)

User Dismiss (swipe down):
  Duration: 200ms
  Easing: ease-in
  Follow swipe gesture
```

---

## Accessibility (WCAG 2.1 AA)

### Color Contrast

All text must meet minimum contrast ratios:
```
Normal Text (16px):
  - text-primary on surface: 4.5:1 ✅
  - text-secondary on surface: 4.5:1 ✅

Large Text (24px+):
  - text-primary on surface: 3:1 ✅

Badges:
  - nutrition-text on nutrition-bg: 4.5:1 ✅
  - skill-text on skill-bg: 4.5:1 ✅
  - time-text on time-bg: 4.5:1 ✅
```

### Touch Targets

Minimum tap area: 44x44px (iOS) / 48x48px (Android)
```
All interactive elements:
  - Buttons: ✅ 48px height
  - Checkboxes: ✅ 48x48px tap area
  - Icons: ✅ 48x48px tap area (even if icon is 24x24px)
  - Links: ✅ 48px height (line-height padding)
```

### Screen Reader Support

All components must have:
```
- Semantic labels (role, label, hint)
- Focus order (logical tab order)
- State announcements (expanded/collapsed, checked/unchecked)
- Error messages (clear, actionable)

Examples:
  - Badge: "Balanced nutrition badge"
  - "Why this?" button: "Expand recipe explanation"
  - Recipe card: "Chicken Tikka Masala recipe, Balanced, Easy, 30 minutes"
```

### Keyboard Navigation (Desktop)

All actions accessible via keyboard:
```
- Tab: Move focus
- Shift+Tab: Move focus backward
- Enter/Space: Activate button
- Arrow keys: Navigate lists
- Esc: Close modals/dialogs
```

---

## Responsive Breakpoints

### Mobile First

```
Small Phone (< 360px):
  - Font sizes: -1px (e.g., 16px → 15px)
  - Padding: 12px (reduced from 16px)
  - Recipe cards: Full width

Medium Phone (360px - 600px):
  - Standard sizes (as specified above)
  - Recipe cards: Full width

Tablet (600px - 1024px):
  - Recipe cards: 2 columns
  - Padding: 24px (increased)
  - Font sizes: +2px for titles

Desktop (> 1024px):
  - Recipe cards: 3 columns (max 400px each)
  - Max content width: 1200px (centered)
  - Font sizes: +4px for titles
```

---

## Design System Checklist

Before finalizing Figma files, ensure:

### Colors
- [ ] All color tokens defined in Figma styles
- [ ] Contrast ratios validated (WCAG AA)
- [ ] Dark mode variants (future)

### Typography
- [ ] All text styles defined in Figma
- [ ] Font weights available (400, 500, 700)
- [ ] Line heights consistent

### Components
- [ ] All components in library
- [ ] Variants defined (default, hover, pressed, disabled)
- [ ] Auto-layout configured
- [ ] Responsive behavior noted

### Spacing
- [ ] 8px grid used consistently
- [ ] All spacing tokens defined
- [ ] Component padding standardized

### Iconography
- [ ] Icon library defined (Material Icons or custom)
- [ ] Icon sizes standardized (16px, 24px, 48px)
- [ ] Icon colors mapped to tokens

### Animations
- [ ] Transition durations documented
- [ ] Easing curves specified
- [ ] Stagger delays noted

---

## Figma File Structure

Recommended organization:

```
SAVO Design System
├── 🎨 Foundation
│   ├── Colors
│   ├── Typography
│   ├── Spacing
│   └── Icons
│
├── 🧩 Components
│   ├── Badges
│   │   ├── RecipeBadge
│   │   └── MultiCuisineBadge
│   ├── Cards
│   │   ├── RecipeCard
│   │   ├── WhyThisRecipe
│   │   ├── YouTubeVideo
│   │   └── FamilyMemberProfile
│   ├── Buttons
│   ├── Inputs
│   └── Toasts
│       └── SkillNudge
│
├── 📱 Screens
│   ├── RecipeBrowse
│   ├── RecipeDetail
│   ├── Settings
│   └── CookingMode
│
└── 🎬 Prototypes
    ├── User Flow 1: First Time
    ├── User Flow 2: Daily Planning
    └── User Flow 3: Cooking Mode
```

---

## Handoff Notes

### For Developers

1. **Component Mapping**:
   - Figma components → Flutter widgets 1:1
   - Use existing Material 3 components where possible
   - Custom components in `lib/widgets/`

2. **Color Tokens**:
   - Figma styles → `lib/theme/color_tokens.dart`
   - Use `Theme.of(context).colorScheme.primary`

3. **Typography**:
   - Figma text styles → `Theme.of(context).textTheme`
   - Custom styles in `lib/theme/text_theme.dart`

4. **Animations**:
   - Use Flutter's implicit animations (AnimatedOpacity, AnimatedContainer)
   - Complex animations → AnimationController

5. **Testing**:
   - Test on smallest device (iPhone SE, 375x667px)
   - Test accessibility (screen reader, keyboard)
   - Test dark mode (future)

### For Designers

1. **Keep Updating**:
   - Add new components as product evolves
   - Version control design files
   - Document changes in changelog

2. **Collaborate**:
   - Weekly design review with engineers
   - Validate implementations match designs
   - Iterate based on user feedback

3. **Measure**:
   - Track user interactions (heatmaps)
   - Monitor completion rates
   - A/B test design variations

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-12-30 | Initial UI specification for product intelligence features |

---

## Contact

Questions? Reach out to:
- Product: [product@savo.ai]
- Design: [design@savo.ai]
- Engineering: [eng@savo.ai]
