/// Platform information utilities with web-safe implementation
/// 
/// Uses conditional imports to avoid dart:io on web platform
library platform_info;

import 'platform_info_stub.dart'
    if (dart.library.io) 'platform_info_io.dart'
    if (dart.library.html) 'platform_info_web.dart';

/// Get a human-readable name for the current platform
String getPlatformName() => getPlatformNameImpl();
