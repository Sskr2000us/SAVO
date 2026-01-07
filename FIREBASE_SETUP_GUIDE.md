# Firebase Cloud Messaging Setup Guide

## 📋 Overview
Configure Firebase Cloud Messaging (FCM) for push notifications in the SAVO mobile app.

## 🎯 Prerequisites
- Google Account
- Flutter mobile app (Android/iOS)
- Supabase project

## 📱 Step 1: Create Firebase Project

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Click "Add project"
3. Enter project name: `SAVO-Mobile`
4. Enable Google Analytics (optional)
5. Click "Create project"

## 📲 Step 2: Add Android App

1. In Firebase Console, click "Add app" → Android icon
2. Fill in app details:
   - **Android package name**: `com.savo.mobile` (from `android/app/build.gradle`)
   - **App nickname**: `SAVO Android`
   - **Debug signing certificate SHA-1**: (optional for now)
3. Click "Register app"
4. **Download `google-services.json`**
5. Place file in: `apps/mobile/android/app/google-services.json`

## 🍎 Step 3: Add iOS App

1. In Firebase Console, click "Add app" → iOS icon
2. Fill in app details:
   - **iOS bundle ID**: `com.savo.mobile` (from `ios/Runner/Info.plist`)
   - **App nickname**: `SAVO iOS`
   - **App Store ID**: (leave blank for now)
3. Click "Register app"
4. **Download `GoogleService-Info.plist`**
5. Place file in: `apps/mobile/ios/Runner/GoogleService-Info.plist`
6. Open Xcode and add file to Runner project

## 🔧 Step 4: Install Flutter Dependencies

Add to `pubspec.yaml`:
```yaml
dependencies:
  firebase_core: ^2.24.2
  firebase_messaging: ^14.7.9
  flutter_local_notifications: ^16.3.0
```

Run:
```bash
cd apps/mobile
flutter pub get
```

## 📝 Step 5: Configure Android

### 5.1 Update `android/build.gradle`
```gradle
buildscript {
    dependencies {
        classpath 'com.google.gms:google-services:4.4.0'
    }
}
```

### 5.2 Update `android/app/build.gradle`
Add at bottom:
```gradle
apply plugin: 'com.google.gms.google-services'
```

### 5.3 Update `AndroidManifest.xml`
Add inside `<application>`:
```xml
<meta-data
    android:name="com.google.firebase.messaging.default_notification_channel_id"
    android:value="savo_digests" />

<service
    android:name=".Application"
    android:exported="false">
    <intent-filter>
        <action android:name="com.google.firebase.MESSAGING_EVENT" />
    </intent-filter>
</service>
```

## 🍎 Step 6: Configure iOS

### 6.1 Enable Push Notifications
1. Open `ios/Runner.xcworkspace` in Xcode
2. Select Runner target
3. Go to "Signing & Capabilities"
4. Click "+" → Add "Push Notifications"
5. Click "+" → Add "Background Modes"
6. Check "Remote notifications"

### 6.2 Update `AppDelegate.swift`
```swift
import UIKit
import Flutter
import Firebase

@UIApplicationMain
@objc class AppDelegate: FlutterAppDelegate {
  override func application(
    _ application: UIApplication,
    didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?
  ) -> Bool {
    FirebaseApp.configure()
    
    if #available(iOS 10.0, *) {
      UNUserNotificationCenter.current().delegate = self as UNUserNotificationCenterDelegate
    }
    
    GeneratedPluginRegistrant.register(with: self)
    return super.application(application, didFinishLaunchingWithOptions: launchOptions)
  }
}
```

## 📱 Step 7: Create NotificationService

Create `apps/mobile/lib/services/notification_service.dart`:

```dart
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

class NotificationService {
  static final FlutterLocalNotificationsPlugin _localNotifications =
      FlutterLocalNotificationsPlugin();
  static final FirebaseMessaging _fcm = FirebaseMessaging.instance;

  /// Initialize Firebase and notification services
  static Future<void> initialize() async {
    await Firebase.initializeApp();

    // Request permissions (iOS)
    NotificationSettings settings = await _fcm.requestPermission(
      alert: true,
      badge: true,
      sound: true,
    );

    if (settings.authorizationStatus == AuthorizationStatus.authorized) {
      print('✅ User granted notification permission');
    }

    // Initialize local notifications
    const AndroidInitializationSettings androidSettings =
        AndroidInitializationSettings('@mipmap/ic_launcher');
    const DarwinInitializationSettings iosSettings =
        DarwinInitializationSettings();

    const InitializationSettings initSettings = InitializationSettings(
      android: androidSettings,
      iOS: iosSettings,
    );

    await _localNotifications.initialize(
      initSettings,
      onDidReceiveNotificationResponse: _onNotificationTapped,
    );

    // Create notification channel (Android)
    const AndroidNotificationChannel channel = AndroidNotificationChannel(
      'savo_digests',
      'Daily Digests',
      description: 'Morning and evening digest notifications',
      importance: Importance.high,
    );

    await _localNotifications
        .resolvePlatformSpecificImplementation<
            AndroidFlutterLocalNotificationsPlugin>()
        ?.createNotificationChannel(channel);

    // Get FCM token and save to Supabase
    await _saveFCMToken();

    // Listen to foreground messages
    FirebaseMessaging.onMessage.listen(_handleForegroundMessage);

    // Listen to background messages
    FirebaseMessaging.onBackgroundMessage(_handleBackgroundMessage);
  }

  /// Save FCM token to Supabase
  static Future<void> _saveFCMToken() async {
    final token = await _fcm.getToken();
    final userId = Supabase.instance.client.auth.currentUser?.id;

    if (token != null && userId != null) {
      await Supabase.instance.client.from('user_devices').upsert({
        'user_id': userId,
        'fcm_token': token,
        'platform': Platform.isAndroid ? 'android' : 'ios',
        'updated_at': DateTime.now().toIso8601String(),
      });
      print('✅ FCM token saved: ${token.substring(0, 20)}...');
    }
  }

  /// Handle foreground notifications
  static Future<void> _handleForegroundMessage(RemoteMessage message) async {
    print('📬 Foreground message: ${message.notification?.title}');

    await _localNotifications.show(
      message.hashCode,
      message.notification?.title,
      message.notification?.body,
      const NotificationDetails(
        android: AndroidNotificationDetails(
          'savo_digests',
          'Daily Digests',
          importance: Importance.high,
          priority: Priority.high,
        ),
        iOS: DarwinNotificationDetails(),
      ),
      payload: message.data.toString(),
    );
  }

  /// Handle background notifications
  static Future<void> _handleBackgroundMessage(RemoteMessage message) async {
    print('📬 Background message: ${message.notification?.title}');
  }

  /// Handle notification tap
  static void _onNotificationTapped(NotificationResponse response) {
    print('🔔 Notification tapped: ${response.payload}');
    // TODO: Navigate to digest screen
  }

  /// Schedule daily digest notifications (local fallback)
  static Future<void> scheduleDailyDigests() async {
    // Morning digest (8 AM)
    await _localNotifications.zonedSchedule(
      0,
      '🌅 Good Morning!',
      'Check your daily digest',
      _nextInstanceOf(8, 0),
      const NotificationDetails(
        android: AndroidNotificationDetails(
          'savo_digests',
          'Daily Digests',
          importance: Importance.high,
        ),
        iOS: DarwinNotificationDetails(),
      ),
      androidScheduleMode: AndroidScheduleMode.exactAllowWhileIdle,
      uiLocalNotificationDateInterpretation:
          UILocalNotificationDateInterpretation.absoluteTime,
      matchDateTimeComponents: DateTimeComponents.time,
    );

    // Evening digest (6 PM)
    await _localNotifications.zonedSchedule(
      1,
      '🌙 Evening Check-in',
      'How was your day?',
      _nextInstanceOf(18, 0),
      const NotificationDetails(
        android: AndroidNotificationDetails(
          'savo_digests',
          'Daily Digests',
          importance: Importance.high,
        ),
        iOS: DarwinNotificationDetails(),
      ),
      androidScheduleMode: AndroidScheduleMode.exactAllowWhileIdle,
      uiLocalNotificationDateInterpretation:
          UILocalNotificationDateInterpretation.absoluteTime,
      matchDateTimeComponents: DateTimeComponents.time,
    );

    print('✅ Daily digests scheduled');
  }

  /// Get next instance of time
  static TZDateTime _nextInstanceOf(int hour, int minute) {
    final now = TZDateTime.now(local);
    var scheduledDate = TZDateTime(local, now.year, now.month, now.day, hour, minute);
    if (scheduledDate.isBefore(now)) {
      scheduledDate = scheduledDate.add(const Duration(days: 1));
    }
    return scheduledDate;
  }
}
```

## 🚀 Step 8: Initialize in main.dart

Update `apps/mobile/lib/main.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'services/notification_service.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  
  // Initialize Supabase
  await Supabase.initialize(
    url: 'YOUR_SUPABASE_URL',
    anonKey: 'YOUR_SUPABASE_ANON_KEY',
  );
  
  // Initialize Firebase & Notifications
  await NotificationService.initialize();
  await NotificationService.scheduleDailyDigests();
  
  runApp(const MyApp());
}
```

## 🗄️ Step 9: Create Database Table

Run in Supabase SQL Editor:

```sql
CREATE TABLE user_devices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    fcm_token TEXT NOT NULL,
    platform TEXT NOT NULL CHECK (platform IN ('android', 'ios', 'web')),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, platform)
);

CREATE INDEX idx_user_devices_user ON user_devices(user_id);
CREATE INDEX idx_user_devices_token ON user_devices(fcm_token);

-- Enable RLS
ALTER TABLE user_devices ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can manage their own devices"
ON user_devices FOR ALL
TO authenticated
USING (user_id = auth.uid())
WITH CHECK (user_id = auth.uid());
```

## 📤 Step 10: Send Test Notification

### Via Firebase Console:
1. Go to Firebase Console → Cloud Messaging
2. Click "Send your first message"
3. Enter notification title and text
4. Select target app
5. Click "Send message"

### Via Backend (Python):
```python
import firebase_admin
from firebase_admin import credentials, messaging

# Initialize Firebase Admin SDK
cred = credentials.Certificate("path/to/serviceAccountKey.json")
firebase_admin.initialize_app(cred)

async def send_digest_notification(fcm_token: str, digest_type: str):
    message = messaging.Message(
        notification=messaging.Notification(
            title='🌅 Good Morning!' if digest_type == 'morning' else '🌙 Evening Check-in',
            body='Check your daily digest',
        ),
        data={
            'digest_type': digest_type,
            'action': 'open_digest',
        },
        token=fcm_token,
    )
    
    response = messaging.send(message)
    print(f'✅ Notification sent: {response}')
```

## ✅ Testing Checklist

- [ ] Firebase project created
- [ ] Android app added with `google-services.json`
- [ ] iOS app added with `GoogleService-Info.plist`
- [ ] Flutter dependencies installed
- [ ] Android configuration complete
- [ ] iOS configuration complete
- [ ] NotificationService created
- [ ] Notifications initialized in main.dart
- [ ] Database table created
- [ ] Test notification sent successfully
- [ ] Foreground notification works
- [ ] Background notification works
- [ ] Notification tap navigates correctly
- [ ] Daily digests scheduled

## 🔍 Troubleshooting

### Android:
- **Build error**: Check `google-services.json` is in correct location
- **No notifications**: Verify notification channel created
- **Background not working**: Check battery optimization settings

### iOS:
- **Build error**: Verify `GoogleService-Info.plist` added to Xcode project
- **No notifications**: Check Push Notifications capability enabled
- **Permission denied**: Request permission explicitly on app launch

## 📚 Next Steps

1. Integrate digest notifications with backend scheduler
2. Add notification preferences in settings
3. Implement notification action buttons
4. Track notification open rates
5. A/B test notification content

---

**Status**: Ready for implementation  
**Priority**: HIGH  
**Estimated Time**: 2-3 hours
