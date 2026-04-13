"""
Signal Mapper Logic.
Translates semantic minister concepts into measurable state context variables.
Prevents false negatives where ministers use synonyms for state metrics.
"""

from typing import Dict, Callable
from engine.Layer3_StateModel.schemas.state_context import StateContext
from engine.Layer4_Analysis.evidence.signal_ontology import canonicalize_signal_token, legacy_aliases_for_signal

def check_mobilization(ctx: StateContext) -> bool:
    return ctx.military.mobilization_level > 0.6 or ctx.capability.troop_mobilization == "active"

def check_troop_movement(ctx: StateContext) -> bool:
    return ctx.military.mobilization_level > 0.4 or ctx.capability.logistics_activity == "high"

def check_clashes(ctx: StateContext) -> bool:
    return ctx.military.clash_history > 0

def check_hostile_rhetoric(ctx: StateContext) -> bool:
    return ctx.diplomatic.hostility_tone > 0.5

def check_diplomatic_breakdown(ctx: StateContext) -> bool:
    return ctx.diplomatic.negotiations < 0.3 or ctx.diplomatic.hostility_tone > 0.8

def check_economic_coercion(ctx: StateContext) -> bool:
    return ctx.economic.sanctions > 0.4 or ctx.economic.economic_pressure > 0.5

def check_logistics(ctx: StateContext) -> bool:
    return ctx.capability.logistics_activity == "high" or ctx.military.exercises > 1

def check_civil_unrest(ctx: StateContext) -> bool:
    return ctx.domestic.unrest > 0.5 or ctx.domestic.protests > 0.4

def check_alliance_activity(ctx: StateContext) -> bool:
    return ctx.diplomatic.alliances > 0.6

# Mapping Table
SIGNAL_MAP: Dict[str, Callable[[StateContext], bool]] = {
    # Canonical token support (lower-cased by matcher)
    "sig_mil_mobilization": check_mobilization,
    "sig_mil_logistics_surge": check_logistics,
    "sig_mil_exercise_escalation": lambda ctx: ctx.military.exercises > 0,
    "sig_mil_forward_deployment": check_mobilization,
    "sig_mil_border_clashes": check_clashes,
    "sig_dip_hostile_rhetoric": check_hostile_rhetoric,
    "sig_dip_channel_open": lambda ctx: ctx.diplomatic.negotiations >= 0.4,
    "sig_dip_channel_closure": check_diplomatic_breakdown,
    "sig_dip_deescalation": lambda ctx: ctx.diplomatic.hostility_tone < 0.4 and ctx.diplomatic.negotiations > 0.3,
    "sig_dip_alliance_coordination": check_alliance_activity,
    "sig_eco_sanctions_active": lambda ctx: ctx.economic.sanctions > 0.1,
    "sig_eco_trade_leverage": lambda ctx: ctx.economic.trade_dependency > 0.6,
    "sig_eco_pressure_high": lambda ctx: ctx.economic.economic_pressure > 0.6,
    "sig_dom_civil_unrest": check_civil_unrest,
    "sig_dom_regime_instability": lambda ctx: ctx.domestic.regime_stability < 0.4,
    "sig_dom_protest_pressure": lambda ctx: ctx.domestic.protests > 0.4,
    "sig_cap_supply_stockpiling": lambda ctx: str(ctx.capability.supply_stockpiling).lower() == "high",
    "sig_cap_cyber_preparation": lambda ctx: str(ctx.capability.cyber_activity).lower() in {"high", "active"},
    "sig_cap_evacuation_activity": lambda ctx: str(ctx.capability.evacuation_activity).lower() in {"high", "active"},
    # Compact ontology support
    "sig_force_concentration": check_mobilization,
    "sig_logistics_surge": check_logistics,
    "sig_exercise_escalation": lambda ctx: ctx.military.exercises >= 2,
    "sig_cyber_preparation": lambda ctx: str(ctx.capability.cyber_activity).lower() in {"high", "active"},
    "sig_dip_hostility": check_hostile_rhetoric,
    "sig_negotiation_breakdown": check_diplomatic_breakdown,
    "sig_alliance_activation": lambda ctx: ctx.diplomatic.alliances >= 0.7,
    "sig_economic_pressure": lambda ctx: ctx.economic.economic_pressure >= 0.5,
    "sig_sanctions_active": lambda ctx: ctx.economic.sanctions >= 0.4,
    "sig_internal_instability": check_civil_unrest,
    "sig_regime_stable": lambda ctx: ctx.domestic.regime_stability >= 0.8,

    # Military
    "military buildup": check_mobilization,
    "troop deployment": check_mobilization,
    "troop movement": check_troop_movement,
    "border clashes": check_clashes,
    "skirmishes": check_clashes,
    "military exercises": lambda ctx: ctx.military.exercises > 0,
    "logistics preparation": check_logistics,
    
    # Diplomatic
    "hostile rhetoric": check_hostile_rhetoric,
    "aggressive statements": check_hostile_rhetoric,
    "diplomatic breakdown": check_diplomatic_breakdown,
    "negotiation failure": check_diplomatic_breakdown,
    "alliance expansion": check_alliance_activity,
    
    # Economic
    "economic coercion": check_economic_coercion,
    "sanctions": lambda ctx: ctx.economic.sanctions > 0.1,
    "trade war": lambda ctx: ctx.economic.trade_dependency > 0.7 and ctx.economic.economic_pressure > 0.4,
    
    # Domestic
    "civil unrest": check_civil_unrest,
    "protests": lambda ctx: ctx.domestic.protests > 0.1,
    "regime instability": lambda ctx: ctx.domestic.regime_stability < 0.4
}

def map_and_check_signal(signal_name: str, ctx: StateContext) -> bool:
    """
    Checks if a semantic signal is present in the state context.
    Matches loosely against keys in the mapping table.
    """
    normalized_signal = str(signal_name or "").lower().strip()

    canonical = canonicalize_signal_token(signal_name)
    if canonical:
        canonical_key = canonical.lower()
        if canonical_key in SIGNAL_MAP:
            return SIGNAL_MAP[canonical_key](ctx)
        for alias in legacy_aliases_for_signal(canonical):
            alias_key = alias.lower().strip()
            if alias_key in SIGNAL_MAP and SIGNAL_MAP[alias_key](ctx):
                return True
    
    # Direct match
    if normalized_signal in SIGNAL_MAP:
        return SIGNAL_MAP[normalized_signal](ctx)
        
    # Partial match (e.g. "reports of border clashes" -> "border clashes")
    for key, check_func in SIGNAL_MAP.items():
        if key in normalized_signal:
            return check_func(ctx)
            
    return False
