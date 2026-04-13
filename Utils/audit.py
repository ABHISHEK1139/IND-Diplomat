"""
Audit Trail for IND-Diplomat
Provides tamper-evident logging to PostgreSQL.
"""

import os
import json
import hashlib
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
import uuid

try:
    import asyncpg
    ASYNCPG_AVAILABLE = True
except ImportError:
    ASYNCPG_AVAILABLE = False
    print("[Audit] Warning: asyncpg not installed. Using in-memory audit trail.")


@dataclass
class AuditEntry:
    """Represents an audit log entry."""
    id: str
    timestamp: str
    user_id: str
    action: str
    resource: str
    details: Dict[str, Any]
    ip_address: str
    user_agent: str
    request_id: str
    response_status: int
    hash: str = None
    previous_hash: str = None


class AuditTrail:
    """
    Production-grade audit trail with:
    1. PostgreSQL persistence
    2. Hash chain for tamper detection
    3. Query and analysis capabilities
    4. In-memory fallback
    """
    
    def __init__(self):
        self.db_url = os.getenv("AUDIT_DB_URL", "postgresql://localhost:5432/ind_diplomat_audit")
        self._pool = None
        self._connected = False
        self._last_hash = "genesis"
        
        # In-memory fallback
        self._memory_store: List[AuditEntry] = []
    
    async def connect(self):
        """Connects to PostgreSQL."""
        if not ASYNCPG_AVAILABLE:
            print("[Audit] Using in-memory audit trail")
            return
        
        try:
            self._pool = await asyncpg.create_pool(self.db_url, min_size=2, max_size=10)
            await self._init_schema()
            self._connected = True
            print("[Audit] Connected to PostgreSQL audit database")
        except Exception as e:
            print(f"[Audit] Database connection failed: {e}")
            self._connected = False
    
    async def _init_schema(self):
        """Initializes the audit table schema."""
        if not self._connected:
            return
        
        async with self._pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id VARCHAR(36) PRIMARY KEY,
                    timestamp TIMESTAMPTZ NOT NULL,
                    user_id VARCHAR(100),
                    action VARCHAR(100) NOT NULL,
                    resource VARCHAR(255),
                    details JSONB,
                    ip_address VARCHAR(45),
                    user_agent TEXT,
                    request_id VARCHAR(36),
                    response_status INTEGER,
                    hash VARCHAR(64) NOT NULL,
                    previous_hash VARCHAR(64)
                );
                
                CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);
                CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_id);
                CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action);
            """)
    
    def _compute_hash(self, entry: AuditEntry, previous_hash: str) -> str:
        """Computes hash for tamper detection."""
        content = json.dumps({
            "id": entry.id,
            "timestamp": entry.timestamp,
            "user_id": entry.user_id,
            "action": entry.action,
            "resource": entry.resource,
            "details": entry.details,
            "previous_hash": previous_hash
        }, sort_keys=True)
        
        return hashlib.sha256(content.encode()).hexdigest()
    
    async def log(
        self,
        user_id: str,
        action: str,
        resource: str = None,
        details: Dict[str, Any] = None,
        ip_address: str = None,
        user_agent: str = None,
        request_id: str = None,
        response_status: int = 200
    ) -> AuditEntry:
        """Logs an audit entry."""
        entry = AuditEntry(
            id=str(uuid.uuid4()),
            timestamp=datetime.utcnow().isoformat() + "Z",
            user_id=user_id,
            action=action,
            resource=resource or "",
            details=details or {},
            ip_address=ip_address or "",
            user_agent=user_agent or "",
            request_id=request_id or str(uuid.uuid4()),
            response_status=response_status
        )
        
        # Compute hash chain
        entry.previous_hash = self._last_hash
        entry.hash = self._compute_hash(entry, self._last_hash)
        self._last_hash = entry.hash
        
        # Persist
        if self._connected:
            await self._persist_entry(entry)
        else:
            self._memory_store.append(entry)
        
        return entry
    
    async def _persist_entry(self, entry: AuditEntry):
        """Persists entry to PostgreSQL."""
        async with self._pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO audit_log (
                    id, timestamp, user_id, action, resource, details,
                    ip_address, user_agent, request_id, response_status, hash, previous_hash
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            """,
                entry.id,
                datetime.fromisoformat(entry.timestamp.replace("Z", "+00:00")),
                entry.user_id,
                entry.action,
                entry.resource,
                json.dumps(entry.details),
                entry.ip_address,
                entry.user_agent,
                entry.request_id,
                entry.response_status,
                entry.hash,
                entry.previous_hash
            )
    
    async def query(
        self,
        user_id: str = None,
        action: str = None,
        start_date: str = None,
        end_date: str = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Queries audit log."""
        if not self._connected:
            # Filter in-memory store
            results = self._memory_store
            if user_id:
                results = [e for e in results if e.user_id == user_id]
            if action:
                results = [e for e in results if e.action == action]
            return [asdict(e) for e in results[-limit:]]
        
        # Build query
        conditions = []
        params = []
        
        if user_id:
            conditions.append(f"user_id = ${len(params) + 1}")
            params.append(user_id)
        if action:
            conditions.append(f"action = ${len(params) + 1}")
            params.append(action)
        if start_date:
            conditions.append(f"timestamp >= ${len(params) + 1}")
            params.append(datetime.fromisoformat(start_date))
        if end_date:
            conditions.append(f"timestamp <= ${len(params) + 1}")
            params.append(datetime.fromisoformat(end_date))
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(f"""
                SELECT * FROM audit_log
                WHERE {where_clause}
                ORDER BY timestamp DESC
                LIMIT {limit}
            """, *params)
            
            return [dict(row) for row in rows]
    
    async def verify_chain(self, entries: List[Dict] = None) -> Dict[str, Any]:
        """Verifies the hash chain integrity."""
        if entries is None:
            if self._connected:
                entries = await self.query(limit=1000)
            else:
                entries = [asdict(e) for e in self._memory_store]
        
        if not entries:
            return {"valid": True, "checked": 0}
        
        # Sort by timestamp
        entries.sort(key=lambda x: x.get("timestamp", ""))
        
        valid = True
        broken_at = None
        
        for i, entry in enumerate(entries):
            if i == 0:
                continue
            
            expected_prev = entries[i - 1].get("hash")
            actual_prev = entry.get("previous_hash")
            
            if expected_prev != actual_prev:
                valid = False
                broken_at = entry.get("id")
                break
        
        return {
            "valid": valid,
            "checked": len(entries),
            "broken_at": broken_at
        }


# Singleton instance
audit_trail = AuditTrail()
