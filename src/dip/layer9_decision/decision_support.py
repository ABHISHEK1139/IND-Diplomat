import logging
import json
from dip.core.json_utils import strip_markdown_json, safe_parse_json
import uuid
from typing import List, Dict, Any
try:
    import litellm
except ImportError:
    litellm = None

from dip.core.schema import StateContext, ScenarioTree, DecisionOption
from dip.Config.config import config
from dip.layer10_telemetry.llm_tracer import tracer

logger = logging.getLogger("Layer9.DecisionSupport")

class DecisionSupportEngine:
    """
    Layer 9: Transforms the World Model and Scenario Tree into actionable policy/decision options.
    """
    
    def __init__(self):
        self.model = config.LLM_MODEL

    async def generate_options(self, state: StateContext, tree: ScenarioTree) -> List[DecisionOption]:
        logger.info("Generating Decision Options based on state and scenarios.")
        
        if not litellm:
            logger.error("litellm not available. Returning default options.")
            return [
                DecisionOption(
                    option_id="OPT-DEFAULT",
                    title="Monitor Situation",
                    description="Maintain current intelligence collection and wait for more data.",
                    cost="Low",
                    risk_level="Low",
                    probability_of_success=1.0,
                    expected_outcome="Status quo maintained."
                )
            ]

        prompt = (
            f"You are the Director of Intelligence advising a top-level decision maker regarding {state.country}.\n"
            f"We have identified the following forecast trajectory:\n"
            f"Base: {tree.base_trajectory}\n"
            f"Most Likely Scenario: {[n.description for n in tree.nodes if n.scenario_type == 'Most Likely']}\n\n"
            "Given this intelligence, generate 3 distinct Decision Options for policymakers.\n"
            "Each option must have a title, description, a list of pros, a list of cons, cost (Low/Med/High), risk_level (Low/Med/High), probability_of_success (float 0.0-1.0), and an expected_outcome.\n\n"
            "Return ONLY a JSON list of objects matching this schema:\n"
            "[\n"
            "  {\n"
            "    \"title\": \"string\",\n"
            "    \"description\": \"string\",\n"
            "    \"pros\": [\"string\"],\n"
            "    \"cons\": [\"string\"],\n"
            "    \"cost\": \"string\",\n"
            "    \"risk_level\": \"string\",\n"
            "    \"probability_of_success\": 0.75,\n"
            "    \"expected_outcome\": \"string\"\n"
            "  }\n"
            "]"
        )

        try:
            response = await tracer.acompletion(
                layer="Layer9_DecisionSupport",
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.4,
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content
            
            content = strip_markdown_json(content)
                
            parsed = json.loads(content)
            options_list = []
            
            if isinstance(parsed, list):
                options_list = parsed
            elif isinstance(parsed, dict):
                for v in parsed.values():
                    if isinstance(v, list):
                        options_list = v
                        break
                        
            results = []
            for item in options_list:
                results.append(DecisionOption(
                    option_id=f"OPT-{uuid.uuid4().hex[:6].upper()}",
                    title=item.get("title", "Unknown Option"),
                    description=item.get("description", "No description provided."),
                    pros=item.get("pros", []),
                    cons=item.get("cons", []),
                    cost=item.get("cost", "Unknown"),
                    risk_level=item.get("risk_level", "Unknown"),
                    probability_of_success=float(item.get("probability_of_success", 0.5)),
                    expected_outcome=item.get("expected_outcome", "Unknown")
                ))
                
            logger.info(f"Generated {len(results)} Decision Options.")
            return results
            
        except Exception as e:
            logger.error(f"Decision Support Engine failed: {e}")
            return []
