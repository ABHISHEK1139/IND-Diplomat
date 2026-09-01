"""
Working Memory (Layer 3)
========================
Persists the short-term StateContext across runs so the system is aware 
of what it briefed the Executive on previously.
"""

import json
import os
import logging
from typing import List, Optional
from datetime import datetime, timezone
from dip.core.schema import StateContext

logger = logging.getLogger("Layer3.working_memory")
MEMORY_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "working_memory.json")


class WorkingMemory:
    def __init__(self, capacity: int = 5):
        self.capacity = capacity
        self._ensure_dir()
        
    def _ensure_dir(self):
        os.makedirs(os.path.dirname(MEMORY_FILE), exist_ok=True)
        if not os.path.exists(MEMORY_FILE):
            with open(MEMORY_FILE, 'w') as f:
                json.dump([], f)
                
    def save_context(self, context: StateContext):
        """Save a context to the working memory buffer."""
        try:
            with open(MEMORY_FILE, 'r') as f:
                history = json.load(f)
        except Exception:
            history = []
            
        # Add timestamp and dump
        dump = context.model_dump() if hasattr(context, "model_dump") else context.dict()
        dump["_saved_at"] = datetime.now(timezone.utc).isoformat()
        
        history.append(dump)
        if len(history) > self.capacity:
            history = history[-self.capacity:]
            
        with open(MEMORY_FILE, 'w') as f:
            json.dump(history, f, indent=2)
            
    def get_last_context(self, country: str) -> Optional[StateContext]:
        """Retrieve the last context saved for a specific country."""
        try:
            with open(MEMORY_FILE, 'r') as f:
                history = json.load(f)
        except Exception:
            return None
            
        # Search backwards
        for dump in reversed(history):
            if dump.get("country") == country:
                # Remove meta field before loading
                dump.pop("_saved_at", None)
                return StateContext(**dump)
                
        return None

    def compare_escalation(self, current_context: StateContext) -> float:
        """Returns the delta between the current escalation and the last one."""
        last = self.get_last_context(current_context.country)
        if not last or not last.escalation or not current_context.escalation:
            return 0.0
            
        return current_context.escalation.escalation_score - last.escalation.escalation_score
