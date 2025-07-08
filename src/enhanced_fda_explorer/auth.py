"""
Authentication and authorization for Enhanced FDA Explorer
"""

import jwt
import hashlib
import secrets
from typing import Dict, Optional, Any
from datetime import datetime, timedelta
from pydantic import BaseModel

from .config import get_config


class User(BaseModel):
    """User model"""
    username: str
    email: str
    roles: list = []
    is_active: bool = True
    created_at: datetime = datetime.now()


class AuthManager:
    """Authentication and authorization manager"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.secret_key = config.auth.secret_key
        self.algorithm = config.auth.algorithm
        self.access_token_expire_minutes = config.auth.access_token_expire_minutes
    
    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None):
        """Create access token"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    async def get_current_user(self, token: str) -> Optional[User]:
        """Get current user from token"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            username: str = payload.get("sub")
            if username is None:
                return None
            # In a real implementation, you would fetch user from database
            return User(username=username, email=f"{username}@example.com")
        except jwt.PyJWTError:
            return None
    
    def hash_password(self, password: str) -> str:
        """Hash password"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify password"""
        return self.hash_password(plain_password) == hashed_password