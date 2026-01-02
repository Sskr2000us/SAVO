"""
Run All Migrations in Order
Executes all migration files in the correct sequence
"""
import sys
from pathlib import Path
from db_helper import DatabaseHelper


def run_all_migrations():
    """Run all migration files in order"""
    print("=" * 60)
    print("SAVO Database Migration Runner")
    print("=" * 60)
    
    db = DatabaseHelper()
    
    if not db.connect():
        print("\n❌ Cannot proceed without database connection")
        return False
    
    try:
        migrations_dir = Path(__file__).parent
        
        # Get all SQL migration files in order
        migration_files = sorted(migrations_dir.glob('[0-9]*.sql'))
        
        if not migration_files:
            print("\n⚠️  No migration files found matching pattern [0-9]*.sql")
            return False
        
        print(f"\n📋 Found {len(migration_files)} migration(s) to run:")
        for mf in migration_files:
            print(f"  - {mf.name}")
        
        print("\n" + "=" * 60)
        
        # Run each migration
        success_count = 0
        failed_migrations = []
        
        for migration_file in migration_files:
            success = db.run_migration_file(migration_file)
            if success:
                success_count += 1
            else:
                failed_migrations.append(migration_file.name)
        
        # Summary
        print("\n" + "=" * 60)
        print(f"Migration Summary: {success_count}/{len(migration_files)} successful")
        print("=" * 60)
        
        if failed_migrations:
            print(f"\n❌ Failed migrations:")
            for name in failed_migrations:
                print(f"  - {name}")
            return False
        else:
            print("\n✅ All migrations completed successfully!")
            
            # Run verification
            print("\n" + "=" * 60)
            print("Running post-migration verification...")
            print("=" * 60)
            verification = db.verify_migrations()
            
            return all(verification.values())
    
    finally:
        db.disconnect()


if __name__ == "__main__":
    success = run_all_migrations()
    sys.exit(0 if success else 1)
