#!/usr/bin/env python3
"""
Admin script to add new psyche tracks to the library
Usage: python add_psyche_track.py track_007.m4a "Track Title" 180 "tag1,tag2,tag3"
"""

import sys
import os
import json
import base64
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client
from google.cloud import storage
from google.oauth2 import service_account

load_dotenv()

def upload_and_add_track(file_path: str, title: str, duration: int, tags: str):
    """Upload track to GCS and add metadata to database"""
    
    # Validate file
    if not Path(file_path).exists():
        print(f"❌ File not found: {file_path}")
        return False
    
    # Generate track ID
    file_name = Path(file_path).name
    track_id = Path(file_name).stem  # e.g., "track_007" from "track_007.m4a"
    
    print(f"🎵 Adding track: {track_id}")
    print(f"   Title: {title}")
    print(f"   Duration: {duration}s")
    print(f"   Tags: {tags}")
    
    try:
        # 1. Upload to GCS
        print("☁️ Uploading to Google Cloud Storage...")
        
        credentials_json = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")
        if credentials_json:
            credentials_info = json.loads(base64.b64decode(credentials_json))
            credentials = service_account.Credentials.from_service_account_info(credentials_info)
            client = storage.Client(credentials=credentials, project=credentials_info['project_id'])
        else:
            client = storage.Client()
        
        bucket_name = os.getenv("GCS_BUCKET_NAME", "subliminalgen-temp-files")
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(f"psyche-tracks/{file_name}")
        
        blob.upload_from_filename(file_path)
        print(f"✅ Uploaded: gs://{bucket_name}/psyche-tracks/{file_name}")
        
        # 2. Add to database
        print("🗄 Adding to Supabase database...")
        
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
        supabase = create_client(supabase_url, supabase_key)
        
        # Parse tags
        tag_list = [tag.strip() for tag in tags.split(",")]
        
        track_data = {
            "id": track_id,
            "title": title,
            "duration": duration,
            "tags": tag_list,
            "file_path": file_name
        }
        
        result = supabase.table("psyche_tracks").insert(track_data).execute()
        
        if result.data:
            print(f"✅ Added to database: {track_id}")
            print(f"   Database record: {result.data[0]}")
            
            # 3. Bump library version
            print("📈 Bumping library version...")
            
            # Get current version
            version_response = supabase.table("psyche_tracks_version").select("version").single().execute()
            current_version = version_response.data["version"]
            new_version = current_version + 1
            
            # Update version
            update_response = supabase.table("psyche_tracks_version").update({
                "version": new_version,
                "last_updated": "now()"
            }).eq("id", "psyche_tracks").execute()
            
            if update_response.data:
                print(f"✅ Library version bumped to: {new_version}")
            else:
                print("⚠️ Version bump failed (non-critical)")
            
            return True
        else:
            print("❌ Failed to add to database")
            return False
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False

if __name__ == "__main__":
    if len(sys.argv) != 5:
        print("Usage: python add_psyche_track.py <file_path> <title> <duration> <tags>")
        print("Example: python add_psyche_track.py track_007.m4a 'Confidence Boost' 240 'confidence,power,success'")
        sys.exit(1)
    
    file_path = sys.argv[1]
    title = sys.argv[2]
    duration = int(sys.argv[3])
    tags = sys.argv[4]
    
    success = upload_and_add_track(file_path, title, duration, tags)
    sys.exit(0 if success else 1)