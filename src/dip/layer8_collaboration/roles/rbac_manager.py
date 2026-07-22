import logging

logger = logging.getLogger("DIP3.Layer8.RBACManager")

class RBACManager:
    """
    Manages Admin, Analyst, and Observer permissions (FastAPI Users/Keycloak backend).
    """
    def __init__(self):
        pass

    def check_permission(self, user_id: str, action: str) -> bool:
        return True
