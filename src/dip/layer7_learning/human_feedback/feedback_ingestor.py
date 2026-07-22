import logging

logger = logging.getLogger("DIP3.Layer7.FeedbackIngestor")

class FeedbackIngestor:
    """
    Ingests the HITL corrections from Phase 6, scoring Analyst Rating and Source Rating.
    """
    def ingest(self, human_edits):
        logger.info("Ingesting human feedback into the learning loop.")
        return len(human_edits)
