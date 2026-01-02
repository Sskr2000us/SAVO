# 🚀 QUICK START - Physical Device Testing

## 📱 Run on Device (Choose One)

### Android
```bash
cd C:\Users\sskr2\SAVO\apps\mobile
flutter run --release
```

### iOS  
```bash
cd /path/to/SAVO/apps/mobile
flutter run --release
```

---

## ✅ Quick Test Sequence (30 minutes)

### Test 1: Scan Milk Carton (5 min)
```
Camera → Point at milk → Capture
✓ Detects "milk"
✓ Shows "1000 ml" quantity
✓ "Auto-detected" badge visible
✓ Confirm → Appears in pantry
```

### Test 2: Manual Add Tomatoes (2 min)
```
Green FAB → Type "tom" → Select "tomato"
✓ Auto-suggests "pieces" 
✓ Set to 3 → Add
✓ Time: Should be <10 seconds
```

### Test 3: Check Recipe (3 min)
```
Recipe → Change to 8 people → "Check if I have enough"
✓ Shows missing items
✓ Shopping list appears
✓ Copy button works
```

### Test 4: Edge Cases (10 min)
```
✓ Airplane mode → Clear error
✓ Blurry photo → Handles gracefully
✓ Empty photo → "No ingredients detected"
✓ Large file (>10MB) → Size error
```

---

## 🎯 Success Criteria

**MUST PASS:**
- [x] Image scanning works (>90% accuracy)
- [x] Quantity detected from labels
- [x] Manual entry < 10 seconds
- [x] No crashes
- [x] Errors are clear and helpful

**Confidence Score:** ___/5

---

## 📸 Required Screenshots

1. ✅ Successful scan (high confidence)
2. ✅ Quantity picker with "Auto-detected"
3. ✅ Manual entry autocomplete
4. ✅ Serving calculator results
5. ✅ Error message example

---

## 🐛 Report Issues

If something fails:
```
Bug #___: [What broke]
Device: Android/iOS
Steps: 1. 2. 3.
Expected: [What should happen]
Actual: [What happened]
```

---

## 📊 Performance Check

| Operation | Target | Actual |
|-----------|--------|--------|
| Scan image | <5s | ___ |
| Manual entry | <10s | ___ |
| Sufficiency check | <500ms | ___ |

---

## ✅ Ready for Beta?

**Decision Checklist:**
- [ ] All critical tests pass
- [ ] Performance acceptable
- [ ] User confidence high (4/5+)
- [ ] No P0 bugs
- [ ] Screenshots captured

**Beta Deployment:** ✅ GO / ❌ NO-GO

---

See [PHYSICAL_DEVICE_TESTING_GUIDE.md](PHYSICAL_DEVICE_TESTING_GUIDE.md) for detailed test cases.

**Testing Time:** 30-60 minutes | **Goal:** Rock-solid confidence 🎯
