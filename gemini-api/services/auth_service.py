import os
import hashlib
from supabase import create_client, Client
from google.oauth2 import id_token
from google.auth.transport import requests
from typing import Optional, Dict, Any

class AuthService:
    def __init__(self):
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
        
        if not supabase_url or not supabase_key:
            raise ValueError("Missing Supabase credentials")
            
        self.supabase: Client = create_client(supabase_url, supabase_key)
        self.google_client_id = os.getenv("GOOGLE_CLIENT_ID")

    def hash_password(self, password: str) -> str:
        """Simple password hashing - use proper bcrypt in production"""
        return hashlib.sha256(password.encode()).hexdigest()

    async def sign_up(self, email: str, password: str, name: Optional[str] = None) -> Dict[str, Any]:
        """Create new user account"""
        try:
            # Check if user exists
            existing = self.supabase.from_("music_users").select("*").eq("email", email).execute()
            if existing.data:
                raise ValueError("User already exists")

            # Create user
            user_data = {
                "email": email,
                "password_hash": self.hash_password(password),
                "name": name or email.split("@")[0],
                "is_vip": False
            }
            
            result = self.supabase.from_("music_users").insert(user_data).execute()
            if not result.data:
                raise ValueError("Failed to create user")
                
            user = result.data[0]
            return {
                "id": user["user_id"],
                "email": user["email"],
                "name": user["name"],
                "isVIP": user["is_vip"]
            }
            
        except Exception as e:
            raise ValueError(f"Sign up failed: {str(e)}")

    async def sign_in(self, email: str, password: str) -> Dict[str, Any]:
        """Authenticate user with email/password"""
        try:
            password_hash = self.hash_password(password)
            
            result = self.supabase.from_("music_users").select("*").eq("email", email).eq("password_hash", password_hash).execute()
            
            if not result.data:
                raise ValueError("Invalid credentials")
                
            user = result.data[0]
            return {
                "id": user["user_id"],
                "email": user["email"],
                "name": user["name"],
                "isVIP": user["is_vip"]
            }
            
        except Exception as e:
            raise ValueError(f"Sign in failed: {str(e)}")

    async def sign_in_with_google(self, id_token_str: str) -> Dict[str, Any]:
        """Authenticate user with Google ID token"""
        try:
            if not self.google_client_id:
                raise ValueError("Google authentication not configured")
                
            # Verify Google token
            idinfo = id_token.verify_oauth2_token(
                id_token_str, requests.Request(), self.google_client_id
            )
            
            email = idinfo["email"]
            name = idinfo.get("name", email.split("@")[0])
            
            # Check if user exists
            result = self.supabase.from_("music_users").select("*").eq("email", email).execute()
            
            if result.data:
                # Existing user
                user = result.data[0]
            else:
                # Create new user
                user_data = {
                    "email": email,
                    "name": name,
                    "is_vip": False,
                    "google_id": idinfo["sub"]
                }
                
                create_result = self.supabase.from_("music_users").insert(user_data).execute()
                if not create_result.data:
                    raise ValueError("Failed to create user")
                user = create_result.data[0]
            
            return {
                "id": user["user_id"],
                "email": user["email"],
                "name": user["name"],
                "isVIP": user["is_vip"]
            }
            
        except Exception as e:
            raise ValueError(f"Google sign in failed: {str(e)}")