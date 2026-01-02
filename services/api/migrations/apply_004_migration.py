"""
Apply migration 004 - Add dinner_courses column
"""
import os
import sys
from pathlib import Path

# Add parent directory to path to import supabase client
sys.path.insert(0, str(Path(__file__).parent.parent))

from supabase import create_client

def apply_migration():
    """Apply the dinner_courses migration"""
    
    # Get Supabase credentials
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    
    if not url or not key:
        print("❌ Error: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
        return False
    
    try:
        # Connect to Supabase
        client = create_client(url, key)
        print("✅ Connected to Supabase")
        
        # Read migration file
        migration_file = Path(__file__).parent / "004_add_dinner_courses.sql"
        with open(migration_file, 'r') as f:
            sql = f.read()
        
        print(f"📄 Read migration: {migration_file.name}")
        
        # Execute migration (Supabase Python client doesn't directly support raw SQL)
        # We'll use the REST API to execute via a stored procedure or direct query
        print("\n⚠️  Manual Step Required:")
        print("Please run this migration in Supabase SQL Editor:")
        print("=" * 60)
        print(sql)
        print("=" * 60)
        
        print("\n📝 Or use Supabase CLI:")
        print(f"   supabase db execute -f {migration_file}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    apply_migration()
