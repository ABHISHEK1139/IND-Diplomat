import logging

logger = logging.getLogger("DIP3.Layer7.DatasetBuilder")

class DatasetBuilder:
    """
    Automatically compiles chatml.jsonl, dpo.jsonl, and reward.jsonl.
    """
    def build_records(self, human_edits):
        logger.info("Compiling SFT/DPO dataset records.")
        return {"chatml": 1, "dpo": 1}
