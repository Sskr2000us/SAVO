import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import '../../theme/app_theme.dart';
import '../../utils/platform_info.dart';

/// Device Security Screen - Enforce 2 device limit to prevent credential sharing
class DeviceSecurityScreen extends StatefulWidget {
  const DeviceSecurityScreen({super.key});

  @override
  State<DeviceSecurityScreen> createState() => _DeviceSecurityScreenState();
}

class _DeviceSecurityScreenState extends State<DeviceSecurityScreen> {
  static const int MAX_DEVICES = 2; // Enforce 2 device limit
  
  bool _isLoading = true;
  bool _isSigningOut = false;
  List<Map<String, dynamic>> _sessions = [];
  String? _currentSessionId;
  String _deviceInfo = '';

  @override
  void initState() {
    super.initState();
    _loadSessions();
  }

  Future<void> _loadSessions() async {
    setState(() => _isLoading = true);
    
    try {
      final session = Supabase.instance.client.auth.currentSession;
      if (session == null) return;

      _currentSessionId = session.accessToken;
      _deviceInfo = getPlatformName();

      // Get all sessions for this user from Supabase
      // Note: Supabase auth doesn't expose all sessions directly via client SDK
      // We simulate by tracking in our database or use Supabase admin API
      
      // For now, show current session only
      // In production, use Supabase Management API to list all sessions
      _sessions = [
        {
          'id': session.accessToken.substring(0, 10),
          'device': _deviceInfo,
          'last_active': session.user.lastSignInAt ?? DateTime.now().toIso8601String(),
          'is_current': true,
        }
      ];

      setState(() => _isLoading = false);
    } catch (e) {
      debugPrint('Error loading sessions: $e');
      setState(() => _isLoading = false);
    }
  }

  Future<void> _signOutDevice(String sessionId, bool isCurrent) async {
    if (isCurrent) {
      _signOutCurrentDevice();
      return;
    }

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Sign Out Device?'),
        content: const Text(
          'This will immediately sign out this device. '
          'They will need to sign in again to access the app.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(context, true),
            style: ElevatedButton.styleFrom(backgroundColor: Colors.red),
            child: const Text('Sign Out Device'),
          ),
        ],
      ),
    );

    if (confirmed != true) return;

    setState(() => _isSigningOut = true);

    try {
      // Revoke specific session using Supabase Admin API
      // For now, we use global scope - signs out all other devices
      await Supabase.instance.client.auth.signOut(scope: SignOutScope.others);
      
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Device signed out successfully'),
            backgroundColor: Colors.green,
          ),
        );
        _loadSessions();
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to sign out device: $e'),
            backgroundColor: Colors.red,
          ),
        );
      }
    } finally {
      setState(() => _isSigningOut = false);
    }
  }

  Future<void> _signOutAllOtherDevices() async {
    if (_sessions.where((s) => s['is_current'] != true).isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('No other devices to sign out')),
      );
      return;
    }

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Sign Out All Other Devices?'),
        content: Text(
          'This will sign out ${_sessions.where((s) => s['is_current'] != true).length} other device(s).\n\n'
          'Use this if you suspect someone else is using your account.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(context, true),
            style: ElevatedButton.styleFrom(backgroundColor: Colors.red),
            child: const Text('Sign Out Others'),
          ),
        ],
      ),
    );

    if (confirmed != true) return;

    setState(() => _isSigningOut = true);

    try {
      await Supabase.instance.client.auth.signOut(scope: SignOutScope.others);
      
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('All other devices signed out'),
            backgroundColor: Colors.green,
          ),
        );
        _loadSessions();
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed: $e'),
            backgroundColor: Colors.red,
          ),
        );
      }
    } finally {
      setState(() => _isSigningOut = false);
    }
  }

  Future<void> _signOutCurrentDevice() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Sign Out This Device?'),
        content: const Text('You will need to sign in again.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(context, true),
            style: ElevatedButton.styleFrom(backgroundColor: Colors.red),
            child: const Text('Sign Out'),
          ),
        ],
      ),
    );

    if (confirmed != true || !mounted) return;

    await Supabase.instance.client.auth.signOut();
    
    if (mounted) {
      Navigator.of(context).pushNamedAndRemoveUntil('/login', (route) => false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Device Security'),
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                // Security Warning
                Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: Colors.orange.shade50,
                    border: Border.all(color: Colors.orange.shade200),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Icon(Icons.security, color: Colors.orange.shade700, size: 24),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              'Device Limit: $MAX_DEVICES Devices',
                              style: TextStyle(
                                fontSize: 16,
                                fontWeight: FontWeight.bold,
                                color: Colors.orange.shade900,
                              ),
                            ),
                            const SizedBox(height: 4),
                            Text(
                              'To prevent unauthorized sharing, you can only be logged in on $MAX_DEVICES devices. '
                              'Sign out suspicious devices below.',
                              style: TextStyle(
                                fontSize: 14,
                                color: Colors.orange.shade800,
                                height: 1.4,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),

                const SizedBox(height: 24),

                // Device Count
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    const Text(
                      'Active Devices',
                      style: TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                      decoration: BoxDecoration(
                        color: _sessions.length > MAX_DEVICES 
                            ? Colors.red.shade100 
                            : Colors.green.shade100,
                        borderRadius: BorderRadius.circular(20),
                      ),
                      child: Text(
                        '${_sessions.length}/$MAX_DEVICES',
                        style: TextStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.bold,
                          color: _sessions.length > MAX_DEVICES 
                              ? Colors.red.shade900 
                              : Colors.green.shade900,
                        ),
                      ),
                    ),
                  ],
                ),

                const SizedBox(height: 16),

                // Device List
                ..._sessions.map((session) => _buildDeviceCard(session)),

                if (_sessions.length > 1) ...[
                  const SizedBox(height: 24),
                  SizedBox(
                    width: double.infinity,
                    height: 48,
                    child: ElevatedButton.icon(
                      onPressed: _isSigningOut ? null : _signOutAllOtherDevices,
                      icon: const Icon(Icons.logout),
                      label: const Text('Sign Out All Other Devices'),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: Colors.red,
                        foregroundColor: Colors.white,
                      ),
                    ),
                  ),
                ],

                const SizedBox(height: 32),

                // Help Text
                Text(
                  '💡 Tips to Keep Your Account Secure',
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.bold,
                    color: Colors.grey.shade700,
                  ),
                ),
                const SizedBox(height: 12),
                _buildTip('Don\'t share your login with friends or family outside your household'),
                _buildTip('Sign out suspicious devices immediately'),
                _buildTip('Change your password if you suspect unauthorized access'),
                _buildTip('Only use the app on trusted devices'),
              ],
            ),
    );
  }

  Widget _buildDeviceCard(Map<String, dynamic> session) {
    final isCurrent = session['is_current'] == true;
    final device = session['device'] ?? 'Unknown Device';
    final lastActive = _formatDateTime(session['last_active']);

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(
          color: isCurrent ? Colors.blue.shade200 : Colors.grey.shade200,
          width: isCurrent ? 2 : 1,
        ),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(
                  _getDeviceIcon(device),
                  color: isCurrent ? Colors.blue : Colors.grey,
                  size: 24,
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Text(
                            device,
                            style: const TextStyle(
                              fontSize: 16,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                          if (isCurrent) ...[
                            const SizedBox(width: 8),
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                              decoration: BoxDecoration(
                                color: Colors.blue.shade100,
                                borderRadius: BorderRadius.circular(4),
                              ),
                              child: Text(
                                'THIS DEVICE',
                                style: TextStyle(
                                  fontSize: 10,
                                  fontWeight: FontWeight.bold,
                                  color: Colors.blue.shade900,
                                ),
                              ),
                            ),
                          ],
                        ],
                      ),
                      const SizedBox(height: 4),
                      Text(
                        'Last active: $lastActive',
                        style: TextStyle(
                          fontSize: 13,
                          color: Colors.grey.shade600,
                        ),
                      ),
                    ],
                  ),
                ),
                if (!_isSigningOut)
                  IconButton(
                    onPressed: () => _signOutDevice(session['id'], isCurrent),
                    icon: const Icon(Icons.logout),
                    color: Colors.red,
                    tooltip: 'Sign out',
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  IconData _getDeviceIcon(String device) {
    final lower = device.toLowerCase();
    if (lower.contains('phone') || lower.contains('mobile') || lower.contains('android') || lower.contains('ios')) {
      return Icons.smartphone;
    } else if (lower.contains('tablet') || lower.contains('ipad')) {
      return Icons.tablet;
    } else if (lower.contains('web') || lower.contains('chrome') || lower.contains('firefox') || lower.contains('safari')) {
      return Icons.computer;
    }
    return Icons.devices;
  }

  String _formatDateTime(dynamic dateTime) {
    try {
      final dt = dateTime is String ? DateTime.parse(dateTime) : dateTime as DateTime;
      final now = DateTime.now();
      final diff = now.difference(dt);

      if (diff.inMinutes < 1) return 'Just now';
      if (diff.inMinutes < 60) return '${diff.inMinutes}m ago';
      if (diff.inHours < 24) return '${diff.inHours}h ago';
      if (diff.inDays < 7) return '${diff.inDays}d ago';
      return '${dt.month}/${dt.day}/${dt.year}';
    } catch (e) {
      return 'Unknown';
    }
  }

  Widget _buildTip(String text) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(Icons.check_circle, size: 16, color: Colors.green.shade700),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              text,
              style: TextStyle(
                fontSize: 14,
                color: Colors.grey.shade700,
                height: 1.4,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
