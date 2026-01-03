import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import '../../theme/app_theme.dart';
import '../../widgets/savo_widgets.dart';
import '../../utils/platform_info.dart';

/// Screen for managing active sessions across multiple devices
/// 
/// Features:
/// - Shows current session metadata (device, last login)
/// - "Sign out all other devices" button using Supabase sign out scope
/// - Helps users manage multi-device access for security
class ActiveSessionsScreen extends StatefulWidget {
  const ActiveSessionsScreen({super.key});

  @override
  State<ActiveSessionsScreen> createState() => _ActiveSessionsScreenState();
}

class _ActiveSessionsScreenState extends State<ActiveSessionsScreen> {
  bool _isSigningOut = false;
  Session? _currentSession;
  String _deviceInfo = 'Unknown Device';
  DateTime? _lastLogin;

  @override
  void initState() {
    super.initState();
    _loadSessionInfo();
  }

  /// Load current session information from Supabase
  Future<void> _loadSessionInfo() async {
    try {
      final session = Supabase.instance.client.auth.currentSession;
      if (session != null) {
        setState(() {
          _currentSession = session;
          _lastLogin = session.user.lastSignInAt != null
              ? DateTime.parse(session.user.lastSignInAt!)
              : null;
          _deviceInfo = _getDeviceInfo();
        });
      }
    } catch (e) {
      debugPrint('Error loading session info: $e');
    }
  }

  /// Get device information for display
  String _getDeviceInfo() {
    return getPlatformName();
  }

  /// Format date/time for display
  String _formatDateTime(DateTime? dateTime) {
    if (dateTime == null) return 'Unknown';
    
    final now = DateTime.now();
    final difference = now.difference(dateTime);
    
    if (difference.inMinutes < 1) {
      return 'Just now';
    } else if (difference.inMinutes < 60) {
      return '${difference.inMinutes} minute${difference.inMinutes == 1 ? '' : 's'} ago';
    } else if (difference.inHours < 24) {
      return '${difference.inHours} hour${difference.inHours == 1 ? '' : 's'} ago';
    } else if (difference.inDays < 7) {
      return '${difference.inDays} day${difference.inDays == 1 ? '' : 's'} ago';
    } else {
      return '${dateTime.month}/${dateTime.day}/${dateTime.year}';
    }
  }

  /// Sign out all other devices while keeping current session
  Future<void> _signOutOtherDevices() async {
    // Show confirmation dialog
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Sign Out Other Devices?'),
        content: const Text(
          'This will sign you out of all other devices and browsers where you\'re logged in. '
          'Your current session will remain active.\n\n'
          'Those devices will need to sign in again to access your account.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(context, true),
            style: ElevatedButton.styleFrom(
              backgroundColor: AppColors.danger,
            ),
            child: const Text('Sign Out Others'),
          ),
        ],
      ),
    );

    if (confirmed != true || !mounted) return;

    setState(() => _isSigningOut = true);

    try {
      // Sign out all sessions except the current one
      // Using Supabase's SignOutScope.otherSessions
      await Supabase.instance.client.auth.signOut(
        scope: SignOutScope.others,
      );

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Successfully signed out all other devices'),
            backgroundColor: AppColors.success,
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to sign out other devices: $e'),
            backgroundColor: AppColors.danger,
          ),
        );
      }
    } finally {
      if (mounted) {
        setState(() => _isSigningOut = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Active Devices'),
        backgroundColor: AppColors.surface,
      ),
      body: ListView(
        padding: const EdgeInsets.all(AppSpacing.md),
        children: [
          // Security info header
          SavoCard(
            child: Padding(
              padding: const EdgeInsets.all(AppSpacing.md),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Icon(
                        Icons.security,
                        color: Colors.orange.shade700,
                        size: 24,
                      ),
                      const SizedBox(width: AppSpacing.md),
                      Expanded(
                        child: Text(
                          'Security Check',
                          style: AppTypography.h2Style().copyWith(
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: AppSpacing.sm),
                  Text(
                    'Review devices accessing your household account. '
                    'If you see an unknown device, sign it out immediately.',
                    style: AppTypography.captionStyle(),
                  ),
                  const SizedBox(height: AppSpacing.sm),
                  Container(
                    padding: const EdgeInsets.all(AppSpacing.sm),
                    decoration: BoxDecoration(
                      color: Colors.blue.shade50,
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: Colors.blue.shade200),
                    ),
                    child: Row(
                      children: [
                        Icon(Icons.info, size: 16, color: Colors.blue.shade700),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            'Max 5 devices per household',
                            style: TextStyle(
                              fontSize: 12,
                              color: Colors.blue.shade700,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: AppSpacing.lg),

          // Current session section
          Text(
            'This Device',
            style: AppTypography.h2Style(),
          ),
          const SizedBox(height: AppSpacing.sm),
          
          SavoCard(
            child: ListTile(
              leading: Container(
                padding: const EdgeInsets.all(AppSpacing.sm),
                decoration: BoxDecoration(
                  color: Colors.green.withOpacity(0.2),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Icon(
                  Icons.smartphone,
                  color: Colors.green.shade700,
                ),
              ),
              title: Row(
                children: [
                  Text(
                    _deviceInfo,
                    style: AppTypography.bodyStyle(),
                  ),
                  const SizedBox(width: AppSpacing.xs),
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: AppSpacing.xs,
                      vertical: 2,
                    ),
                    decoration: BoxDecoration(
                      color: AppColors.success.withOpacity(0.2),
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: Text(
                      'ACTIVE',
                      style: AppTypography.captionStyle().copyWith(
                        color: AppColors.success,
                        fontSize: 10,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                ],
              ),
              subtitle: Padding(
                padding: const EdgeInsets.only(top: AppSpacing.xs),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Last login: ${_formatDateTime(_lastLogin)}',
                      style: AppTypography.captionStyle(),
                    ),
                    if (_currentSession?.user.email != null) ...[
                      const SizedBox(height: 4),
                      Text(
                        _currentSession!.user.email!,
                        style: AppTypography.captionStyle().copyWith(
                          color: AppColors.primary,
                        ),
                      ),
                    ],
                  ],
                ),
              ),
              isThreeLine: true,
            ),
          ),

          const SizedBox(height: AppSpacing.xl),

          // Sign out other devices section
          Text(
            'Security Actions',
            style: AppTypography.h2Style(),
          ),
          const SizedBox(height: AppSpacing.sm),
          
          SavoCard(
            child: Column(
              children: [
                ListTile(
                  leading: const Icon(
                    Icons.devices_other,
                    color: AppColors.textSecondary,
                  ),
                  title: Text(
                    'Other Devices',
                    style: AppTypography.bodyStyle(),
                  ),
                  subtitle: Padding(
                    padding: const EdgeInsets.only(top: AppSpacing.xs),
                    child: Text(
                      'Sign out of all other devices and browsers where you\'re logged in',
                      style: AppTypography.captionStyle(),
                    ),
                  ),
                  isThreeLine: true,
                ),
                const Divider(height: 1),
                Padding(
                  padding: const EdgeInsets.all(AppSpacing.md),
                  child: SizedBox(
                    width: double.infinity,
                    child: ElevatedButton.icon(
                      onPressed: _isSigningOut ? null : _signOutOtherDevices,
                      icon: _isSigningOut
                          ? const SizedBox(
                              width: 16,
                              height: 16,
                              child: CircularProgressIndicator(
                                strokeWidth: 2,
                                valueColor: AlwaysStoppedAnimation<Color>(
                                  Colors.white,
                                ),
                              ),
                            )
                          : const Icon(Icons.logout),
                      label: Text(_isSigningOut
                          ? 'Signing Out...'
                          : 'Sign Out All Other Devices'),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppColors.danger,
                        padding: const EdgeInsets.symmetric(
                          vertical: AppSpacing.md,
                        ),
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),

          const SizedBox(height: AppSpacing.lg),

          // Additional info
          SavoCard(
            child: Padding(
              padding: const EdgeInsets.all(AppSpacing.md),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      const Icon(
                        Icons.security,
                        color: AppColors.textSecondary,
                        size: 20,
                      ),
                      const SizedBox(width: AppSpacing.sm),
                      Text(
                        'Security Tips',
                        style: AppTypography.bodyStyle().copyWith(
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: AppSpacing.sm),
                  _buildSecurityTip(
                    '• Sign out other devices if you see suspicious activity',
                  ),
                  _buildSecurityTip(
                    '• Your session will automatically refresh when you use the app',
                  ),
                  _buildSecurityTip(
                    '• Use a strong password and enable two-factor authentication',
                  ),
                  _buildSecurityTip(
                    '• Regularly review your active sessions for security',
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSecurityTip(String text) {
    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.xs),
      child: Text(
        text,
        style: AppTypography.captionStyle(),
      ),
    );
  }
}
