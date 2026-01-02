"""
Database Migration Helper Functions
Helps verify and run migrations for SAVO database
"""
import os
import sys
from pathlib import Path
from typing import List, Dict, Optional
import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class DatabaseHelper:
    """Helper class for database operations and migration management"""
    
    def __init__(self):
        """Initialize database connection"""
        # Get database URL from environment
        self.database_url = os.getenv("DATABASE_URL")
        
        if not self.database_url:
            # Try to build from Supabase credentials
            supabase_url = os.getenv("SUPABASE_URL")
            if supabase_url:
                # Extract project ref from URL
                project_ref = supabase_url.replace("https://", "").split(".")[0]
                db_password = os.getenv("SUPABASE_DB_PASSWORD", "")
                self.database_url = f"postgresql://postgres:{db_password}@db.{project_ref}.supabase.co:5432/postgres"
        
        if not self.database_url:
            raise ValueError("DATABASE_URL or SUPABASE credentials must be set")
        
        self.conn = None
    
    def connect(self):
        """Establish database connection"""
        try:
            self.conn = psycopg2.connect(self.database_url)
            print("✅ Connected to database successfully")
            return True
        except Exception as e:
            print(f"❌ Failed to connect to database: {e}")
            return False
    
    def disconnect(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            print("✅ Disconnected from database")
    
    def execute_query(self, query: str, params: tuple = None) -> Optional[List[tuple]]:
        """Execute a SQL query and return results"""
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(query, params)
                
                # Check if query returns results
                if cursor.description:
                    results = cursor.fetchall()
                    return results
                else:
                    self.conn.commit()
                    return None
        except Exception as e:
            self.conn.rollback()
            print(f"❌ Query failed: {e}")
            raise
    
    def table_exists(self, table_name: str) -> bool:
        """Check if a table exists"""
        query = """
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = %s
            );
        """
        result = self.execute_query(query, (table_name,))
        return result[0][0] if result else False
    
    def column_exists(self, table_name: str, column_name: str) -> bool:
        """Check if a column exists in a table"""
        query = """
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_schema = 'public'
                AND table_name = %s 
                AND column_name = %s
            );
        """
        result = self.execute_query(query, (table_name, column_name))
        return result[0][0] if result else False
    
    def get_table_columns(self, table_name: str) -> List[Dict[str, str]]:
        """Get all columns for a table"""
        query = """
            SELECT column_name, data_type, column_default, is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'public'
            AND table_name = %s
            ORDER BY ordinal_position;
        """
        results = self.execute_query(query, (table_name,))
        
        columns = []
        for row in results:
            columns.append({
                'name': row[0],
                'type': row[1],
                'default': row[2],
                'nullable': row[3]
            })
        return columns
    
    def run_migration_file(self, filepath: Path) -> bool:
        """Run a single migration file"""
        try:
            print(f"\n📄 Running migration: {filepath.name}")
            
            with open(filepath, 'r', encoding='utf-8') as f:
                sql_content = f.read()
            
            # Execute the migration
            with self.conn.cursor() as cursor:
                cursor.execute(sql_content)
                self.conn.commit()
            
            print(f"✅ Migration {filepath.name} completed successfully")
            return True
            
        except Exception as e:
            self.conn.rollback()
            print(f"❌ Migration {filepath.name} failed: {e}")
            return False
    
    def verify_migrations(self) -> Dict[str, bool]:
        """Verify all critical database objects exist"""
        print("\n🔍 Verifying Database Schema...")
        print("=" * 60)
        
        verification = {}
        
        # Check critical tables
        tables_to_check = [
            'users',
            'household_profiles',
            'family_members',
            'ingredient_scans',
            'detected_ingredients',
            'user_pantry',
            'quantity_units',
            'standard_serving_sizes'
        ]
        
        print("\n📊 Tables:")
        for table in tables_to_check:
            exists = self.table_exists(table)
            verification[f"table_{table}"] = exists
            status = "✅" if exists else "❌"
            print(f"  {status} {table}")
        
        # Check critical columns
        columns_to_check = [
            ('household_profiles', 'skill_level'),
            ('household_profiles', 'dinner_courses'),
            ('user_pantry', 'quantity'),
            ('user_pantry', 'unit'),
            ('detected_ingredients', 'detected_quantity'),
            ('detected_ingredients', 'detected_unit'),
        ]
        
        print("\n📝 Columns:")
        for table, column in columns_to_check:
            exists = self.column_exists(table, column)
            verification[f"column_{table}.{column}"] = exists
            status = "✅" if exists else "❌"
            print(f"  {status} {table}.{column}")
        
        # Check functions
        print("\n⚙️ Functions:")
        functions_to_check = [
            'convert_unit',
            'get_standard_serving',
            'check_recipe_sufficiency',
            'auto_add_confirmed_to_pantry'
        ]
        
        for func in functions_to_check:
            query = """
                SELECT EXISTS (
                    SELECT FROM pg_proc 
                    WHERE proname = %s
                );
            """
            result = self.execute_query(query, (func,))
            exists = result[0][0] if result else False
            verification[f"function_{func}"] = exists
            status = "✅" if exists else "❌"
            print(f"  {status} {func}()")
        
        # Summary
        print("\n" + "=" * 60)
        total = len(verification)
        passed = sum(1 for v in verification.values() if v)
        print(f"\n📊 Verification Summary: {passed}/{total} checks passed")
        
        if passed == total:
            print("✅ All database objects verified successfully!")
        else:
            print(f"⚠️  {total - passed} checks failed. Review missing objects above.")
        
        return verification
    
    def get_migration_status(self) -> Dict[str, Dict]:
        """Get detailed status of all migrations"""
        migrations_dir = Path(__file__).parent
        migration_files = sorted(migrations_dir.glob('*.sql'))
        
        status = {}
        for migration_file in migration_files:
            status[migration_file.name] = {
                'exists': migration_file.exists(),
                'size': migration_file.stat().st_size if migration_file.exists() else 0,
                'path': str(migration_file)
            }
        
        return status


def main():
    """Main function to run database verification"""
    print("=" * 60)
    print("SAVO Database Helper & Migration Verification")
    print("=" * 60)
    
    db = DatabaseHelper()
    
    if not db.connect():
        print("\n❌ Cannot proceed without database connection")
        print("\nPlease ensure:")
        print("  1. DATABASE_URL is set in environment")
        print("  2. OR SUPABASE_URL and SUPABASE_DB_PASSWORD are set")
        print("  3. Database is accessible")
        return False
    
    try:
        # Verify all migrations
        verification = db.verify_migrations()
        
        # Show migration files status
        print("\n" + "=" * 60)
        print("📁 Migration Files:")
        print("=" * 60)
        
        migration_status = db.get_migration_status()
        for filename, info in migration_status.items():
            size_kb = info['size'] / 1024
            print(f"  ✅ {filename} ({size_kb:.1f} KB)")
        
        # Show critical table schemas
        print("\n" + "=" * 60)
        print("🔍 Critical Table Schemas:")
        print("=" * 60)
        
        critical_tables = ['household_profiles', 'user_pantry']
        for table in critical_tables:
            if db.table_exists(table):
                print(f"\n  📊 {table}:")
                columns = db.get_table_columns(table)
                for col in columns:
                    nullable = "NULL" if col['nullable'] == 'YES' else "NOT NULL"
                    default = f" DEFAULT {col['default']}" if col['default'] else ""
                    print(f"    - {col['name']}: {col['type']} {nullable}{default}")
        
        return all(verification.values())
        
    finally:
        db.disconnect()


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
