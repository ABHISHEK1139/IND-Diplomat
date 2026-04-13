"""
JWT Authentication for IND-Diplomat
Provides secure token-based authentication.
"""

import os
import jwt
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum

try:
    from passlib.context import CryptContext
    PASSLIB_AVAILABLE = True
except ImportError:
    PASSLIB_AVAILABLE = False


logger = logging.getLogger(__name__)


class Role(Enum):
    """User roles for RBAC."""
    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"


@dataclass
class User:
    """User model."""
    user_id: str
    username: str
    role: Role
    organization: str
    is_active: bool = True


class JWTAuth:
    """
    Production-grade JWT authentication with:
    1. Token generation and validation
    2. Password hashing
    3. Role-based claims
    4. Configurable expiration
    """
    
    def __init__(self):
        self.auth_mode = str(os.getenv("AUTH_MODE", "development") or "development").strip().lower()
        self.strict_security = str(os.getenv("AUTH_STRICT_SECURITY", "false") or "false").strip().lower() in {
            "1", "true", "yes", "on"
        }

        secret = str(os.getenv("JWT_SECRET_KEY", "") or "").strip()
        if not secret:
            if self.auth_mode == "production" or self.strict_security:
                raise RuntimeError("JWT_SECRET_KEY must be configured in production/strict mode")
            secret = "dev-insecure-jwt-secret"
            logger.warning("JWT_SECRET_KEY not set; using development fallback secret")

        if secret == "super-secret-key-change-in-production":
            if self.auth_mode == "production" or self.strict_security:
                raise RuntimeError("Refusing weak default JWT secret in production/strict mode")
            logger.warning("Weak JWT secret configured; rotate JWT_SECRET_KEY before production")

        self.secret_key = secret
        self.algorithm = "HS256"
        self.access_token_expire_minutes = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
        self.refresh_token_expire_days = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
        
        if PASSLIB_AVAILABLE:
            self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        else:
            self.pwd_context = None
        
        # In-memory user store (replace with database in production)
        # Using plain text for demo - in production, store hashed passwords from a database
        def _hash(pw: str) -> str:
            if self.pwd_context:
                try:
                    return self.pwd_context.hash(pw)
                except Exception:
                    pass
            return pw

        enable_demo_users = str(
            os.getenv(
                "AUTH_ENABLE_DEMO_USERS",
                "true" if self.auth_mode != "production" else "false",
            )
            or "false"
        ).strip().lower() in {"1", "true", "yes", "on"}

        self._users: Dict[str, Dict] = {}

        if enable_demo_users:
            admin_password = str(os.getenv("AUTH_DEMO_ADMIN_PASSWORD", "admin123") or "admin123")
            analyst_password = str(os.getenv("AUTH_DEMO_ANALYST_PASSWORD", "analyst123") or "analyst123")
            self._users.update(
                {
                    "admin": {
                        "user_id": "u001",
                        "username": "admin",
                        "password_hash": _hash(admin_password),
                        "role": Role.ADMIN,
                        "organization": "MEA",
                        "is_active": True,
                    },
                    "analyst": {
                        "user_id": "u002",
                        "username": "analyst",
                        "password_hash": _hash(analyst_password),
                        "role": Role.ANALYST,
                        "organization": "MEA",
                        "is_active": True,
                    },
                }
            )

        bootstrap_username = str(os.getenv("AUTH_BOOTSTRAP_USERNAME", "") or "").strip()
        bootstrap_password = str(os.getenv("AUTH_BOOTSTRAP_PASSWORD", "") or "").strip()
        if bootstrap_username and bootstrap_password:
            role_name = str(os.getenv("AUTH_BOOTSTRAP_ROLE", "admin") or "admin").strip().lower()
            role_value = Role.ADMIN if role_name == "admin" else (Role.VIEWER if role_name == "viewer" else Role.ANALYST)
            self._users[bootstrap_username] = {
                "user_id": str(os.getenv("AUTH_BOOTSTRAP_USER_ID", f"u_{bootstrap_username}") or f"u_{bootstrap_username}"),
                "username": bootstrap_username,
                "password_hash": _hash(bootstrap_password),
                "role": role_value,
                "organization": str(os.getenv("AUTH_BOOTSTRAP_ORG", "MEA") or "MEA"),
                "is_active": True,
            }
    
    def hash_password(self, password: str) -> str:
        """Hashes a password."""
        if self.pwd_context:
            return self.pwd_context.hash(password)
        return password  # Fallback (not secure)
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verifies a password against its hash."""
        if self.pwd_context:
            try:
                return self.pwd_context.verify(plain_password, hashed_password)
            except Exception:
                pass
        return plain_password == hashed_password  # Fallback
    
    def create_access_token(self, user: User, expires_delta: timedelta = None) -> str:
        """Creates a JWT access token."""
        if expires_delta is None:
            expires_delta = timedelta(minutes=self.access_token_expire_minutes)
        
        expire = datetime.utcnow() + expires_delta
        
        payload = {
            "sub": user.user_id,
            "username": user.username,
            "role": user.role.value,
            "org": user.organization,
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "access"
        }
        
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
    
    def create_refresh_token(self, user: User) -> str:
        """Creates a JWT refresh token."""
        expire = datetime.utcnow() + timedelta(days=self.refresh_token_expire_days)
        
        payload = {
            "sub": user.user_id,
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "refresh"
        }
        
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
    
    def decode_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Decodes and validates a JWT token."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
    
    def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """Authenticates a user."""
        user_data = self._users.get(username)
        if not user_data:
            return None
        
        if not self.verify_password(password, user_data["password_hash"]):
            return None
        
        if not user_data["is_active"]:
            return None
        
        return User(
            user_id=user_data["user_id"],
            username=user_data["username"],
            role=user_data["role"],
            organization=user_data["organization"],
            is_active=user_data["is_active"]
        )
    
    def get_user_from_token(self, token: str) -> Optional[User]:
        """Gets user from token."""
        payload = self.decode_token(token)
        if not payload:
            return None
        
        username = payload.get("username")
        user_data = self._users.get(username)
        if not user_data:
            return None
        
        return User(
            user_id=user_data["user_id"],
            username=user_data["username"],
            role=user_data["role"],
            organization=user_data["organization"],
            is_active=user_data["is_active"]
        )


class RBAC:
    """
    Role-Based Access Control for IND-Diplomat.
    Defines permissions for each role.
    """
    
    PERMISSIONS = {
        Role.ADMIN: {
            "query": True,
            "query_stream": True,
            "ingest": True,
            "export_report": True,
            "view_metrics": True,
            "manage_users": True,
            "view_audit": True,
            "use_mcts": True,
            "use_causal": True,
            "use_red_team": True,
            "use_multi_perspective": True
        },
        Role.ANALYST: {
            "query": True,
            "query_stream": True,
            "ingest": False,
            "export_report": True,
            "view_metrics": False,
            "manage_users": False,
            "view_audit": False,
            "use_mcts": True,
            "use_causal": True,
            "use_red_team": True,
            "use_multi_perspective": True
        },
        Role.VIEWER: {
            "query": True,
            "query_stream": True,
            "ingest": False,
            "export_report": False,
            "view_metrics": False,
            "manage_users": False,
            "view_audit": False,
            "use_mcts": False,
            "use_causal": False,
            "use_red_team": False,
            "use_multi_perspective": False
        }
    }
    
    @classmethod
    def has_permission(cls, role: Role, permission: str) -> bool:
        """Checks if a role has a specific permission."""
        role_permissions = cls.PERMISSIONS.get(role, {})
        return role_permissions.get(permission, False)
    
    @classmethod
    def get_role_permissions(cls, role: Role) -> Dict[str, bool]:
        """Gets all permissions for a role."""
        return cls.PERMISSIONS.get(role, {})


# Singleton instance
jwt_auth = JWTAuth()


def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Verify a JWT token and return the payload.
    This is a convenience function for the jwt_auth.decode_token method.
    """
    return jwt_auth.decode_token(token)

