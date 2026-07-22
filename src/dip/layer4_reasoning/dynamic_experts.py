"""
Dynamic Experts
================
Spawns specialized analytical experts (agents) at runtime based on the
investigation domain. Experts query the World Model rather than raw text.
"""

import logging
import json
from dip.core.json_utils import strip_markdown_json, safe_parse_json
from typing import List, Any

from dip.Config.config import config
from dip.layer10_telemetry.llm_tracer import tracer
from dip.layer3_world_model.world_model import WorldModel
from dip.core.schema import MinisterHypothesisOutput
from dip.layer4_reasoning.dspy_signatures import ExpertAnalysis

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

    async def analyze(self, world_model: WorldModel, topic: str, heuristic_baseline: List[Any] = None) -> MinisterHypothesisOutput:
        """Analyze the current state from the perspective of this expert using the World Model."""
        # Query World Model instead of raw context
        beliefs = world_model.get_beliefs_about(topic, max_hops=2)
        timeline = world_model.get_timeline(topic)

        # Build context from graph
        graph_context = "Knowledge Graph Beliefs:\n"
        if heuristic_baseline:
            graph_context += "HEURISTIC BASELINE (Deterministic Guardrails):\n"
            for h in heuristic_baseline:
                if getattr(h, "source", "") == "Heuristic":
                    graph_context += f"- [{h.minister}] CONF:{getattr(h, 'confidence', 0)} SIGNALS:{getattr(h, 'predicted_signals', [])}\n"
            graph_context += "\n"
        if not beliefs:
            graph_context += "None found.\n"
        else:
            for b in beliefs[:50]: # Limit context size
                graph_context += f"- {b.get('head')} [{b.get('type')}] {b.get('tail')}\n"

        if not dspy:
            logger.error("dspy not found. Cannot run expert analysis.")
            return MinisterHypothesisOutput(minister=self.role, rationale="Error: dspy not installed.")
            
        try:
            # We configure DSPy's LM temporarily if not global. Assuming global configuration elsewhere, 
            # but we'll use Predict directly.
            predictor = dspy.Predict(ExpertAnalysis)
            
            # Using synchronous predict for now as DSPy async support varies by version
            result = predictor(
                topic=topic,
                expert_role=f"{self.role} - {self.expertise}",
                graph_context=graph_context
            )
            
            try:
                conf = float(result.confidence)
            except (ValueError, TypeError):
                conf = 0.5
                
            return MinisterHypothesisOutput(
                minister=self.role,
                predicted_signals=[s.strip() for s in result.predicted_signals.split(',')],
                matched_signals=[s.strip() for s in result.matched_signals.split(',')],
                missing_signals=[s.strip() for s in result.missing_signals.split(',')],
                confidence=conf,
                rationale=result.rationale
            )
            
        except Exception as e:
            logger.error(f"{self.role} failed to analyze: {e}")
            return MinisterHypothesisOutput(minister=self.role, rationale=f"Error: {e}")


class DynamicExpertSpawner:
    """
    Spawns appropriate experts based on investigation domains.
    Uses Tier 3 Frontier Models (e.g. GPT-5.5 API).
    """
    def __init__(self):
        self.model = config.LLM_MODEL

    async def spawn_experts(self, topic: str, domains: List[str], heuristic_baseline: List[Any] = None) -> List[DynamicExpert]:
        """Ask the LLM to determine the best experts for this investigation."""
        logger.info(f"Spawning dynamic experts for domains: {domains}")
        
        baseline_str = ""
        if heuristic_baseline:
            baseline_str = "\nBaseline Heuristic Assessments (For Context):\n" + "\n".join([f"- {h.minister}: Conf {getattr(h, 'confidence', 0)}" for h in heuristic_baseline if getattr(h, 'source', '') == 'Heuristic'])

        prompt = (
            f"We are conducting a strategic intelligence investigation on: {topic}\n"
            f"The primary domains are: {', '.join(domains)}\n"
            f"{baseline_str}\n"
            "Identify 3 distinct expert roles needed to analyze this issue properly.\n"
            "Output ONLY a JSON list of objects, where each object has 'role' and 'expertise'.\n"
            "[\n"
            "  {\"role\": \"Economist\", \"expertise\": \"Macro-economic stability\"}\n"
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
            content = response.choices[0].message.content
            content = strip_markdown_json(content)
                
            parsed = json.loads(content)
            expert_list = parsed if isinstance(parsed, list) else list(parsed.values())[0]
                        
            experts = []
            for item in expert_list[:4]: 
                role = item.get("role", "General Analyst")
                expertise = item.get("expertise", "Geopolitics")
                experts.append(DynamicExpert(role, expertise))
                
            logger.info(f"Spawned {len(experts)} experts: {[e.role for e in experts]}")
            return experts
            
        except Exception as e:
            logger.error(f"Failed to spawn experts: {e}. Falling back.")
            return [
                DynamicExpert("Strategic Analyst", "Geopolitics and strategy"),
                DynamicExpert("Domain Expert", "Core topic fundamentals")
            ]
