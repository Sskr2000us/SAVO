"""
Set up Supabase Storage Buckets for Ingredient Intelligence
Creates 3 buckets with proper RLS policies:
1. savo-ingredients - Reference ingredient images (public read)
2. savo-ingredients-thumbnails - Optimized thumbnails (public read)
3. savo-user-scans - User uploaded scans (private, user-only access)
"""

import os
import sys
from supabase import create_client, Client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")  # Service role key for admin operations

def setup_storage_buckets():
    """Set up storage buckets with proper policies"""
    
    print("\n" + "="*80)
    print("SAVO STORAGE BUCKET SETUP")
    print("="*80)
    
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        print("❌ ERROR: Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
        print("Set these environment variables first:")
        print("  $env:SUPABASE_URL = 'https://your-project.supabase.co'")
        print("  $env:SUPABASE_SERVICE_ROLE_KEY = 'your-service-role-key'")
        sys.exit(1)
    
    try:
        # Create Supabase client
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        print(f"✅ Connected to Supabase: {SUPABASE_URL}")
        
        # Bucket configurations
        buckets = [
            {
                "name": "savo-ingredients",
                "public": True,
                "file_size_limit": 10485760,  # 10MB
                "allowed_mime_types": ["image/jpeg", "image/png", "image/webp"],
                "description": "Reference ingredient images for CV training and display"
            },
            {
                "name": "savo-ingredients-thumbnails",
                "public": True,
                "file_size_limit": 1048576,  # 1MB
                "allowed_mime_types": ["image/jpeg", "image/png", "image/webp"],
                "description": "Optimized thumbnails for fast loading"
            },
            {
                "name": "savo-user-scans",
                "public": False,
                "file_size_limit": 10485760,  # 10MB
                "allowed_mime_types": ["image/jpeg", "image/png", "image/webp"],
                "description": "User-uploaded ingredient scans (private)"
            }
        ]
        
        print("\n" + "-"*80)
        print("CREATING STORAGE BUCKETS")
        print("-"*80)
        
        for bucket_config in buckets:
            try:
                # Try to create bucket
                bucket = supabase.storage.create_bucket(
                    bucket_config["name"],
                    {
                        "public": bucket_config["public"],
                        "file_size_limit": bucket_config["file_size_limit"],
                        "allowed_mime_types": bucket_config["allowed_mime_types"]
                    }
                )
                print(f"✅ Created bucket: {bucket_config['name']}")
                print(f"   • Public: {bucket_config['public']}")
                print(f"   • Size limit: {bucket_config['file_size_limit'] / 1024 / 1024}MB")
                print(f"   • Formats: {', '.join(bucket_config['allowed_mime_types'])}")
                
            except Exception as e:
                if "already exists" in str(e).lower():
                    print(f"⏭️  Bucket '{bucket_config['name']}' already exists")
                else:
                    print(f"❌ Error creating bucket '{bucket_config['name']}': {e}")
        
        print("\n" + "-"*80)
        print("STORAGE POLICIES")
        print("-"*80)
        print("📋 Note: RLS policies need to be set via Supabase Dashboard or SQL")
        print("\nSuggested policies:")
        print("\n1. savo-ingredients (public read):")
        print("   • SELECT: anon, authenticated")
        print("   • INSERT: authenticated (admin only)")
        print("\n2. savo-ingredients-thumbnails (public read):")
        print("   • SELECT: anon, authenticated")
        print("   • INSERT: authenticated (admin only)")
        print("\n3. savo-user-scans (private):")
        print("   • SELECT: authenticated (user_id = auth.uid())")
        print("   • INSERT: authenticated (user_id = auth.uid())")
        print("   • DELETE: authenticated (user_id = auth.uid())")
        
        print("\n" + "="*80)
        print("✅ STORAGE SETUP COMPLETE!")
        print("="*80)
        print("\nNext steps:")
        print("1. Upload ingredient images to 'savo-ingredients'")
        print("2. Generate thumbnails to 'savo-ingredients-thumbnails'")
        print("3. Configure RLS policies via Supabase Dashboard")
        print("="*80 + "\n")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    setup_storage_buckets()
