import logging
import os
from pathlib import Path
from typing import Optional

try:
    import casbin
except ImportError:
    casbin = None

logger = logging.getLogger("DIP3.Layer10.RBAC")

class CasbinRBAC:
    """
    Casbin enforcement for multi-tenant dossier access.
    """
    def __init__(self, model_path: Optional[str] = None, policy_path: Optional[str] = None):
        model_path = model_path or os.getenv("CASBIN_MODEL_PATH")
        policy_path = policy_path or os.getenv("CASBIN_POLICY_PATH")
        if not casbin:
            logger.warning("casbin not installed; RBAC will deny access.")
            self.enforcer = None
            return

        if not model_path or not policy_path:
            logger.error("Casbin model and policy paths are required; RBAC will deny access.")
            self.enforcer = None
            return
        if not Path(model_path).is_file() or not Path(policy_path).is_file():
            logger.error("Casbin model or policy file is missing; RBAC will deny access.")
            self.enforcer = None
            return

        self.enforcer = casbin.Enforcer(model_path, policy_path)

    def can_access(self, sub: str, obj: str, act: str) -> bool:
        if not self.enforcer:
            return False
        return bool(self.enforcer.enforce(sub, obj, act))
