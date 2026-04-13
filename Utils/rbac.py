"""
Multi-Tenant RBAC & Data Entitlements
Implements Role-Based Access Control for entitlement-aware retrieval.
Ensures sensitive documents are filtered by user clearance level.
"""

from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import hashlib


class ClearanceLevel(Enum):
    """Security clearance levels."""
    PUBLIC = 0
    INTERNAL = 1
    CONFIDENTIAL = 2
    SECRET = 3
    TOP_SECRET = 4
    SCI = 5  # Sensitive Compartmented Information


class Permission(Enum):
    """System permissions."""
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    ADMIN = "admin"
    EXPORT = "export"
    SHARE = "share"
    ANNOTATE = "annotate"


@dataclass
class Role:
    """A role with associated permissions."""
    role_id: str
    name: str
    description: str
    clearance_level: ClearanceLevel
    permissions: Set[Permission]
    jurisdictions: List[str]  # e.g., ["IND", "USA", "EU"]
    document_types: List[str]  # e.g., ["treaty", "memo", "intelligence"]


@dataclass
class User:
    """A user with roles and clearance."""
    user_id: str
    username: str
    email: str
    organization: str
    roles: List[str]  # Role IDs
    clearance_level: ClearanceLevel
    jurisdictions: List[str]
    active: bool
    created_at: datetime
    last_login: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DocumentEntitlement:
    """Entitlement metadata for a document."""
    document_id: str
    classification: ClearanceLevel
    jurisdictions: List[str]
    compartments: List[str]  # SCI compartments
    owner_org: str
    created_at: datetime
    declassify_on: Optional[datetime] = None


class RBACManager:
    """
    Role-Based Access Control Manager.
    
    Implements:
    1. User/Role management
    2. Clearance level enforcement
    3. Jurisdiction-based filtering
    4. Entitlement-aware retrieval
    """
    
    # Default roles
    DEFAULT_ROLES = {
        "analyst": Role(
            role_id="analyst",
            name="Analyst",
            description="Standard analyst with read access",
            clearance_level=ClearanceLevel.CONFIDENTIAL,
            permissions={Permission.READ, Permission.ANNOTATE},
            jurisdictions=["IND"],
            document_types=["treaty", "memo", "news", "report"]
        ),
        "senior_analyst": Role(
            role_id="senior_analyst",
            name="Senior Analyst",
            description="Senior analyst with broader access",
            clearance_level=ClearanceLevel.SECRET,
            permissions={Permission.READ, Permission.WRITE, Permission.ANNOTATE, Permission.SHARE},
            jurisdictions=["IND", "SAARC", "ASEAN"],
            document_types=["treaty", "memo", "news", "report", "assessment"]
        ),
        "director": Role(
            role_id="director",
            name="Director",
            description="Director level with full access",
            clearance_level=ClearanceLevel.TOP_SECRET,
            permissions={Permission.READ, Permission.WRITE, Permission.DELETE, Permission.EXPORT, Permission.SHARE},
            jurisdictions=["*"],  # All jurisdictions
            document_types=["*"]  # All types
        ),
        "admin": Role(
            role_id="admin",
            name="Administrator",
            description="System administrator",
            clearance_level=ClearanceLevel.TOP_SECRET,
            permissions={Permission.ADMIN, Permission.READ, Permission.WRITE, Permission.DELETE},
            jurisdictions=["*"],
            document_types=["*"]
        ),
        "public": Role(
            role_id="public",
            name="Public User",
            description="Public access only",
            clearance_level=ClearanceLevel.PUBLIC,
            permissions={Permission.READ},
            jurisdictions=["*"],
            document_types=["news", "public_treaty"]
        )
    }
    
    def __init__(self):
        self._roles: Dict[str, Role] = self.DEFAULT_ROLES.copy()
        self._users: Dict[str, User] = {}
        self._entitlements: Dict[str, DocumentEntitlement] = {}
        self._audit_log: List[Dict] = []
    
    # ============== Role Management ==============
    
    def create_role(
        self,
        role_id: str,
        name: str,
        description: str,
        clearance: ClearanceLevel,
        permissions: Set[Permission],
        jurisdictions: List[str] = None,
        document_types: List[str] = None
    ) -> Role:
        """Create a new role."""
        role = Role(
            role_id=role_id,
            name=name,
            description=description,
            clearance_level=clearance,
            permissions=permissions,
            jurisdictions=jurisdictions or [],
            document_types=document_types or []
        )
        self._roles[role_id] = role
        return role
    
    def get_role(self, role_id: str) -> Optional[Role]:
        """Get a role by ID."""
        return self._roles.get(role_id)
    
    # ============== User Management ==============
    
    def create_user(
        self,
        username: str,
        email: str,
        organization: str,
        roles: List[str],
        clearance: ClearanceLevel = None
    ) -> User:
        """Create a new user."""
        user_id = hashlib.md5(f"{username}{email}".encode()).hexdigest()[:12]
        
        # Derive clearance from highest role if not specified
        if clearance is None:
            clearance = max(
                (self._roles[r].clearance_level for r in roles if r in self._roles),
                default=ClearanceLevel.PUBLIC
            )
        
        # Aggregate jurisdictions from roles
        jurisdictions = set()
        for role_id in roles:
            if role_id in self._roles:
                jurisdictions.update(self._roles[role_id].jurisdictions)
        
        user = User(
            user_id=user_id,
            username=username,
            email=email,
            organization=organization,
            roles=roles,
            clearance_level=clearance,
            jurisdictions=list(jurisdictions),
            active=True,
            created_at=datetime.now()
        )
        
        self._users[user_id] = user
        self._log_audit("user_created", user_id=user_id, username=username)
        
        return user
    
    def get_user(self, user_id: str) -> Optional[User]:
        """Get a user by ID."""
        return self._users.get(user_id)
    
    def get_user_permissions(self, user_id: str) -> Set[Permission]:
        """Get aggregated permissions for a user."""
        user = self.get_user(user_id)
        if not user:
            return set()
        
        permissions = set()
        for role_id in user.roles:
            if role_id in self._roles:
                permissions.update(self._roles[role_id].permissions)
        
        return permissions
    
    # ============== Entitlement Management ==============
    
    def register_document_entitlement(
        self,
        document_id: str,
        classification: ClearanceLevel,
        jurisdictions: List[str],
        compartments: List[str] = None,
        owner_org: str = None
    ) -> DocumentEntitlement:
        """Register entitlements for a document."""
        entitlement = DocumentEntitlement(
            document_id=document_id,
            classification=classification,
            jurisdictions=jurisdictions,
            compartments=compartments or [],
            owner_org=owner_org or "SYSTEM",
            created_at=datetime.now()
        )
        
        self._entitlements[document_id] = entitlement
        return entitlement
    
    def get_document_entitlement(self, document_id: str) -> Optional[DocumentEntitlement]:
        """Get entitlements for a document."""
        return self._entitlements.get(document_id)
    
    # ============== Access Control ==============
    
    def check_access(
        self,
        user_id: str,
        document_id: str,
        permission: Permission = Permission.READ
    ) -> tuple[bool, str]:
        """
        Check if user has access to a document.
        Returns (allowed, reason).
        """
        user = self.get_user(user_id)
        if not user:
            return False, "User not found"
        
        if not user.active:
            return False, "User account is inactive"
        
        # Check permission
        user_permissions = self.get_user_permissions(user_id)
        if permission not in user_permissions and Permission.ADMIN not in user_permissions:
            return False, f"User lacks {permission.value} permission"
        
        # Check document entitlement
        entitlement = self.get_document_entitlement(document_id)
        if not entitlement:
            # No entitlement = public access
            return True, "Document has no access restrictions"
        
        # Check clearance level
        if user.clearance_level.value < entitlement.classification.value:
            return False, f"Insufficient clearance: {user.clearance_level.name} < {entitlement.classification.name}"
        
        # Check jurisdiction
        if "*" not in user.jurisdictions:
            if not any(j in user.jurisdictions for j in entitlement.jurisdictions):
                return False, f"Jurisdiction mismatch: user has {user.jurisdictions}, document requires {entitlement.jurisdictions}"
        
        self._log_audit("access_granted", user_id=user_id, document_id=document_id)
        return True, "Access granted"
    
    def filter_documents(
        self,
        user_id: str,
        documents: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Filter documents based on user entitlements.
        Used for entitlement-aware retrieval.
        """
        user = self.get_user(user_id)
        if not user:
            return []
        
        filtered = []
        for doc in documents:
            doc_id = doc.get("id") or doc.get("document_id") or str(hash(str(doc)))
            allowed, _ = self.check_access(user_id, doc_id)
            
            if allowed:
                filtered.append(doc)
        
        self._log_audit(
            "documents_filtered",
            user_id=user_id,
            total=len(documents),
            accessible=len(filtered)
        )
        
        return filtered
    
    def get_user_document_filter(self, user_id: str) -> Dict[str, Any]:
        """
        Get filter criteria for retrieval queries.
        Used to pre-filter at the vector store level.
        """
        user = self.get_user(user_id)
        if not user:
            return {"classification": {"$lte": 0}}  # Public only
        
        return {
            "classification": {"$lte": user.clearance_level.value},
            "jurisdictions": {"$in": user.jurisdictions} if "*" not in user.jurisdictions else None
        }
    
    # ============== Audit ==============
    
    def _log_audit(self, action: str, **details):
        """Log an audit event."""
        self._audit_log.append({
            "action": action,
            "timestamp": datetime.now().isoformat(),
            **details
        })
    
    def get_audit_log(
        self,
        user_id: str = None,
        action: str = None,
        limit: int = 100
    ) -> List[Dict]:
        """Get audit log entries."""
        logs = self._audit_log
        
        if user_id:
            logs = [l for l in logs if l.get("user_id") == user_id]
        if action:
            logs = [l for l in logs if l.get("action") == action]
        
        return logs[-limit:]
    
    def get_access_summary(self, user_id: str) -> Dict[str, Any]:
        """Get access summary for a user."""
        user = self.get_user(user_id)
        if not user:
            return {"error": "User not found"}
        
        return {
            "user_id": user_id,
            "username": user.username,
            "organization": user.organization,
            "clearance": user.clearance_level.name,
            "roles": user.roles,
            "permissions": [p.value for p in self.get_user_permissions(user_id)],
            "jurisdictions": user.jurisdictions,
            "active": user.active
        }


# Singleton instance
rbac_manager = RBACManager()


# Middleware for API integration
def require_permission(permission: Permission):
    """Decorator to require a specific permission."""
    def decorator(func):
        def wrapper(user_id: str, *args, **kwargs):
            permissions = rbac_manager.get_user_permissions(user_id)
            if permission not in permissions and Permission.ADMIN not in permissions:
                raise PermissionError(f"User {user_id} lacks {permission.value} permission")
            return func(user_id, *args, **kwargs)
        return wrapper
    return decorator


def entitlement_filter(user_id: str):
    """Context manager for filtered retrieval."""
    class EntitlementContext:
        def __init__(self, user_id):
            self.user_id = user_id
            self.filter = rbac_manager.get_user_document_filter(user_id)
        
        def filter_results(self, documents: List[Dict]) -> List[Dict]:
            return rbac_manager.filter_documents(self.user_id, documents)
    
    return EntitlementContext(user_id)
