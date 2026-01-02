# Database Migration Quick Reference

## ✅ All Migrations Ready

| # | File | Status | What It Does |
|---|------|--------|--------------|
| 1 | 001_initial_schema.sql | ✅ | Base tables (users, profiles, family) |
| 2 | 002_vision_scanning_tables.sql | ✅ | Scanning & pantry tables |
| 3 | 002_user_profile_spec.sql | ✅ | Profile extensions & audit log |
| 4 | **003_add_quantities.sql** | ✅ **Idempotent** | **Quantity tracking (21 units, 50+ servings)** |
| 5 | **004_add_dinner_courses.sql** | ✅ **Idempotent** | **Multi-course meal planning** |

---

## 🚀 Run Migrations (Choose One)

### Option 1: Python Helper (Automated)
```bash
cd services/api/migrations
python run_migrations.py
```
✅ Runs all migrations in order  
✅ Shows detailed results  
✅ Verifies objects created

### Option 2: Supabase SQL Editor (Manual)
1. Go to Supabase Dashboard → SQL Editor
2. Paste each migration file (001 → 004)
3. Click "Run" for each
4. Verify success messages

### Option 3: Let Render Auto-Deploy
```bash
git push origin main
```
✅ Render will auto-run migrations on deploy

---

## 🔍 Verify Migrations

### Quick Check (PowerShell)
```powershell
.\services\api\verify_migrations.ps1
```

### Detailed Check (Python)
```bash
cd services/api/migrations
python db_helper.py
```

Shows:
- ✅ All tables exist
- ✅ All columns exist (skill_level, dinner_courses, quantity, unit)
- ✅ All functions exist (convert_unit, get_standard_serving, check_recipe_sufficiency)
- ✅ Table schemas

---

## 📊 What's New

### Migration 003: Quantity Tracking ⭐
- **Pantry with quantities:** 2 cups milk, 500g flour
- **21 units:** g, kg, lb, oz, ml, l, cup, tbsp, tsp, etc.
- **50+ standard servings:** Chicken breast = 170g, Apple = 1 piece
- **Unit conversion:** Convert cups to ml automatically
- **Recipe checker:** Do I have enough ingredients?

### Migration 004: Dinner Courses ⭐
- **Multi-course dinners:** 1-5 courses
- **Smart planning:** Generate appetizer + main + dessert
- **User preference:** Set in settings screen

---

## 🧪 Test After Migrations

```bash
# 1. Verify database
python services/api/migrations/db_helper.py

# 2. Test API
curl https://savo-api.onrender.com/api/v1/profile/household

# 3. Test Flutter
cd apps/mobile
flutter run --release
```

**In Flutter App:**
1. Go to Settings
2. Set Skill Level (1-5) → Save → Reload → Verify persists ✅
3. Set Dinner Courses (1-5) → Save → Reload → Verify persists ✅
4. Scan ingredient → Verify quantity detected ✅
5. Check pantry → Verify quantity shows (e.g., "2 cups") ✅

---

## 📁 File Locations

```
services/api/migrations/
├── 001_initial_schema.sql          ← Base schema
├── 002_vision_scanning_tables.sql  ← Scanning
├── 002_user_profile_spec.sql       ← Profiles
├── 003_add_quantities.sql          ← Quantities ⭐
├── 004_add_dinner_courses.sql      ← Courses ⭐
├── db_helper.py                    ← Verification tool
├── run_migrations.py               ← Auto-runner
├── README.md                       ← Full guide
└── MIGRATION_SUMMARY.md            ← Complete docs
```

---

## ⚡ Quick Commands

```bash
# Verify migrations
python services/api/migrations/db_helper.py

# Run all migrations
python services/api/migrations/run_migrations.py

# Deploy to Render
git push origin main

# Test API
curl https://savo-api.onrender.com/health

# Run Flutter
cd apps/mobile && flutter run --release
```

---

## 🆘 Troubleshooting

**Migration fails?**
→ Migrations 003 & 004 are idempotent - just re-run ✅

**Connection error?**
→ Check DATABASE_URL or SUPABASE credentials in .env

**Column already exists?**
→ Normal! Migrations check IF NOT EXISTS ✅

**Need help?**
→ See [MIGRATION_SUMMARY.md](MIGRATION_SUMMARY.md) for details

---

## 📈 Production Status

**95% Ready for Deployment** 🚀

✅ All migrations created  
✅ Migrations idempotent (safe to re-run)  
✅ Backend API updated  
✅ Flutter UI complete  
✅ All settings wired end-to-end  
✅ Helper scripts created  
✅ Documentation complete  

**Remaining:**
- Run migrations on Supabase
- Verify Render deployment
- Physical device testing

---

**Last Updated:** January 2, 2026  
**Ready to Deploy!** ✅
