import logging
import os
from typing import Optional

try:
    from keycloak import KeycloakOpenID
except ImportError:
    KeycloakOpenID = None

logger = logging.getLogger("DIP3.Layer10.Auth")

class KeycloakAuthenticator:
    """
    Keycloak OpenID integration for SSO.
    """
    def __init__(
        self,
        server_url: str = "http://localhost:8080/auth/",
        client_id: str = "dip-client",
        realm_name: str = "dip-realm",
        client_secret_key: Optional[str] = None,
    ):
        if not KeycloakOpenID:
            logger.warning("python-keycloak not installed; SSO authentication is unavailable.")
            self.keycloak_openid = None
            return

        client_secret_key = client_secret_key or os.getenv("KEYCLOAK_CLIENT_SECRET")
        if not client_secret_key:
            raise ValueError("KEYCLOAK_CLIENT_SECRET is required when Keycloak authentication is enabled")

        self.keycloak_openid = KeycloakOpenID(
            server_url=server_url,
            client_id=client_id,
            realm_name=realm_name,
            client_secret_key=client_secret_key,
            verify=True
        )

    def verify_token(self, token: str) -> dict:
        if not self.keycloak_openid:
            logger.warning("Keycloak is unavailable; refusing token verification.")
            return {"active": False}
            
        try:
            return self.keycloak_openid.introspect(token)
        except Exception as e:
            logger.error(f"Token verification failed: {e}")
            return {"active": False}
