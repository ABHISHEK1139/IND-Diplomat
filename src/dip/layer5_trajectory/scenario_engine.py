import logging
import json
from dip.core.json_utils import strip_markdown_json, safe_parse_json
from typing import List, Dict, Any
try:
    import litellm
except ImportError:
    litellm = None

from dip.core.schema import StateContext, ScenarioTree, ScenarioNode
from dip.Config.config import config
from dip.layer10_telemetry.llm_tracer import tracer

logger = logging.getLogger("Layer5.ScenarioEngine")

class ScenarioEngine:
    """
    Layer 5: Projects a ScenarioTree based on the current World Model state.
    Generates Best Case, Most Likely, Worst Case, and Black Swan branches.
    """
    
    def __init__(self):
        self.model = config.LLM_MODEL

    async def generate_scenarios(self, state: StateContext) -> ScenarioTree:
        logger.info(f"Generating Scenario Tree for {state.country}")
        
        if not litellm:
            logger.error("litellm not available. Returning default tree.")
            return ScenarioTree(
                base_trajectory="Unknown",
                nodes=[
                    ScenarioNode(scenario_type="Most Likely", description="Status Quo", probability=1.0)
                ]
            )

        prompt = (
            f"You are a strategic forecaster. Analyze the current state for {state.country}.\n"
            f"Number of signals: {len(state.current_signals)}\n"
            f"Number of beliefs: {len(state.beliefs)}\n\n"
            "Generate a scenario tree detailing 4 possible future trajectories:\n"
            "1. 'Most Likely'\n"
            "2. 'Best Case'\n"
            "3. 'Worst Case'\n"
            "4. 'Black Swan'\n\n"
            "Return ONLY a JSON object matching this schema:\n"
            "{\n"
            "  \"base_trajectory\": \"string (Current overall direction)\",\n"
            "  \"nodes\": [\n"
            "    {\n"
            "      \"scenario_type\": \"Most Likely\",\n"
            "      \"description\": \"Detailed description of the projected outcome.\",\n"
            "      \"probability\": 0.60,\n"
            "      \"trigger_events\": [\"event 1\", \"event 2\"]\n"
            "    }\n"
            "  ]\n"
            "}"
        )

        try:
            response = await tracer.acompletion(
                layer="Layer5_ScenarioEngine",
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.4,
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content
            
            content = strip_markdown_json(content)
                
            data = json.loads(content)
            
            nodes = []
            for n in data.get("nodes", []):
                nodes.append(ScenarioNode(
                    scenario_type=n.get("scenario_type", "Unknown"),
                    description=n.get("description", "Unknown"),
                    probability=float(n.get("probability", 0.0)),
                    trigger_events=n.get("trigger_events", [])
                ))
                
            tree = ScenarioTree(
                base_trajectory=data.get("base_trajectory", "Unknown"),
                nodes=nodes
            )
            logger.info(f"Successfully generated Scenario Tree with {len(nodes)} nodes.")
            return tree
            
        except Exception as e:
            logger.error(f"Scenario Engine failed: {e}")
            return ScenarioTree(
                base_trajectory="Error computing trajectory",
                nodes=[]
            )
