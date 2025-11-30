#!/usr/bin/env python3
"""
Cleanup script for expired Platinum download files
Run daily via cron: 0 2 * * * cd /app && python cleanup_platinum.py
"""

import os
import sys
from datetime import datetime
from supabase import create_client
from dotenv import load_dotenv

def cleanup_expired_platinum_files():
    """Clean up expired Platinum download files from storage and database"""
    
    # Load environment variables
    load_dotenv()
    
    # Initialize Supabase
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
    
    if not supabase_url or not supabase_key:
        print("❌ Missing Supabase credentials")
        return False
    
    try:
        supabase = create_client(supabase_url, supabase_key)
        now = datetime.now().isoformat()
        
        print(f"🧹 Starting cleanup at {now}")
        
        # Get expired downloads
        expired_result = (
            supabase.table("platinum_downloads")
            .select("file_path, token, title")
            .lt("expires_at", now)
            .execute()
        )
        
        if not expired_result.data:
            print("🔍 No expired files found")
            return True
        
        expired_files = expired_result.data
        print(f"📋 Found {len(expired_files)} expired files")
        
        # Delete files from storage
        file_paths = [item["file_path"] for item in expired_files]
        deleted_count = 0
        
        for file_path in file_paths:
            try:
                supabase.storage.from_("music").remove([file_path])
                deleted_count += 1
                print(f"🗑️  Deleted: {file_path}")
            except Exception as e:
                print(f"⚠️  Failed to delete {file_path}: {e}")
        
        # Clean database records
        delete_result = (
            supabase.table("platinum_downloads")
            .delete()
            .lt("expires_at", now)
            .execute()
        )
        
        db_deleted = len(delete_result.data) if delete_result.data else 0
        
        print(f"✅ Cleanup complete:")
        print(f"   - Storage files deleted: {deleted_count}/{len(file_paths)}")
        print(f"   - Database records cleaned: {db_deleted}")
        
        return True
        
    except Exception as e:
        print(f"❌ Cleanup failed: {e}")
        return False

def main():
    """Main entry point"""
    success = cleanup_expired_platinum_files()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()