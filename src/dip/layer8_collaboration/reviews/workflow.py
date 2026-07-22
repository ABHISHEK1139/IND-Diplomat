import logging

logger = logging.getLogger("DIP3.Layer8.ReviewWorkflow")

class ReviewWorkflow:
    """
    Manages the Draft -> Analyst Review -> Senior Review -> Approved pipeline.
    """
    def __init__(self):
        pass

    def transition_state(self, document_id: str, new_state: str):
        logger.info(f"Document {document_id} transitioned to {new_state}")
