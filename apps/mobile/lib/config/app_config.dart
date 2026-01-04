class Config {
  // Supabase Configuration
  // TODO: Move these to Vercel environment variables in production
  static String get supabaseUrl {
    const v = String.fromEnvironment('SUPABASE_URL');
    final trimmed = v.trim();
    if (trimmed.isNotEmpty) return trimmed;
    return 'https://ondfkfkvfxffclzotuvm.supabase.co';
  }

  static String get supabaseAnonKey {
    const v = String.fromEnvironment('SUPABASE_ANON_KEY');
    final trimmed = v.trim();
    if (trimmed.isNotEmpty) return trimmed;
    return 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9uZGZrZmt2ZnhmZmNsem90dXZtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjcwMzU1NzYsImV4cCI6MjA4MjYxMTU3Nn0.ksizl220jrw0n7P2otYEprTgdNpke5whaoCK_09_kdQ';
  }
  
  // Backend API Configuration
  static String get apiBaseUrl {
    const v = String.fromEnvironment('API_BASE_URL');
    final trimmed = v.trim();
    if (trimmed.isNotEmpty) return trimmed;
    return 'https://savo-ynp1.onrender.com';
  }
  
  // Development mode flag
  static const bool isDevelopment = bool.fromEnvironment('DEV', defaultValue: false);
}
