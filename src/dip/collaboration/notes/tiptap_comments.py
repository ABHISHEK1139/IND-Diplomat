import logging

logger = logging.getLogger("DIP3.Layer8.TipTapComments")

class TipTapComments:
    """
    Handles rich-text annotations, highlights, and @mentions on evidence and reports.
    """
    def __init__(self):
        pass

    def add_highlight(self, document_id: str, user_id: str, content: str):
        logger.info(f"User {user_id} added highlight to {document_id}")
