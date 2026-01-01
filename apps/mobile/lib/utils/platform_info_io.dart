/// Platform info implementation for native platforms (uses dart:io)
import 'dart:io';

String getPlatformNameImpl() {
  if (Platform.isAndroid) {
    return 'Android Device';
  } else if (Platform.isIOS) {
    return 'iOS Device';
  } else if (Platform.isMacOS) {
    return 'macOS';
  } else if (Platform.isWindows) {
    return 'Windows PC';
  } else if (Platform.isLinux) {
    return 'Linux';
  } else {
    return 'Unknown Device';
  }
}
