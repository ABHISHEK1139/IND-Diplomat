"""
Reasoning Trace
===============
Logs the complete provenance graph of the decision.
World Model -> Experts -> Debates -> Evidence -> Consensus.
"""

import logging
import json
from datetime import datetime, timezone
from typing import Dict, Any

logger = logging.getLogger("Layer4.ReasoningTrace")


class ReasoningTrace:
    def __init__(self):
        self.trace_log = []

    def record_step(self, step_name: str, data: Dict[str, Any]):
        """Records a step in the reasoning pipeline."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "step": step_name,
            "data": data
        }
        self.trace_log.append(entry)
        logger.debug(f"Trace recorded: {step_name}")

    def export_trace(self, filepath: str):
        """Saves the complete provenance to disk."""
        try:
            with open(filepath, 'w') as f:
                json.dump(self.trace_log, f, indent=2)
            logger.info(f"Reasoning trace exported to {filepath}")
        except Exception as e:
            logger.error(f"Failed to export trace: {e}")
