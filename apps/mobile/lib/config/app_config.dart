class Config {
  // Supabase Configuration
  // TODO: Move these to Vercel environment variables in production
  static const String supabaseUrl = String.fromEnvironment(
    'SUPABASE_URL',
    defaultValue: 'https://ondfkfkvfxffclzotuvm.supabase.co', // Your Supabase project URL
  );
  
  static const String supabaseAnonKey = String.fromEnvironment(
    'SUPABASE_ANON_KEY',
    defaultValue: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9uZGZrZmt2ZnhmZmNsem90dXZtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjcwMzU1NzYsImV4cCI6MjA4MjYxMTU3Nn0.ksizl220jrw0n7P2otYEprTgdNpke5whaoCK_09_kdQ', // Your Supabase anon key
  );
  
  // Backend API Configuration
  static const String apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'https://savo-ynp1.onrender.com',
  );
  
  // Development mode flag
  static const bool isDevelopment = bool.fromEnvironment('DEV', defaultValue: false);
}
