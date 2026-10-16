import logging
import os
from collections import OrderedDict
from typing import Dict, Any, Optional

try:
    import y_py as Y
except ImportError:
    Y = None

logger = logging.getLogger("DIP3.Layer8.YjsSync")

#: Max live YDoc instances. ``document_id`` comes straight from the
#: ``/ws/collab/{document_id}`` path segment, so without a cap an attacker
#: (or a buggy client) can grow this dict forever.
MAX_DOCUMENTS = int(os.getenv("DIP_YJS_MAX_DOCS", "100"))


class YjsSyncEngine:
    """
    Real-time CRDT sync for multi-user document editing.
    Manages in-memory YDoc instances for active collaborative sessions.
    """
    def __init__(self):
        # Maps document_id -> Y.YDoc, most-recently-used last (LRU eviction).
        self.documents: "OrderedDict[str, Any]" = OrderedDict()

    def get_document(self, document_id: str):
        if not Y:
            logger.warning("y-py is not installed. CRDT sync disabled.")
            return None

        doc = self.documents.get(document_id)
        if doc is None:
            doc = Y.YDoc()
            self.documents[document_id] = doc
            while len(self.documents) > MAX_DOCUMENTS:
                evicted, _ = self.documents.popitem(last=False)
                logger.info(f"Evicted idle YDoc for {evicted} (LRU cap {MAX_DOCUMENTS})")
        else:
            self.documents.move_to_end(document_id)

        return doc

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
