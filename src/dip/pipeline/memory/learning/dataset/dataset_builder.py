"""
DIP 3.0 Dataset Builder — Phase 7 Learning Loop.
Compiles Supervised Fine-Tuning (SFT) and Direct Preference Optimization (DPO) datasets
from reasoning traces, ministerial debate critiques, and Human-in-the-Loop (HITL) analyst corrections.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("DIP3.Layer7.DatasetBuilder")


class DatasetBuilder:
    """
    Compiles standard JSONL datasets for fine-tuning and alignment:
      - dpo_pairs.jsonl: Direct Preference Optimization pairs (prompt, chosen, rejected)
      - sft_chatml.jsonl: ChatML formatted supervised training examples
      - reward_ratings.jsonl: Scored outputs for reward modeling
    """

    def __init__(self, output_dir: str = "data/datasets"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.dpo_file = self.output_dir / "dpo_pairs.jsonl"
        self.sft_file = self.output_dir / "sft_chatml.jsonl"
        self.reward_file = self.output_dir / "reward_ratings.jsonl"

    def build_records(self, human_edits: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Convert human edits and corrections into SFT and DPO records.
        """
        logger.info(f"Compiling SFT/DPO dataset records from {len(human_edits)} edits.")
        dpo_count = 0
        sft_count = 0

        for edit in human_edits:
            prompt = edit.get("prompt") or f"Layer: {edit.get('layer', 'reasoning')}"
            original = edit.get("original_data") or edit.get("rejected")
            corrected = edit.get("corrected_data") or edit.get("chosen")
            rationale = edit.get("human_rationale") or edit.get("rationale", "")

            if corrected:
                # SFT Record
                sft_record = {
                    "messages": [
                        {"role": "system", "content": "You are POLITIQ AI Strategic Intelligence Analyst."},
                        {"role": "user", "content": prompt},
                        {"role": "assistant", "content": corrected if isinstance(corrected, str) else json.dumps(corrected)},
                    ],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                with open(self.sft_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(sft_record) + "\n")
                sft_count += 1

                # DPO Record (if original/rejected is present)
                if original and original != corrected:
                    dpo_record = {
                        "prompt": prompt,
                        "chosen": corrected if isinstance(corrected, str) else json.dumps(corrected),
                        "rejected": original if isinstance(original, str) else json.dumps(original),
                        "rationale": rationale,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                    with open(self.dpo_file, "a", encoding="utf-8") as f:
                        f.write(json.dumps(dpo_record) + "\n")
                    dpo_count += 1

        logger.info(f"Dataset build complete: {sft_count} SFT records, {dpo_count} DPO pairs.")
        return {"sft": sft_count, "dpo": dpo_count}

    def compile_from_investigation(
        self,
        investigation_id: str,
        query: str,
        council_session: Any,
        human_feedback: Optional[List[Any]] = None,
    ) -> Dict[str, int]:
        """
        Extract preference pairs from ministerial debate rounds and HITL corrections.
        """
        records: List[Dict[str, Any]] = []

        # 1. Process explicit human corrections
        if human_feedback:
            for fb in human_feedback:
                if getattr(fb, "action_taken", "") in ["Edited", "Rejected"]:
                    records.append({
                        "prompt": f"Assess strategic threat and policy options for query: {query}",
                        "original_data": getattr(fb, "original_data", ""),
                        "corrected_data": getattr(fb, "corrected_data", ""),
                        "human_rationale": getattr(fb, "human_rationale", ""),
                        "layer": getattr(fb, "layer", "HITL_CORRECTION"),
                    })

        # 2. Extract ministerial consensus vs contrarian dissent pairs
        if hasattr(council_session, "hypotheses") and council_session.hypotheses:
            consensus_hyps = [
                h for h in council_session.hypotheses
                if getattr(h, "confidence", 0.0) >= 0.60
            ]
            if consensus_hyps:
                top_hyp = max(consensus_hyps, key=lambda h: getattr(h, "confidence", 0.0))
                minister_name = getattr(top_hyp, "minister", "Security Minister")
                
                chosen_text = (
                    f"[{minister_name}] Assessed confidence: {top_hyp.confidence:.2f}\n"
                    f"Corroborated Signals: {', '.join(top_hyp.matched_signals or ['Grounded intelligence verified'])}\n"
                    f"Rationale: {getattr(top_hyp, 'rationale', 'Hypothesis verified against StateContext.')}"
                )
                
                # Uncalibrated baseline
                rejected_text = (
                    f"[{minister_name}] Assessed confidence: 0.20\n"
                    "Uncertain assessment with no specific signal grounding."
                )

                records.append({
                    "prompt": f"Ministerial hypothesis evaluation for {getattr(council_session.state_context, 'country', 'target')}: {top_hyp.hypothesis_type}",
                    "original_data": rejected_text,
                    "corrected_data": chosen_text,
                    "human_rationale": "Prioritize signal-grounded, calibrated ministerial analysis.",
                    "layer": "MINISTERIAL_DELIBERATION",
                })

        return self.build_records(records)

    def get_dataset_stats(self) -> Dict[str, Any]:
        """Return line counts and file sizes of the generated datasets."""
        dpo_lines = sum(1 for _ in open(self.dpo_file, "r", encoding="utf-8")) if self.dpo_file.exists() else 0
        sft_lines = sum(1 for _ in open(self.sft_file, "r", encoding="utf-8")) if self.sft_file.exists() else 0
        return {
            "dpo_pairs_count": dpo_lines,
            "sft_records_count": sft_lines,
            "dpo_file_path": str(self.dpo_file),
            "sft_file_path": str(self.sft_file),
        }
