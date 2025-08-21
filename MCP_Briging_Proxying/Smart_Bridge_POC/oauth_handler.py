#!/usr/bin/env python3
"""
OAuth 2.1 with PKCE implementation for MCP SSE Bridge
"""

import base64
import hashlib
import secrets
import time
import urllib.parse
from typing import Dict, Optional
import aiohttp
import jwt
from fastapi import HTTPException

class OAuth2Handler:
    """OAuth 2.1 with PKCE implementation for Google OAuth"""
    
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str, allowed_domains: list = None):
        self.client_id = client_id
        self.client_secret = client_secret  
        self.redirect_uri = redirect_uri
        self.allowed_domains = allowed_domains or []
        
        # Google OAuth endpoints
        self.auth_endpoint = "https://accounts.google.com/o/oauth2/v2/auth"
        self.token_endpoint = "https://oauth2.googleapis.com/token"
        self.userinfo_endpoint = "https://www.googleapis.com/oauth2/v2/userinfo"
        
        # In-memory session storage (use Redis/DB for production)
        self.sessions: Dict[str, Dict] = {}
        self.auth_codes: Dict[str, Dict] = {}
    
    def generate_pkce_pair(self) -> tuple[str, str]:
        """Generate PKCE code verifier and challenge"""
        # Generate code verifier (43-128 characters)
        code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')
        
        # Generate code challenge (SHA256 hash of verifier)
        challenge = hashlib.sha256(code_verifier.encode('utf-8')).digest()
        code_challenge = base64.urlsafe_b64encode(challenge).decode('utf-8').rstrip('=')
        
        return code_verifier, code_challenge
    
    def generate_authorization_url(self, state: str = None) -> tuple[str, str, str]:
        """Generate OAuth authorization URL with PKCE"""
        if not state:
            state = secrets.token_urlsafe(32)
        
        code_verifier, code_challenge = self.generate_pkce_pair()
        
        # Store PKCE parameters for later verification
        self.auth_codes[state] = {
            "code_verifier": code_verifier,
            "code_challenge": code_challenge,
            "created_at": time.time()
        }
        
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "access_type": "offline",  # Request refresh token
            "prompt": "consent"
        }
        
        auth_url = f"{self.auth_endpoint}?{urllib.parse.urlencode(params)}"
        return auth_url, state, code_verifier
    
    async def exchange_code_for_tokens(self, code: str, state: str) -> Dict[str, str]:
        """Exchange authorization code for access token using PKCE"""
        if state not in self.auth_codes:
            raise HTTPException(400, "Invalid state parameter")
        
        auth_data = self.auth_codes[state]
        
        # Check state expiry (10 minutes)
        if time.time() - auth_data["created_at"] > 600:
            del self.auth_codes[state]
            raise HTTPException(400, "Authorization code expired")
        
        token_data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "grant_type": "authorization_code", 
            "redirect_uri": self.redirect_uri,
            "code_verifier": auth_data["code_verifier"]
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(self.token_endpoint, data=token_data) as response:
                if response.status != 200:
                    text = await response.text()
                    raise HTTPException(400, f"Token exchange failed: {text}")
                
                tokens = await response.json()
        
        # Clean up used auth code
        del self.auth_codes[state]
        return tokens
    
    async def get_user_info(self, access_token: str) -> Dict[str, str]:
        """Get user information from Google"""
        headers = {"Authorization": f"Bearer {access_token}"}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(self.userinfo_endpoint, headers=headers) as response:
                if response.status != 200:
                    raise HTTPException(401, "Invalid access token")
                
                user_info = await response.json()
        
        # Validate domain if configured
        if self.allowed_domains:
            email = user_info.get("email", "")
            domain = email.split("@")[-1] if "@" in email else ""
            if domain not in self.allowed_domains:
                raise HTTPException(403, f"Domain {domain} not allowed")
        
        return user_info
    
    def create_session(self, user_info: Dict, tokens: Dict) -> str:
        """Create user session"""
        session_id = secrets.token_urlsafe(32)
        
        self.sessions[session_id] = {
            "user_id": user_info.get("id"),
            "email": user_info.get("email"),
            "name": user_info.get("name"),
            "access_token": tokens.get("access_token"),
            "refresh_token": tokens.get("refresh_token"),
            "expires_at": time.time() + tokens.get("expires_in", 3600),
            "created_at": time.time()
        }
        
        return session_id
    
    def validate_session(self, session_id: str) -> Optional[Dict]:
        """Validate session and return user info"""
        if session_id not in self.sessions:
            return None
        
        session = self.sessions[session_id]
        
        # Check if token expired
        if time.time() > session["expires_at"]:
            # TODO: Implement refresh token logic
            del self.sessions[session_id]
            return None
        
        return session
    
    def get_oauth_metadata(self, base_url: str) -> Dict:
        """Return OAuth 2.1 authorization server metadata"""
        return {
            "issuer": base_url,
            "authorization_endpoint": f"{base_url}/oauth/authorize",
            "token_endpoint": f"{base_url}/oauth/token", 
            "userinfo_endpoint": f"{base_url}/oauth/userinfo",
            "registration_endpoint": f"{base_url}/oauth/register",
            "scopes_supported": ["openid", "email", "profile"],
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "code_challenge_methods_supported": ["S256"],
            "subject_types_supported": ["public"],
            "id_token_signing_alg_values_supported": ["RS256"],
            "token_endpoint_auth_methods_supported": ["client_secret_post", "client_secret_basic"]
        }