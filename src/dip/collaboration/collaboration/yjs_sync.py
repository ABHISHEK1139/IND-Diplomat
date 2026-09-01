import logging
from typing import Dict, Any, Optional

try:
    import y_py as Y
except ImportError:
    Y = None

logger = logging.getLogger("DIP3.Layer8.YjsSync")

class YjsSyncEngine:
    """
    Real-time CRDT sync for multi-user document editing.
    Manages in-memory YDoc instances for active collaborative sessions.
    """
    def __init__(self):
        # Maps document_id -> Y.YDoc
        self.documents: Dict[str, Any] = {}
        
    def get_document(self, document_id: str):
        if not Y:
            logger.warning("y-py is not installed. CRDT sync disabled.")
            return None
            
        if document_id not in self.documents:
            self.documents[document_id] = Y.YDoc()
            logger.info(f"Initialized new YDoc for {document_id}")
            
        return self.documents[document_id]

    def apply_update(self, document_id: str, update: bytes) -> None:
        """
        Applies a binary update from a client to the server's YDoc.
        """
        doc = self.get_document(document_id)
        if doc:
            Y.apply_update(doc, update)
            logger.debug(f"Applied Yjs update to {document_id}")

    def encode_state_vector(self, document_id: str) -> Optional[bytes]:
        """
        Returns the state vector of the document, useful for clients to compute missing differences.
        """
        doc = self.get_document(document_id)
        if doc:
            return Y.encode_state_vector(doc)
        return None

    def encode_state_as_update(self, document_id: str, state_vector: Optional[bytes] = None) -> Optional[bytes]:
        """
        Returns the document state encoded as an update binary. 
        If state_vector is provided, returns only the differences.
        """
        doc = self.get_document(document_id)
        if doc:
            if state_vector:
                return Y.encode_state_as_update(doc, state_vector)
            return Y.encode_state_as_update(doc)
        return None

# Global instance to manage active sessions across websocket connections
yjs_engine = YjsSyncEngine()
