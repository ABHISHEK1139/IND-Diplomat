"""
Hypothesis Expansion Engine
============================

Converts abstract intelligence signals into concrete, observable
real-world indicators.

    SIG_MIL_ESCALATION  →  ["troop deployment", "missile test", ...]

This is the bridge between "what the system WANTS to know" and
"what MoltBot should SEARCH FOR".

Without this module, the investigation loop searches:
    "Iran SIG_FORCE_POSTURE"  ← returns nothing useful

With this module, the investigation loop searches:
    "Iran naval deployment"
    "Iran border troop movement"
    "Iran military aircraft surge"
    ← returns real articles with extractable observations

Design:
    - HYPOTHESIS_LIBRARY is a curated, static dictionary.
    - expand_signal() returns observables for a signal.
    - expand_for_country() appends country context.
    - No LLM, no AI — pure domain knowledge.
"""

from __future__ import annotations

import logging
from typing import Dict, List

logger = logging.getLogger("Layer4_Analysis.hypothesis.hypothesis_expander")


# =====================================================================
# Observable Evidence Library
# =====================================================================
# Each signal maps to real-world phenomena that, if detected, would
# constitute evidence for or against that signal.  These are the
# "footprints" an intelligence collector would look for.

HYPOTHESIS_LIBRARY: Dict[str, List[str]] = {

    # ── CAPABILITY dimension ──────────────────────────────────────

    "SIG_MIL_ESCALATION": [
        "troop deployment",
        "military convoy",
        "reserve mobilization",
        "airbase activation",
        "missile test",
        "artillery movement",
        "military exercise cancelled leave",
        "emergency military orders",
        "arms shipment delivery",
        "air defense activation",
    ],

    "SIG_FORCE_POSTURE": [
        "naval deployment",
        "border troop movement",
        "tank transport",
        "military aircraft surge",
        "defense readiness alert",
        "military drill border",
        "forward operating base",
        "reconnaissance flight",
    ],

    "SIG_MIL_MOBILIZATION": [
        "military mobilization",
        "reserve call-up",
        "conscription order",
        "emergency draft",
        "military personnel recall",
    ],

    "SIG_LOGISTICS_PREP": [
        "military supply convoy",
        "ammunition depot movement",
        "fuel stockpiling military",
        "field hospital deployment",
        "military logistics buildup",
    ],

    "SIG_LOGISTICS_SURGE": [
        "military cargo flights",
        "emergency supply shipment",
        "port military loading",
        "rail military transport surge",
    ],

    "SIG_WMD_RISK": [
        "uranium enrichment increase",
        "nuclear facility activity",
        "IAEA inspection blocked",
        "chemical weapons precursor",
        "biological weapons research",
        "nuclear test preparation",
    ],

    "SIG_CYBER_ACTIVITY": [
        "power grid cyber attack",
        "banking system outage",
        "government website defaced",
        "telecom disruption",
        "malware campaign",
        "cyber espionage operation",
        "critical infrastructure hack",
        "SCADA attack",
    ],

    "SIG_CYBER_PREPARATION": [
        "cyber unit formation",
        "APT group activity increase",
        "zero day exploit stockpiling",
        "cyber weapons test",
    ],

    # ── INTENT dimension ──────────────────────────────────────────

    "SIG_DIP_HOSTILITY": [
        "ambassador recalled",
        "diplomatic expulsion",
        "embassy closure",
        "diplomatic protest",
        "severed diplomatic relations",
        "hostile diplomatic statement",
    ],

    "SIG_DIP_HOSTILE_RHETORIC": [
        "war threat statement",
        "ultimatum issued",
        "red line warning",
        "military threat speech",
        "annihilation rhetoric",
    ],

    "SIG_DIPLOMACY_ACTIVE": [
        "diplomatic summit",
        "peace talks scheduled",
        "mediation effort",
        "ceasefire negotiation",
        "diplomatic channel opened",
    ],

    "SIG_NEGOTIATION_BREAKDOWN": [
        "talks collapsed",
        "negotiation failed",
        "peace process suspended",
        "agreement rejected",
        "walkout talks",
    ],

    "SIG_ALLIANCE_ACTIVATION": [
        "mutual defense invoked",
        "joint military exercise",
        "coalition formed",
        "defense pact activated",
        "military alliance meeting",
    ],

    "SIG_ALLIANCE_SHIFT": [
        "new military partnership",
        "alliance withdrawal",
        "defense cooperation cancelled",
        "realignment strategic partner",
        "arms deal new partner",
    ],

    "SIG_COERCIVE_PRESSURE": [
        "coercive economic measure",
        "sanctions pressure",
        "economic blockade",
        "hostage taking diplomatic",
        "extraterritorial sanction",
        "economic coercion",
    ],

    "SIG_COERCIVE_BARGAINING": [
        "ultimatum deadline",
        "conditional threat",
        "compellence strategy",
        "escalation threat bargaining",
    ],

    "SIG_RETALIATORY_THREAT": [
        "retaliation warning",
        "counter-strike threat",
        "proportional response warning",
        "revenge attack threat",
    ],

    "SIG_DETERRENCE_SIGNALING": [
        "show of force military",
        "carrier group deployment",
        "nuclear posture review",
        "missile defense activation",
        "strategic bomber flight",
    ],

    "SIG_DECEPTION_ACTIVITY": [
        "disinformation campaign",
        "military deception exercise",
        "false flag operation",
        "propaganda offensive",
        "information warfare campaign",
    ],

    # ── STABILITY dimension ───────────────────────────────────────

    "SIG_INTERNAL_INSTABILITY": [
        "protests",
        "riots",
        "security crackdown",
        "mass arrests",
        "state of emergency",
        "political crisis",
        "government resignation",
        "coup rumors",
    ],

    "SIG_INTERNAL_UNREST": [
        "civil unrest",
        "strike action",
        "anti-government demonstration",
        "police violence protesters",
        "internet shutdown",
    ],

    "SIG_DOM_INTERNAL_INSTABILITY": [
        "domestic political crisis",
        "ruling party split",
        "military coup attempt",
        "constitutional crisis",
        "leadership succession crisis",
    ],

    # ── COST dimension ────────────────────────────────────────────

    "SIG_ECO_SANCTIONS_ACTIVE": [
        "sanctions enforcement",
        "OFAC designation",
        "asset freeze",
        "trade embargo imposed",
        "financial sanctions compliance",
    ],

    "SIG_SANCTIONS_ACTIVE": [
        "sanctions list update",
        "sanctions evasion crackdown",
        "secondary sanctions imposed",
        "sanctions waiver expired",
    ],

    "SIG_ECO_PRESSURE_HIGH": [
        "currency collapse",
        "GDP contraction",
        "hyperinflation",
        "oil revenue decline",
        "economic recession",
    ],

    "SIG_ECON_PRESSURE": [
        "economic pressure",
        "trade deficit increase",
        "foreign investment withdrawal",
        "credit rating downgrade",
        "fiscal crisis",
    ],

    "SIG_ECONOMIC_PRESSURE": [
        "economic strain",
        "budget deficit increase",
        "unemployment surge",
        "inflation acceleration",
        "debt crisis",
    ],

    "SIG_ECO_DEPENDENCY": [
        "trade dependency",
        "single export reliance",
        "energy import dependence",
        "supply chain vulnerability",
    ],

    "SIG_TRADE_DISRUPTION": [
        "trade route blocked",
        "shipping disruption",
        "port closure",
        "supply chain breakdown",
        "import ban imposed",
    ],

    "SIG_LEGAL_VIOLATION": [
        "treaty violation",
        "UNSCR breach",
        "international court ruling",
        "war crimes accusation",
        "arms embargo violation",
    ],
}


# =====================================================================
# Public API
# =====================================================================

def expand_signal(signal_code: str) -> List[str]:
    """
    Return real-world observable indicators for a missing signal.

    Parameters
    ----------
    signal_code : str
        Canonical signal code (e.g. "SIG_MIL_ESCALATION").

    Returns
    -------
    list[str]
        Observable phenomena to search for.
        Empty list if signal has no expansion defined.
    """
    return list(HYPOTHESIS_LIBRARY.get(signal_code.upper(), []))


def expand_for_country(signal_code: str, country: str) -> List[str]:
    """
    Return country-contextualized search queries.

    Combines each observable with the country name for
    directed web search.

    Parameters
    ----------
    signal_code : str
        Canonical signal code.
    country : str
        Country name or code (e.g. "Iran", "IRN").

    Returns
    -------
    list[str]
        Queries like "Iran troop deployment", "Iran missile test".
    """
    observables = expand_signal(signal_code)
    if not observables:
        return []
    country = country.strip()
    if not country:
        return observables
    return [f"{country} {obs}" for obs in observables]


def expand_multiple(signal_codes: List[str]) -> Dict[str, List[str]]:
    """
    Expand multiple signals at once.

    Returns
    -------
    dict
        signal_code → list of observables.
        Signals with no expansion are included as empty lists.
    """
    return {sig: expand_signal(sig) for sig in signal_codes}


def coverage_report() -> Dict[str, int]:
    """
    Report how many observables each signal has.

    Useful for diagnosing gaps in the hypothesis library.
    """
    return {sig: len(obs) for sig, obs in HYPOTHESIS_LIBRARY.items()}
