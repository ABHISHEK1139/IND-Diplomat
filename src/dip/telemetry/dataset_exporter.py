import json
import os
from pathlib import Path
from dip.core.schema import Investigation

class DatasetExporter:
    """
    Exports an Investigation's reasoning traces and HITL feedback into a JSONL training dataset.
    """
    def __init__(self, output_dir: str = "data/datasets"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def export_sft(self, investigation: Investigation):
        """Exports traces for Supervised Fine-Tuning (SFT)."""
        filename = self.output_dir / f"{investigation.investigation_id}_sft.jsonl"
        with open(filename, "w", encoding="utf-8") as f:
            for trace in investigation.reasoning_traces:
                record = {
                    "instruction": trace.prompt,
                    "context": trace.context,
                    "response": trace.output,
                    "layer": trace.layer
                }
                f.write(json.dumps(record) + "\n")
        return str(filename)
        
    def export_dpo(self, investigation: Investigation):
        """Exports Human-in-the-Loop corrections for Direct Preference Optimization (DPO)."""
        filename = self.output_dir / f"{investigation.investigation_id}_dpo.jsonl"
        master_file = self.output_dir / "dpo_pairs.jsonl"
        
        with open(filename, "w", encoding="utf-8") as f, open(master_file, "a", encoding="utf-8") as mf:
            for feedback in investigation.human_feedback:
                if feedback.action_taken in ["Edited", "Rejected"]:
                    record = {
                        "prompt": f"Layer: {feedback.layer}",
                        "chosen": feedback.corrected_data,
                        "rejected": feedback.original_data,
                        "rationale": feedback.human_rationale
                    }
                    line = json.dumps(record)
                    f.write(line + "\n")
                    mf.write(line + "\n")
        return str(filename)

