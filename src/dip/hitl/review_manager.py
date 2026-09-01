import json
import logging
import uuid
import os
from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel

from dip.core.schema import HITLFeedback
from dip.pipeline.memory.core.investigation_memory import InvestigationMemory

logger = logging.getLogger("Layer11.HITL")

class ReviewManager:
    """
    Human-in-the-Loop review manager. Pauses pipeline execution to request human validation.
    Generates DPO/RLHF feedback based on edits.
    """
    def __init__(self, investigation_id: str):
        self.investigation_id = investigation_id
        self.memory = InvestigationMemory()
        self.hitl_enabled = os.getenv("HITL_MODE", "0") == "1"

    def checkpoint(self, layer_name: str, data: Any) -> Any:
        """
        Pauses the execution and asks the user to review the data.
        If HITL_MODE is off, passes data through untouched.
        """
        if not self.hitl_enabled:
            return data

        print(f"\n" + "="*50)
        print(f"🛑 HITL CHECKPOINT: {layer_name}")
        print("="*50)
        
        # Serialize for display
        if isinstance(data, BaseModel):
            original_json = data.model_dump_json(indent=2)
        elif isinstance(data, list) and all(isinstance(x, BaseModel) for x in data):
            original_json = json.dumps([x.model_dump() for x in data], indent=2)
        else:
            original_json = json.dumps(data, default=str, indent=2)
            
        print("Data for review:")
        print(original_json)
        print("\nOptions: [a]pprove, [r]eject, [e]dit")
        
        choice = input("Enter choice (a/r/e): ").strip().lower()
        
        action_taken = "Approved"
        corrected_json = original_json
        rationale = ""
        
        if choice == 'r':
            action_taken = "Rejected"
            rationale = input("Reason for rejection: ")
            print(f"[{layer_name}] Rejected by Human.")
            
        elif choice == 'e':
            action_taken = "Edited"
            print("Enter your corrected JSON (single line for simplicity or press Enter to skip):")
            edited = input("> ").strip()
            if edited:
                corrected_json = edited
            rationale = input("Reason for edit: ")
            print(f"[{layer_name}] Edited by Human.")
            
        else:
            print(f"[{layer_name}] Approved by Human.")
            
        # Record feedback
        feedback = HITLFeedback(
            feedback_id=f"FB-{uuid.uuid4().hex[:6].upper()}",
            layer=layer_name,
            original_data=original_json,
            corrected_data=corrected_json,
            action_taken=action_taken,
            human_rationale=rationale,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        
        inv = self.memory.get_investigation(self.investigation_id)
        if inv:
            inv.human_feedback.append(feedback)
            self.memory.save_investigation(inv)
            
        # Return the corrected data if possible
        if action_taken == "Edited" and corrected_json != original_json:
            try:
                parsed = json.loads(corrected_json)
                if isinstance(data, BaseModel):
                    return data.__class__.model_validate(parsed)
                elif isinstance(data, list) and len(data) > 0 and isinstance(data[0], BaseModel):
                    cls = data[0].__class__
                    return [cls.model_validate(x) for x in parsed]
                return parsed
            except Exception as e:
                logger.error(f"Failed to parse edited JSON: {e}")
                print("Falling back to original data due to parse error.")
                return data

        return data
