"""
Dynamic Experts
================
Spawns specialized analytical experts (agents) at runtime based on the
investigation domain. Experts query the World Model rather than raw text.
"""

import logging
import json
from typing import List, Any, Optional

from dip.core.Config.config import config
from dip.telemetry.llm_tracer import tracer
from dip.pipeline.world_model.world.world_model import WorldModel
from dip.core.schema import MinisterHypothesisOutput
from dip.core.json_utils import strip_markdown_json, safe_parse_json

try:
    import dspy
except ImportError:
    dspy = None

logger = logging.getLogger("Layer4.DynamicExperts")


class DynamicExpert:
    """
    An expert spawned at runtime based on the investigation domain.
    Queries the World Model for context.
    """
    def __init__(self, role: str, expertise: str):
        self.role = role
        self.expertise = expertise
        self.model = config.LLM_MODEL

    async def analyze(
        self, 
        world_model: WorldModel, 
        topic: str, 
        heuristic_baseline: List[Any] = None
    ) -> MinisterHypothesisOutput:
        """Analyze the current state from the perspective of this expert using the World Model."""
        beliefs = world_model.get_beliefs_about(topic, max_hops=2)

        # Build context from graph
        graph_context = "Knowledge Graph Beliefs:\n"
        if heuristic_baseline:
            graph_context += "HEURISTIC BASELINE (Deterministic Guardrails):\n"
            for h in heuristic_baseline:
                if getattr(h, "source", "") == "Heuristic":
                    graph_context += f"- [{getattr(h, 'minister', 'Minister')}] CONF:{getattr(h, 'confidence', 0)} SIGNALS:{getattr(h, 'predicted_signals', [])}\n"
            graph_context += "\n"
        if not beliefs:
            graph_context += "None found.\n"
        else:
            for b in beliefs[:50]:  # Limit context size
                graph_context += f"- {b.get('head')} [{b.get('type')}] {b.get('tail')}\n"

        prompt = (
            f"You are the {self.role} specializing in {self.expertise}.\n"
            f"Topic under investigation: {topic}\n\n"
            f"{graph_context}\n\n"
            "Analyze the situation strictly from your professional domain perspective.\n"
            "Respond in strict JSON format:\n"
            "{\n"
            '  "predicted_signals": ["signal_1", "signal_2"],\n'
            '  "matched_signals": ["matched_signal"],\n'
            '  "missing_signals": ["missing_signal"],\n'
            '  "confidence": 0.0 to 1.0,\n'
            '  "rationale": "Detailed explanation of your domain analysis."\n'
            "}"
        )

        try:
            response = await tracer.acompletion(
                layer="Layer4_DynamicExpert",
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
                minister=self.role,
                predicted_signals=pred,
                matched_signals=matched,
                missing_signals=missing,
                confidence=conf,
                rationale=data.get("rationale", f"Analysis conducted by {self.role}.")
            )
        except Exception as e:
            logger.error(f"{self.role} analysis fallback failed: {e}")
            return MinisterHypothesisOutput(
                minister=self.role,
                predicted_signals=[f"{self.role.lower().replace(' ', '_')}_active"],
                matched_signals=[],
                missing_signals=[],
                confidence=0.5,
                rationale=f"Analysis by {self.role} (heuristic fallback due to: {e})"
            )


class DynamicExpertSpawner:
    """
    Spawns appropriate experts based on investigation domains.
    """
    def __init__(self):
        self.model = config.LLM_MODEL

    async def spawn_experts(
        self, 
        topic: str, 
        domains: List[str], 
        heuristic_baseline: List[Any] = None
    ) -> List[DynamicExpert]:
        """Spawn expert agents dynamically based on topic and heuristic gaps."""
        baseline_str = ""
        if heuristic_baseline:
            baseline_str = "Existing Minister Hypotheses (Baseline):\n"
            for h in heuristic_baseline:
                baseline_str += f"- {getattr(h, 'minister', 'Minister')}: {getattr(h, 'rationale', '')} (Conf: {getattr(h, 'confidence', 0)})\n"

        prompt = (
            f"Topic: '{topic}'\n"
            f"Domains Available: {', '.join(domains)}\n"
            f"{baseline_str}\n"
            "Identify 3 distinct expert roles needed to analyze this issue properly.\n"
            "Respond in strict JSON with a list of expert objects:\n"
            "[\n"
            '  {"role": "Strategic Economist", "expertise": "Sanctions and currency vulnerability"},\n'
            '  {"role": "Maritime Intelligence Analyst", "expertise": "Naval choke point blockades"}\n'
            "]"
        )

        try:
            response = await tracer.acompletion(
                layer="Layer4_ExpertSpawner",
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            content = strip_markdown_json(response.choices[0].message.content)
            parsed = safe_parse_json(content)

            # Robust unpacking of various LLM JSON shapes
            if isinstance(parsed, list):
                expert_list = parsed
            elif isinstance(parsed, dict):
                for key in ("experts", "roles", "expert_list", "data", "analysts"):
                    if isinstance(parsed.get(key), list):
                        expert_list = parsed[key]
                        break
                else:
                    if "role" in parsed:
                        expert_list = [parsed]
                    else:
                        expert_list = list(parsed.values())
            else:
                expert_list = []

            experts = []
            for item in expert_list[:4]:
                if isinstance(item, dict):
                    role = item.get("role", "General Analyst")
                    expertise = item.get("expertise", "Geopolitical Analysis")
                elif isinstance(item, str):
                    role = item
                    expertise = "Domain Analysis"
                else:
                    continue
                experts.append(DynamicExpert(role, expertise))

            if not experts:
                raise ValueError("No experts parsed from model response")

            logger.info(f"Spawned {len(experts)} experts: {[e.role for e in experts]}")
            return experts

        except Exception as e:
            logger.warning(f"Failed to spawn experts dynamically: {e}. Falling back to standard experts.")
            return [
                DynamicExpert("Strategic Analyst", "Geopolitics and defense strategy"),
                DynamicExpert("Economic Intelligence Analyst", "Trade and sanctions resilience"),
                DynamicExpert("Diplomatic Observer", "Negotiation and multilateral alignments")
            ]
