# Vision Scanning - Quick Deployment Guide

## Prerequisites
- Supabase project with database access
- OpenAI API key with GPT-4 Vision access
- Flutter development environment
- Backend deployed (Render/similar)

---

## Step 1: Database Migration (5 minutes)

```bash
# Connect to Supabase SQL editor and run:
services/api/migrations/002_vision_scanning_tables.sql
```

**Verify:**
```sql
SELECT COUNT(*) FROM information_schema.tables 
WHERE table_name IN ('ingredient_scans', 'detected_ingredients', 'user_pantry', 'scan_feedback', 'scan_corrections');
-- Should return 5
```

---

## Step 2: Backend Configuration (5 minutes)

### Environment Variables
Add to your backend `.env`:
```bash
OPENAI_API_KEY=sk-...your-key...
```

### Install Python Dependencies
```bash
cd services/api
pip install openai pillow
```

### Verify Routes Registered
Check `services/api/app/api/router.py` - should include:
```python
from app.api.routes.scanning import router as scanning_router
api_router.include_router(scanning_router, tags=["scanning"])
```
✅ Already done in implementation

### Test Backend Locally
```bash
cd services/api
uvicorn app.main:app --reload

# Visit http://localhost:8000/docs
# Look for /api/scanning/* endpoints
```

---

## Step 3: Flutter Dependencies (10 minutes)

### Update `pubspec.yaml`
```yaml
dependencies:
  camera: ^0.10.5
  image_picker: ^1.0.4
  http_parser: ^4.0.2
  # ... existing dependencies
```

### Install
```bash
cd apps/mobile
flutter pub get
```

---

## Step 4: Mobile Permissions (5 minutes)

### Android: `android/app/src/main/AndroidManifest.xml`
Add before `<application>`:
```xml
<uses-permission android:name="android.permission.CAMERA" />
<uses-permission android:name="android.permission.WRITE_EXTERNAL_STORAGE" />
<uses-permission android:name="android.permission.READ_EXTERNAL_STORAGE" />
```

### iOS: `ios/Runner/Info.plist`
Add:
```xml
<key>NSCameraUsageDescription</key>
<string>SAVO needs camera access to scan your pantry and detect ingredients.</string>
<key>NSPhotoLibraryUsageDescription</key>
<string>SAVO needs photo library access to select pantry images.</string>
```

---

## Step 5: Add Navigation (10 minutes)

In your main Flutter app, add navigation to scanning:

```dart
import 'screens/scanning/camera_capture_screen.dart';

// In your home screen or navigation menu:
ElevatedButton(
  onPressed: () {
    Navigator.push(
      context,
      MaterialPageRoute(builder: (context) => CameraCaptureScreen()),
    );
  },
  child: Text('Scan Pantry'),
)
```

---

## Step 6: Test End-to-End (15 minutes)

### Test 1: Basic Scanning
1. Open app on physical device (camera needed)
2. Navigate to "Scan Pantry"
3. Capture photo of 3-5 visible ingredients
4. Verify analysis completes (~3-4 seconds)
5. Verify ingredients detected with confidence scores

### Test 2: Confirmation Flow
1. Review high-confidence items (should be auto-selected)
2. Review medium-confidence items (should show alternatives)
3. Tap "Confirm" button
4. Verify success message
5. Check pantry inventory updated

### Test 3: Allergen Warning
1. Set up test user with dairy allergen
2. Scan image with milk/cheese
3. Verify red allergen warning appears
4. Confirm ingredient (allowed)
5. Verify warning was shown

### Test 4: Close Alternatives
1. Scan image with partially obscured green vegetable
2. Verify medium confidence detection
3. Verify alternative chips appear (spinach, kale, lettuce, etc.)
4. Tap alternative chip
5. Verify ingredient modified correctly

---

## Step 7: Monitor Performance (Ongoing)

### Run Weekly Optimization Report
```bash
cd services/api
python analyze_scanning_performance.py --days 7 --export weekly_report.json
```

### Check Metrics Dashboard
Query Supabase:
```sql
SELECT * FROM scanning_metrics 
ORDER BY scan_date DESC 
LIMIT 7;
```

### Monitor API Costs
```sql
SELECT 
  DATE(created_at) as day,
  COUNT(*) as scans,
  SUM(api_cost_cents) / 100.0 as cost_dollars
FROM ingredient_scans
WHERE created_at >= NOW() - INTERVAL '30 days'
GROUP BY DATE(created_at)
ORDER BY day DESC;
```

---

## Troubleshooting

### Camera Not Working
- **Android**: Check `AndroidManifest.xml` permissions
- **iOS**: Check `Info.plist` usage descriptions
- **Both**: Test on physical device (emulator cameras limited)

### Analysis Fails
- Check `OPENAI_API_KEY` is set correctly
- Verify OpenAI account has GPT-4 Vision access
- Check backend logs for Vision API errors
- Verify image size < 10MB

### No Ingredients Detected
- Ensure good lighting in photo
- Avoid blurry images
- Make sure ingredients visible (not obscured)
- Try closer photo with fewer items

### Allergen Warnings Not Showing
- Verify user has allergens declared in profile
- Check allergen keywords in `vision_api.py`
- Verify detection uses canonical names

### Slow Performance
- Check network latency to backend
- Monitor OpenAI API response times
- Optimize image size before upload (already handled)
- Consider caching for repeated scans

---

## Production Checklist

- [ ] Database migration run successfully
- [ ] Backend deployed with OPENAI_API_KEY
- [ ] Flutter dependencies installed
- [ ] Camera permissions added to both platforms
- [ ] Navigation to scanning screen added
- [ ] Tested on physical device (iOS + Android)
- [ ] Allergen warnings verified
- [ ] Pantry updates working
- [ ] Feedback submission working
- [ ] Monitoring dashboard set up
- [ ] Weekly optimization report scheduled

---

## API Endpoints Reference

### Scan Image
```bash
POST /api/scanning/analyze-image
Content-Type: multipart/form-data
Authorization: Bearer {token}

Fields:
- image: file (JPEG/PNG)
- scan_type: pantry|fridge|counter|shopping
- location_hint: string (optional)
```

### Confirm Ingredients
```bash
POST /api/scanning/confirm-ingredients
Content-Type: application/json
Authorization: Bearer {token}

{
  "scan_id": "uuid",
  "confirmations": [
    {"detected_id": "uuid", "action": "confirmed"},
    {"detected_id": "uuid", "action": "modified", "confirmed_name": "kale"},
    {"detected_id": "uuid", "action": "rejected"}
  ]
}
```

### Get Pantry
```bash
GET /api/scanning/pantry
Authorization: Bearer {token}
```

### Get History
```bash
GET /api/scanning/history?limit=20&offset=0
Authorization: Bearer {token}
```

### Submit Feedback
```bash
POST /api/scanning/feedback
Content-Type: application/json
Authorization: Bearer {token}

{
  "scan_id": "uuid",
  "feedback_type": "correction",
  "detected_name": "lettuce",
  "correct_name": "kale",
  "accuracy_rating": 4
}
```

---

## Support & Maintenance

### Common Issues

**Issue**: "Not authenticated" errors  
**Fix**: Ensure Bearer token is being sent correctly from Flutter app

**Issue**: Vision API quota exceeded  
**Fix**: Monitor usage, consider caching, or upgrade OpenAI plan

**Issue**: Low accuracy for specific items  
**Fix**: Run optimization report, add corrections to prompt examples

**Issue**: Users confused by confirmation flow  
**Fix**: Add onboarding tutorial or help tooltips

### Performance Optimization

1. **Image Compression**: Already handled (Pillow in backend)
2. **Caching**: Consider caching scan results for 5 minutes
3. **Batch Processing**: Future: Allow multiple images in one scan
4. **Edge Cases**: Continually update normalization rules from corrections

---

## Success Metrics to Track

### Daily/Weekly
- Total scans
- Average detections per scan
- Accuracy rate (confirmed / total)
- User engagement (unique users scanning)

### Monthly
- Accuracy trends over time
- Most commonly detected ingredients
- Most common corrections (for prompt improvement)
- User satisfaction ratings

### Quarterly
- API cost trends
- Feature adoption rate
- Impact on recipe generation usage
- User retention after first scan

---

## Complete! 🎉

Your vision scanning system is ready for production. Users can now:
1. Scan their pantry/fridge with phone camera
2. Review detected ingredients with confidence scores
3. Confirm or modify detections
4. See allergen warnings
5. Have confirmed ingredients automatically added to pantry
6. Generate recipes using their actual inventory

**End-to-end flow is complete with zero gaps!**
