from dip.core.Config.config import config
"""
War Gaming Scenario Engine (Layer 8)
====================================
Simulates the global downstream effects of a hypothetical geopolitical action.
"""

import os
import json
import logging
from typing import List

try:
    import litellm
except ImportError:
    litellm = None

from dotenv import load_dotenv
from dip.core.json_utils import strip_markdown_json
from dip.core.schema import StateContext, Signal, WargameAction, WargameResult
from dip.pipeline.world_model.state.conflict_state_model import compute_domain_indices, compute_escalation
from dip.pipeline.world_model.state.belief_accumulator import evaluate
from dip.pipeline.memory.global_state.causal_graph import CausalGraph
from dip.pipeline.forecasting.wargaming.simulation_engine import run_simulation

load_dotenv()
logger = logging.getLogger("Layer8.scenario_engine")
LLM_MODEL = config.LLM_MODEL


async def translate_action_to_signals(action: WargameAction) -> List[Signal]:
    """Uses LLM to translate a natural language policy action into mathematical signals."""
    if not litellm:
        logger.error("LiteLLM not installed. Cannot translate action.")
        return []

    prompt = (
        f"You are a geopolitical war gaming engine. Translate this hypothetical action into structured signals.\n"
        f"Action: '{action.description}'\n"
        f"Target Country (if any): {action.target_country}\n\n"
        "Return a JSON array of signals. Each signal must have:\n"
        "  - 'entity': The actor country (e.g., 'IND').\n"
        "  - 'action': A canonical code (e.g., SIG_MIL_ESCALATION, SIG_ECONOMIC_PRESSURE, SIG_DIP_HOSTILITY, SIG_DIPLOMACY_ACTIVE, SIG_AID_COOPERATION).\n"
        "  - 'target': The target country.\n"
        "  - 'intensity': Float 0.0 to 1.0 representing severity/impact.\n"
    )

    try:
        response = await litellm.acompletion(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=1000
        )
        
        raw = strip_markdown_json(response.choices[0].message.content)
        parsed = json.loads(raw)
        
        extracted_list = []
        if isinstance(parsed, list):
            extracted_list = parsed
        elif isinstance(parsed, dict):
            for v in parsed.values():
                if isinstance(v, list):
                    extracted_list = v
                    break

        signals = []
        for item in extracted_list:
            sig = Signal(
                entity=item.get("entity", "UNKNOWN"),
                action=item.get("action", "SIG_UNKNOWN"),
                target=item.get("target"),
                intensity=float(item.get("intensity", 0.5)),
                confidence=1.0,  # Simulated action is 100% confident
                source_ref="WARGAME_SIM",
                domain="military" if "MIL" in item.get("action", "") else "diplomatic"
            )
            signals.append(sig)
        return signals
    except Exception as e:
        logger.error(f"Failed to translate action: {e}")
        return []


async def synthesize_consequences(action: str, target: str, delta: float, spillovers: dict) -> str:
    """Uses LLM to write a National Security briefing on the simulated consequences."""
    if not litellm:
        return "Consequence synthesis requires LLM."

    prompt = (
        f"Write a War Gaming Consequence Briefing for the Head of State.\n"
        f"Hypothetical Action Taken: {action}\n"
        f"Target: {target}\n"
        f"Direct Escalation Impact: {delta:+.2f}\n"
        f"Global Spillover (Top 3 affected): {str(list(spillovers.items())[:3])}\n\n"
        "Provide a 3-paragraph strategic assessment of what adversaries will likely do next (counter-moves) "
        "and the global economic/military fallout over the next 6 months. Use a formal, objective intelligence tone."
    )

    try:
        response = await litellm.acompletion(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=1000
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Failed to synthesize consequences: {e}")
        return "Synthesis failed."


async def run_wargame(original_context: StateContext, action: WargameAction) -> WargameResult:
    """Runs a full 6-month simulation of a hypothetical geopolitical action."""
    logger.info(f"Running Wargame: {action.description}")
    
    # 1. Translate Action to Signals
    synthetic_signals = await translate_action_to_signals(action)
    
    # 2. Clone State
    try:
        sim_context = original_context.model_copy(deep=True)
    except AttributeError: # pydantic v1 fallback
        sim_context = original_context.copy(deep=True)
        
    sim_context.current_signals.extend(synthetic_signals)
    
    # 3. Recalculate State Logic (Direct Impact)
    # Re-evaluate beliefs with the new 100% confident synthetic signals
    sim_context.beliefs = evaluate(sim_context.current_signals)
    
    # Recompute domains and escalation
    new_domains = compute_domain_indices(sim_context.beliefs, sim_context.current_signals)
    new_escalation = compute_escalation(new_domains, sim_context.temporal_indicators, sim_context.beliefs)
    sim_context.escalation = new_escalation
    
    original_score = original_context.escalation.escalation_score if original_context.escalation else 0.0
    new_score = new_escalation.escalation_score
    escalation_delta = new_score - original_score
    
    # 4. Global Contagion (Simulate 6 months / 12 steps)
    target_country = action.target_country or "UNKNOWN"
    initial_shocks = {target_country: new_score}
    
    # Use the new Graph-Based Causal Analyzer
    graph = CausalGraph()
    spillovers = graph.calculate_spillover(initial_shocks, max_depth=4)
    
    # Filter out the origin country to just show spillovers
    if target_country in spillovers:
        del spillovers[target_country]
        
    # Sort spillovers by magnitude
    sorted_spillovers = dict(sorted(spillovers.items(), key=lambda item: item[1], reverse=True))
    
    # 5. Synthesize Briefing
    briefing = await synthesize_consequences(action.description, target_country, escalation_delta, sorted_spillovers)
    
    # 6. Monte Carlo Simulation
    simulation_outcomes = run_simulation(sim_context)
    
    return WargameResult(
        action=action,
        synthetic_signals=synthetic_signals,
        escalation_delta=escalation_delta,
        global_spillovers=sorted_spillovers,
        consequence_briefing=briefing,
        simulation_outcomes=simulation_outcomes
    )
