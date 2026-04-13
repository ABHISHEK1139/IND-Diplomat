"""
Session Memory for IND-Diplomat
Provides conversation history and multi-turn reasoning support.
"""

import os
import json
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


@dataclass
class Message:
    """Represents a conversation message."""
    role: str  # 'user', 'assistant', 'system'
    content: str
    timestamp: str
    metadata: Dict[str, Any] = None
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Message':
        return cls(**data)


@dataclass
class Session:
    """Represents a conversation session."""
    session_id: str
    user_id: str
    created_at: str
    last_activity: str
    messages: List[Message]
    context: Dict[str, Any]
    
    def to_dict(self) -> Dict:
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "created_at": self.created_at,
            "last_activity": self.last_activity,
            "messages": [m.to_dict() for m in self.messages],
            "context": self.context
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Session':
        return cls(
            session_id=data["session_id"],
            user_id=data["user_id"],
            created_at=data["created_at"],
            last_activity=data["last_activity"],
            messages=[Message.from_dict(m) for m in data.get("messages", [])],
            context=data.get("context", {})
        )


class SessionManager:
    """
    Production-grade session manager with:
    1. Redis-backed persistence
    2. Automatic session expiration
    3. Multi-turn conversation history
    4. Context accumulation
    """
    
    def __init__(self):
        self.redis_host = os.getenv("REDIS_HOST", "localhost")
        self.redis_port = int(os.getenv("REDIS_PORT", "6379"))
        self.session_ttl = int(os.getenv("SESSION_TTL_HOURS", "24")) * 3600
        self.max_messages = int(os.getenv("SESSION_MAX_MESSAGES", "50"))
        
        self.prefix = "ind_diplomat:session:"
        self._client = None
        self._connected = False
        
        # In-memory fallback
        self._memory_store: Dict[str, Session] = {}
        
        self._connect()
    
    def _connect(self):
        """Connects to Redis."""
        if not REDIS_AVAILABLE:
            print("[Session] Redis not available, using in-memory storage")
            return
        
        try:
            self._client = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                decode_responses=True,
                socket_timeout=5
            )
            self._client.ping()
            self._connected = True
            print(f"[Session] Connected to Redis for session storage")
        except Exception as e:
            print(f"[Session] Redis connection failed: {e}")
            self._connected = False
    
    def create_session(self, user_id: str, initial_context: Dict = None) -> Session:
        """Creates a new conversation session."""
        now = datetime.utcnow().isoformat() + "Z"
        
        session = Session(
            session_id=str(uuid.uuid4()),
            user_id=user_id,
            created_at=now,
            last_activity=now,
            messages=[],
            context=initial_context or {}
        )
        
        self._save_session(session)
        return session
    
    def get_session(self, session_id: str) -> Optional[Session]:
        """Retrieves a session by ID."""
        if self._connected:
            try:
                key = f"{self.prefix}{session_id}"
                data = self._client.get(key)
                if data:
                    return Session.from_dict(json.loads(data))
            except Exception as e:
                print(f"[Session] Get error: {e}")
        
        # Fallback to memory
        return self._memory_store.get(session_id)
    
    def _save_session(self, session: Session):
        """Saves session to storage."""
        if self._connected:
            try:
                key = f"{self.prefix}{session.session_id}"
                self._client.setex(key, self.session_ttl, json.dumps(session.to_dict()))
                return
            except Exception as e:
                print(f"[Session] Save error: {e}")
        
        # Fallback to memory
        self._memory_store[session.session_id] = session
    
    def add_message(self, session_id: str, role: str, content: str, metadata: Dict = None) -> bool:
        """Adds a message to session history."""
        session = self.get_session(session_id)
        if not session:
            return False
        
        message = Message(
            role=role,
            content=content,
            timestamp=datetime.utcnow().isoformat() + "Z",
            metadata=metadata
        )
        
        session.messages.append(message)
        session.last_activity = datetime.utcnow().isoformat() + "Z"
        
        # Trim old messages if exceeding limit
        if len(session.messages) > self.max_messages:
            session.messages = session.messages[-self.max_messages:]
        
        self._save_session(session)
        return True
    
    def get_conversation_history(self, session_id: str, last_n: int = 10) -> List[Dict]:
        """Gets recent conversation history for context."""
        session = self.get_session(session_id)
        if not session:
            return []
        
        messages = session.messages[-last_n:]
        return [{"role": m.role, "content": m.content} for m in messages]
    
    def update_context(self, session_id: str, key: str, value: Any) -> bool:
        """Updates session context."""
        session = self.get_session(session_id)
        if not session:
            return False
        
        session.context[key] = value
        self._save_session(session)
        return True
    
    def get_context(self, session_id: str) -> Dict[str, Any]:
        """Gets session context."""
        session = self.get_session(session_id)
        return session.context if session else {}
    
    def delete_session(self, session_id: str) -> bool:
        """Deletes a session."""
        if self._connected:
            try:
                key = f"{self.prefix}{session_id}"
                self._client.delete(key)
            except Exception as e:
                print(f"[Session] Delete error: {e}")
        
        if session_id in self._memory_store:
            del self._memory_store[session_id]
        return True
    
    def get_user_sessions(self, user_id: str) -> List[str]:
        """Gets all session IDs for a user."""
        sessions = []
        
        if self._connected:
            try:
                for key in self._client.scan_iter(f"{self.prefix}*"):
                    data = self._client.get(key)
                    if data:
                        session = json.loads(data)
                        if session.get("user_id") == user_id:
                            sessions.append(session["session_id"])
            except Exception:
                pass
        
        # Check memory store
        for sid, session in self._memory_store.items():
            if session.user_id == user_id and sid not in sessions:
                sessions.append(sid)
        
        return sessions


# Singleton instance
session_manager = SessionManager()
