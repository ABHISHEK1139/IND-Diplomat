"""
Council Debate Orchestrator
===========================
Orchestrates a debate between dynamic experts when their hypotheses
conflict. Leverages tracer.acompletion for robust synthesis.
"""

import logging
import json
from typing import List

from dip.core.Config.config import config
from dip.telemetry.llm_tracer import tracer
from dip.pipeline.world_model.world.world_model import WorldModel
from dip.pipeline.deliberation.reasoning.dynamic_experts import DynamicExpert
from dip.core.schema import MinisterHypothesisOutput
from dip.core.json_utils import strip_markdown_json, safe_parse_json

logger = logging.getLogger("Layer4.CouncilDebate")


class CouncilDebate:
    """
    Manages disagreements between experts, forcing them to find consensus
    or articulate irreconcilable uncertainty based on the World Model.
    """

    def __init__(self):
        self.model = config.LLM_MODEL

    async def resolve_conflicts(
        self, 
        world_model: WorldModel, 
        topic: str, 
        experts: List[DynamicExpert], 
        hypotheses: List[MinisterHypothesisOutput]
    ) -> MinisterHypothesisOutput:
        """
        Takes conflicting hypotheses and synthesizes a unified consensus assessment.
        """
        logger.info("Resolving hypothesis conflicts via Council Arbiter.")
        
        # Format the debate context
        debate_context = f"Topic: {topic}\n\n"
        for i, hyp in enumerate(hypotheses):
            minister = getattr(hyp, "minister", f"Expert_{i+1}")
            conf = getattr(hyp, "confidence", 0.5)
            rationale = getattr(hyp, "rationale", "")
            preds = ", ".join(getattr(hyp, "predicted_signals", []))
            debate_context += f"Expert {i+1} ({minister}):\n"
            debate_context += f"- Confidence: {conf}\n"
            debate_context += f"- Rationale: {rationale}\n"
            debate_context += f"- Predicted: {preds}\n\n"

        prompt = (
            "You are the Senior Council Arbiter for IND-Diplomat.\n"
            f"Topic: {topic}\n\n"
            f"Expert Hypotheses:\n{debate_context}\n"
            "Your task is to reconcile these conflicting assessments into an objective, unified consensus.\n"
            "Respond in strict JSON:\n"
            "{\n"
            '  "predicted_signals": ["signal_1", "signal_2"],\n'
            '  "matched_signals": ["matched_1"],\n'
            '  "missing_signals": ["missing_1"],\n'
            '  "confidence": 0.0 to 1.0,\n'
            '  "rationale": "Comprehensive consensus reconciling the differing perspectives."\n'
            "}"
        )

        try:
            response = await tracer.acompletion(
                layer="Layer4_DebateArbiter",
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            content = strip_markdown_json(response.choices[0].message.content)
            data = json.loads(content)

            raw_conf = data.get("confidence", 0.5)
            try:
                conf = float(raw_conf) if raw_conf is not None else 0.5
            except (ValueError, TypeError):
                conf = 0.5
            conf = max(0.0, min(1.0, conf))

            pred = data.get("predicted_signals", [])
            if isinstance(pred, str):
                pred = [s.strip() for s in pred.split(",") if s.strip()]
            matched = data.get("matched_signals", [])
            if isinstance(matched, str):
                matched = [s.strip() for s in matched.split(",") if s.strip()]
            missing = data.get("missing_signals", [])
            if isinstance(missing, str):
                missing = [s.strip() for s in missing.split(",") if s.strip()]

            return MinisterHypothesisOutput(
                minister="Council Arbiter",
                predicted_signals=pred,
                matched_signals=matched,
                missing_signals=missing,
                confidence=conf,
                rationale=data.get("rationale", "Synthesized consensus.")
            )

        except Exception as e:
            logger.warning(f"Council Debate synthesis failed: {e}. Falling back to highest confidence hypothesis.")
            best = max(hypotheses, key=lambda h: getattr(h, "confidence", 0.0) or 0.0)
            return MinisterHypothesisOutput(
                minister="Council Arbiter (Consensus)",
                confidence=best.confidence,
                predicted_signals=best.predicted_signals,
                matched_signals=best.matched_signals,
                missing_signals=best.missing_signals,
                rationale=f"Reconciled consensus based on highest-confidence evidence: {best.rationale}"
            )
