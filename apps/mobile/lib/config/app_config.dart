class Config {
  // Supabase Configuration
  // TODO: Move these to Vercel environment variables in production
  static const String supabaseUrl = String.fromEnvironment(
    'SUPABASE_URL',
    defaultValue: 'https://tifecgfgtxkydqxjumnn.supabase.co', // Your Supabase project URL
  );
  
  static const String supabaseAnonKey = String.fromEnvironment(
    'SUPABASE_ANON_KEY',
    defaultValue: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRpZmVjZ2ZndHhreWRxeGp1bW5uIiwicm9sZSI6ImFub24iLCJpYXQiOjE3MzU1OTUxNjEsImV4cCI6MjA1MTE3MTE2MX0.PUQ_BEv-KTkKnAvVd2_LbSPdO7kU8AkkIOKo8z_hXqc', // Your Supabase anon key
  );
  
  // Backend API Configuration
  static const String apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'https://savo-ynp1.onrender.com',
  );
  
  // Development mode flag
  static const bool isDevelopment = bool.fromEnvironment('DEV', defaultValue: false);
}
