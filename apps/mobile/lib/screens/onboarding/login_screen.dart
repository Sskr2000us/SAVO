import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../models/profile_state.dart';
import '../../services/auth_service.dart';
import '../../services/profile_service.dart';
import '../../services/api_client.dart';
import '../../services/onboarding_storage.dart';
import 'onboarding_coordinator.dart';
import 'signup_screen.dart';

class OnboardingLoginScreen extends StatefulWidget {
  const OnboardingLoginScreen({super.key});

  @override
  State<OnboardingLoginScreen> createState() => _OnboardingLoginScreenState();
}

class _OnboardingLoginScreenState extends State<OnboardingLoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();
  final _otpController = TextEditingController();
  
  bool _isLoading = false;
  bool _isOtpMode = false;
  bool _otpSent = false;
  String? _error;

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    _otpController.dispose();
    super.dispose();
  }

  Future<void> _handleEmailPasswordLogin() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() {
      _isLoading = true;
      _error = null;
    });

    final authService = Provider.of<AuthService>(context, listen: false);
    final apiClient = Provider.of<ApiClient>(context, listen: false);
    final profileService = ProfileService(apiClient);
    final profileState = Provider.of<ProfileState>(context, listen: false);

    try {
      // Sign in
      final response = await authService.signInWithPassword(
        email: _emailController.text.trim(),
        password: _passwordController.text,
      );

      // Check if email is confirmed
      if (response.user != null && response.user!.emailConfirmedAt == null) {
        setState(() {
          _error = 'Please confirm your email first. Check your inbox for the confirmation link.';
          _isLoading = false;
        });
        await authService.signOut();
        return;
      }

      // Verify we have a valid session
      if (!authService.isAuthenticated) {
        setState(() {
          _error = 'Failed to create session. Please try again.';
          _isLoading = false;
        });
        return;
      }

      // Get onboarding status (returns resume step for existing/new users)
      final status = await profileService.getOnboardingStatus();
      profileState.updateOnboardingStatus(status);
      
      // Fetch full profile only if onboarding is complete
      if (status['completed'] == true) {
        try {
          final profile = await profileService.getFullProfile();
          profileState.updateProfileData(profile);
        } catch (e) {
          debugPrint('Could not load profile: $e');
        }
      }

      // Save progress locally for offline resume
      final userId = profileState.userId;
      if (userId != null) {
        await OnboardingStorage.saveLastStep('LOGIN', userId);
      }

      if (mounted) {
        // Navigate to onboarding flow (will show appropriate step)
        Navigator.of(context).pushReplacementNamed('/onboarding');
      }
    } catch (e) {
      setState(() {
        _error = 'Login failed: ${e.toString()}';
        _isLoading = false;
      });
    }
  }

  Future<void> _handleOtpRequest() async {
    if (_emailController.text.trim().isEmpty) {
      setState(() => _error = 'Please enter your email');
      return;
    }

    setState(() {
      _isLoading = true;
      _error = null;
    });

    final authService = Provider.of<AuthService>(context, listen: false);

    try {
      await authService.signInWithOtp(email: _emailController.text.trim());
      setState(() {
        _otpSent = true;
        _isLoading = false;
      });
    } catch (e) {
      setState(() {
        _error = 'Failed to send OTP: ${e.toString()}';
        _isLoading = false;
      });
    }
  }

  Future<void> _handleOtpVerify() async {
    if (_otpController.text.trim().isEmpty) {
      setState(() => _error = 'Please enter the OTP code');
      return;
    }

    setState(() {
      _isLoading = true;
      _error = null;
    });

    final authService = Provider.of<AuthService>(context, listen: false);
    final apiClient = Provider.of<ApiClient>(context, listen: false);
    final profileService = ProfileService(apiClient);
    final profileState = Provider.of<ProfileState>(context, listen: false);

    try {
      // Verify OTP
      await authService.verifyOtp(
        email: _emailController.text.trim(),
        token: _otpController.text.trim(),
      );

      // Get onboarding status (returns resume step for existing/new users)
      final status = await profileService.getOnboardingStatus();
      profileState.updateOnboardingStatus(status);
      
      // Fetch full profile only if onboarding is complete
      if (status['completed'] == true) {
        try {
          final profile = await profileService.getFullProfile();
          profileState.updateProfileData(profile);
        } catch (e) {
          debugPrint('Could not load profile: $e');
        }
      }

      // Save progress locally for offline resume
      final userId = profileState.userId;
      if (userId != null) {
        await OnboardingStorage.saveLastStep('LOGIN', userId);
      }

      if (mounted) {
        // Navigate to onboarding flow (will show appropriate step)
        Navigator.of(context).pushReplacementNamed('/onboarding');
      }
    } catch (e) {
      setState(() {
        _error = 'OTP verification failed: ${e.toString()}';
        _isLoading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24.0),
          child: Form(
            key: _formKey,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const SizedBox(height: 60),
                // Logo or app name
                const Text(
                  'SAVO',
                  style: TextStyle(
                    fontSize: 48,
                    fontWeight: FontWeight.bold,
                  ),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 8),
                const Text(
                  'Your AI Cooking Assistant',
                  style: TextStyle(fontSize: 16, color: Colors.grey),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 60),
                
                // Email field
                TextFormField(
                  controller: _emailController,
                  decoration: const InputDecoration(
                    labelText: 'Email',
                    border: OutlineInputBorder(),
                    prefixIcon: Icon(Icons.email),
                  ),
                  keyboardType: TextInputType.emailAddress,
                  validator: (value) {
                    if (value == null || value.isEmpty) {
                      return 'Please enter your email';
                    }
                    if (!value.contains('@')) {
                      return 'Please enter a valid email';
                    }
                    return null;
                  },
                ),
                const SizedBox(height: 16),
                
                if (!_isOtpMode && !_otpSent) ...[
                  // Password field (email/password mode)
                  TextFormField(
                    controller: _passwordController,
                    decoration: const InputDecoration(
                      labelText: 'Password',
                      border: OutlineInputBorder(),
                      prefixIcon: Icon(Icons.lock),
                    ),
                    obscureText: true,
                    validator: (value) {
                      if (value == null || value.isEmpty) {
                        return 'Please enter your password';
                      }
                      return null;
                    },
                  ),
                  const SizedBox(height: 24),
                  
                  // Login button
                  ElevatedButton(
                    onPressed: _isLoading ? null : _handleEmailPasswordLogin,
                    style: ElevatedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(vertical: 16),
                    ),
                    child: _isLoading
                        ? const CircularProgressIndicator()
                        : const Text('Sign In'),
                  ),
                  const SizedBox(height: 16),
                  
                  // Switch to OTP
                  TextButton(
                    onPressed: () => setState(() => _isOtpMode = true),
                    child: const Text('Sign in with magic link instead'),
                  ),
                ],
                
                if (_isOtpMode && !_otpSent) ...[
                  // OTP request button
                  const SizedBox(height: 8),
                  ElevatedButton(
                    onPressed: _isLoading ? null : _handleOtpRequest,
                    style: ElevatedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(vertical: 16),
                    ),
                    child: _isLoading
                        ? const CircularProgressIndicator()
                        : const Text('Send Magic Link'),
                  ),
                  const SizedBox(height: 16),
                  
                  // Switch back to password
                  TextButton(
                    onPressed: () => setState(() => _isOtpMode = false),
                    child: const Text('Sign in with password instead'),
                  ),
                ],
                
                // Signup link
                const SizedBox(height: 24),
                Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    const Text('Don\'t have an account? '),
                    TextButton(
                      onPressed: () {
                        Navigator.push(
                          context,
                          MaterialPageRoute(
                            builder: (context) => const OnboardingSignupScreen(),
                          ),
                        );
                      },
                      child: const Text('Sign Up'),
                    ),
                  ],
                ),
                
                if (_otpSent) ...[
                  // OTP code field
                  const Text(
                    'Check your email for the verification code',
                    textAlign: TextAlign.center,
                    style: TextStyle(color: Colors.grey),
                  ),
                  const SizedBox(height: 16),
                  TextFormField(
                    controller: _otpController,
                    decoration: const InputDecoration(
                      labelText: 'Verification Code',
                      border: OutlineInputBorder(),
                      prefixIcon: Icon(Icons.pin),
                    ),
                    keyboardType: TextInputType.number,
                  ),
                  const SizedBox(height: 24),
                  
                  // Verify button
                  ElevatedButton(
                    onPressed: _isLoading ? null : _handleOtpVerify,
                    style: ElevatedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(vertical: 16),
                    ),
                    child: _isLoading
                        ? const CircularProgressIndicator()
                        : const Text('Verify Code'),
                  ),
                  const SizedBox(height: 16),
                  
                  // Resend OTP
                  TextButton(
                    onPressed: _isLoading ? null : _handleOtpRequest,
                    child: const Text('Resend Code'),
                  ),
                ],
                
                // Error message
                if (_error != null) ...[
                  const SizedBox(height: 16),
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: Colors.red.withOpacity(0.1),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Text(
                      _error!,
                      style: const TextStyle(color: Colors.red),
                      textAlign: TextAlign.center,
                    ),
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}
