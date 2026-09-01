import logging
import json
from dip.core.json_utils import strip_markdown_json, safe_parse_json
import copy
from typing import List, Dict, Any, Optional
try:
    import litellm
except ImportError:
    litellm = None

from dip.telemetry.llm_tracer import tracer

from dip.core.schema import StateContext, Signal
from dip.core.Config.config import config

logger = logging.getLogger("Layer4.CounterfactualEngine")

class CounterfactualEngine:
    """
    Evaluates "What if?" scenarios by cloning the world model and projecting outcomes.
    """
    def __init__(self):
        self.model = config.LLM_MODEL

    async def evaluate_what_if(self, state: StateContext, what_if_query: str) -> StateContext:
        """
        Takes the current StateContext, applies a hypothetical counterfactual,
        and returns a projected new StateContext with synthetic signals.
        """
        logger.info(f"Evaluating counterfactual: {what_if_query}")
        
        if not litellm:
            logger.error("litellm not available. Returning original state.")
            return state

        # 1. Clone the state
        projected_state = copy.deepcopy(state)
        
        # 2. Ask LLM how this counterfactual changes the signals
        prompt = (
            f"We are analyzing the intelligence state for: {state.country}\n"
            f"The user has posed a counterfactual: '{what_if_query}'\n\n"
            "Generate 1 to 3 synthetic 'Signals' that would immediately result if this counterfactual occurred.\n"
            "Each signal must have:\n"
            "  - 'entity': Actor ISO-3\n"
            "  - 'action': Event code (e.g. SIG_MIL_ESCALATION, SIG_ECONOMIC_SHOCK)\n"
            "  - 'target': Target ISO-3 or null\n"
            "  - 'intensity': 0.0 to 1.0\n"
            "Output ONLY a JSON list of these synthetic signals."
        )

        try:
            response = await tracer.acompletion(
                layer="Layer4_Counterfactual",
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content
            
            content = strip_markdown_json(content)
                
            parsed = json.loads(content)
            synthetic_list = []
            
            if isinstance(parsed, list):
                synthetic_list = parsed
            elif isinstance(parsed, dict):
                for v in parsed.values():
                    if isinstance(v, list):
                        synthetic_list = v
                        break
                        
            # 3. Inject synthetic signals into the cloned state
            for item in synthetic_list:
                sig = Signal(
                    entity=item.get("entity", "UNKNOWN"),
                    action=item.get("action", "SIG_UNKNOWN"),
                    target=item.get("target"),
                    intensity=float(item.get("intensity", 0.8)),
                    confidence=1.0, # It's a hypothetical certainty
                    source_ref="COUNTERFACTUAL_ENGINE"
                )
                projected_state.current_signals.append(sig)
                
            logger.info(f"Injected {len(synthetic_list)} synthetic signals for counterfactual.")
            return projected_state
            
        except Exception as e:
            logger.error(f"Counterfactual Engine failed: {e}")
            return projected_state
