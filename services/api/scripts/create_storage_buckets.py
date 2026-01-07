"""
Create Supabase Storage Buckets Programmatically

This script creates the 3 required storage buckets for SAVO:
1. savo-ingredients (public)
2. savo-ingredients-thumbnails (public)
3. savo-user-scans (private)

Usage:
    python services/api/scripts/create_storage_buckets.py

Environment Variables Required:
    SUPABASE_URL - Your Supabase project URL
    SUPABASE_SERVICE_ROLE_KEY - Service role key (NOT anon key!)
"""

import os
import sys
from supabase import create_client, Client


def create_storage_buckets():
    """Create storage buckets with proper configuration"""
    
    # Get credentials
    supabase_url = os.getenv("SUPABASE_URL")
    service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if not supabase_url or not service_role_key:
        print("❌ Error: Missing environment variables")
        print("   Required: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY")
        print("\n   Set them with:")
        print('   $env:SUPABASE_URL="https://your-project.supabase.co"')
        print('   $env:SUPABASE_SERVICE_ROLE_KEY="your-service-role-key"')
        sys.exit(1)
    
    print(f"🔗 Connecting to: {supabase_url}")
    
    # Initialize Supabase client with service role key
    supabase: Client = create_client(supabase_url, service_role_key)
    
    # Define buckets
    buckets = [
        {
            "id": "savo-ingredients",
            "name": "savo-ingredients",
            "public": True,
            "file_size_limit": 10485760,  # 10 MB
            "allowed_mime_types": ["image/jpeg", "image/png", "image/webp"]
        },
        {
            "id": "savo-ingredients-thumbnails",
            "name": "savo-ingredients-thumbnails",
            "public": True,
            "file_size_limit": 1048576,  # 1 MB
            "allowed_mime_types": ["image/jpeg", "image/png", "image/webp"]
        },
        {
            "id": "savo-user-scans",
            "name": "savo-user-scans",
            "public": False,
            "file_size_limit": 10485760,  # 10 MB
            "allowed_mime_types": ["image/jpeg", "image/png", "image/webp"]
        }
    ]
    
    print("\n📦 Creating storage buckets...\n")
    
    created_count = 0
    existing_count = 0
    
    for bucket_config in buckets:
        bucket_id = bucket_config["id"]
        bucket_name = bucket_config["name"]
        is_public = bucket_config["public"]
        
        try:
            # Attempt to create bucket
            result = supabase.storage.create_bucket(
                bucket_id,
                options={
                    "public": is_public,
                    "file_size_limit": bucket_config["file_size_limit"],
                    "allowed_mime_types": bucket_config["allowed_mime_types"]
                }
            )
            
            visibility = "PUBLIC" if is_public else "PRIVATE"
            print(f"✅ Created bucket: {bucket_name} ({visibility})")
            created_count += 1
            
        except Exception as e:
            error_msg = str(e).lower()
            
            if "already exists" in error_msg or "duplicate" in error_msg:
                visibility = "PUBLIC" if is_public else "PRIVATE"
                print(f"⚠️  Bucket already exists: {bucket_name} ({visibility})")
                existing_count += 1
            else:
                print(f"❌ Failed to create bucket {bucket_name}: {e}")
    
    # Summary
    print("\n" + "="*60)
    print(f"📊 Summary:")
    print(f"   ✅ Created: {created_count} bucket(s)")
    print(f"   ⚠️  Already existed: {existing_count} bucket(s)")
    print(f"   📦 Total: {created_count + existing_count} bucket(s)")
    print("="*60)
    
    # Verify buckets
    print("\n🔍 Verifying buckets...\n")
    
    try:
        all_buckets = supabase.storage.list_buckets()
        
        savo_buckets = [b for b in all_buckets if b.get("name", "").startswith("savo-")]
        
        if savo_buckets:
            print("📋 SAVO Buckets:")
            for bucket in savo_buckets:
                name = bucket.get("name", "unknown")
                is_public = bucket.get("public", False)
                visibility = "PUBLIC" if is_public else "PRIVATE"
                print(f"   • {name} ({visibility})")
        
        if len(savo_buckets) == 3:
            print("\n✅ All 3 buckets verified successfully!")
            print("\n📝 Next steps:")
            print("   1. Run SQL migration to apply RLS policies:")
            print("      services/api/migrations/006_storage_policies_only.sql")
            print("   2. Upload reference images")
            print("   3. Test image URLs")
        else:
            print(f"\n⚠️  Warning: Expected 3 buckets, found {len(savo_buckets)}")
    
    except Exception as e:
        print(f"❌ Failed to verify buckets: {e}")


if __name__ == "__main__":
    print("=" * 60)
    print("SAVO Storage Bucket Creation")
    print("=" * 60)
    
    try:
        create_storage_buckets()
        print("\n✅ Bucket creation complete!")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)
