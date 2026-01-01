import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'screens/home_screen.dart';
import 'screens/plan_screen.dart';
import 'screens/cook_screen.dart';
import 'screens/leftovers_screen.dart';
import 'screens/settings_screen.dart';
import 'screens/onboarding/onboarding_coordinator.dart';
import 'services/api_client.dart';
import 'services/auth_service.dart';
import 'services/profile_service.dart';
import 'services/onboarding_storage.dart';
import 'models/profile_state.dart';
import 'theme/app_theme.dart';
import 'config/app_config.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  
  // Initialize Supabase with session persistence
  await Supabase.initialize(
    url: Config.supabaseUrl,
    anonKey: Config.supabaseAnonKey,
    authOptions: const FlutterAuthClientOptions(
      authFlowType: AuthFlowType.pkce,
      autoRefreshToken: true,
      persistSession: true,
    ),
  );
  
  runApp(const SavoApp());
}

class SavoApp extends StatefulWidget {
  const SavoApp({super.key});

  @override
  State<SavoApp> createState() => _SavoAppState();
}

class _SavoAppState extends State<SavoApp> with WidgetsBindingObserver {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      // Refresh session when app resumes
      _refreshSession();
    }
  }

  Future<void> _refreshSession() async {
    try {
      final session = Supabase.instance.client.auth.currentSession;
      if (session != null) {
        await Supabase.instance.client.auth.refreshSession();
      }
    } catch (e) {
      // Session refresh failed - user needs to re-authenticate
      debugPrint('Session refresh failed: $e');
      // In production, navigate to login screen
    }
  }

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        Provider(create: (_) => ApiClient()),
        Provider(create: (_) => AuthService()),
        ChangeNotifierProvider(create: (_) => ProfileState()),
      ],
      child: MaterialApp(
        title: 'SAVO',
        theme: AppTheme.darkTheme,
        home: const AppStartupScreen(),
        routes: {
          '/onboarding': (context) => const OnboardingCoordinator(),
          '/home': (context) => const MainNavigationShell(),
        },
      ),
    );
  }
}

class MainNavigationShell extends StatefulWidget {
  const MainNavigationShell({super.key});

  @override
  State<MainNavigationShell> createState() => _MainNavigationShellState();
}

class _MainNavigationShellState extends State<MainNavigationShell> {
  int _selectedIndex = 0;

  static const List<Widget> _screens = [
    HomeScreen(),
    PlanScreen(),
    CookScreen(),
    LeftoversScreen(),
    SettingsScreen(),
  ];

  void _onItemTapped(int index) {
    setState(() {
      _selectedIndex = index;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: _screens[_selectedIndex],
      bottomNavigationBar: NavigationBar(
        selectedIndex: _selectedIndex,
        onDestinationSelected: _onItemTapped,
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.home_outlined),
            selectedIcon: Icon(Icons.home),
            label: 'Home',
          ),
          NavigationDestination(
            icon: Icon(Icons.restaurant_menu_outlined),
            selectedIcon: Icon(Icons.restaurant_menu),
            label: 'Plan',
          ),
          NavigationDestination(
            icon: Icon(Icons.timer_outlined),
            selectedIcon: Icon(Icons.timer),
            label: 'Cook',
          ),
          NavigationDestination(
            icon: Icon(Icons.kitchen_outlined),
            selectedIcon: Icon(Icons.kitchen),
            label: 'Leftovers',
          ),
          NavigationDestination(
            icon: Icon(Icons.settings_outlined),
            selectedIcon: Icon(Icons.settings),
            label: 'Settings',
          ),
        ],
      ),
    );
  }
}

// Legacy health check code removed - replaced with proper navigation

/// App startup screen that checks auth and onboarding status
class AppStartupScreen extends StatefulWidget {
  const AppStartupScreen({super.key});

  @override
  State<AppStartupScreen> createState() => _AppStartupScreenState();
}

class _AppStartupScreenState extends State<AppStartupScreen> {
  @override
  void initState() {
    super.initState();
    _checkAuthAndOnboarding();
  }

  Future<void> _checkAuthAndOnboarding() async {
    try {
      final session = Supabase.instance.client.auth.currentSession;
      
      // No session -> start onboarding (which starts at LOGIN)
      if (session == null) {
        if (mounted) {
          Navigator.of(context).pushReplacementNamed('/onboarding');
        }
        return;
      }

      // Has session -> check onboarding status from server
      final apiClient = Provider.of<ApiClient>(context, listen: false);
      final profileService = ProfileService(apiClient);
      final profileState = Provider.of<ProfileState>(context, listen: false);
      final userId = session.user.id;

      try {
        final status = await profileService.getOnboardingStatus();
        profileState.updateOnboardingStatus(status);

        // Load profile data if exists
        try {
          final profile = await profileService.getFullProfile();
          profileState.updateProfileData(profile);
        } catch (e) {
          debugPrint('No profile yet: $e');
        }

        if (mounted) {
          if (status['completed'] == true) {
            // Onboarding complete -> go to home
            Navigator.of(context).pushReplacementNamed('/home');
          } else {
            // Onboarding incomplete -> resume onboarding
            Navigator.of(context).pushReplacementNamed('/onboarding');
          }
        }
      } catch (serverError) {
        debugPrint('Error checking server onboarding status: $serverError');
        
        // Fallback to local storage (offline mode)
        try {
          final isComplete = await OnboardingStorage.isOnboardingComplete(userId);
          
          if (mounted) {
            if (isComplete) {
              // Local cache says complete - go to home
              debugPrint('Using cached completion status (offline mode)');
              Navigator.of(context).pushReplacementNamed('/home');
            } else {
              // Resume onboarding with cached progress
              debugPrint('Resuming onboarding from cache (offline mode)');
              Navigator.of(context).pushReplacementNamed('/onboarding');
            }
          }
        } catch (localError) {
          debugPrint('Error reading local storage: $localError');
          // Ultimate fallback: start onboarding
          if (mounted) {
            Navigator.of(context).pushReplacementNamed('/onboarding');
          }
        }
      }
    } catch (e) {
      debugPrint('Error checking auth/onboarding: $e');
      if (mounted) {
        // Error -> start onboarding
        Navigator.of(context).pushReplacementNamed('/onboarding');
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return const Scaffold(
      body: Center(
        child: CircularProgressIndicator(),
      ),
    );
  }
}
