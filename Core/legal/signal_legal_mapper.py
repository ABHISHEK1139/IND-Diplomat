"""
Core.legal.signal_legal_mapper — Conditional Legal Retrieval Gate
==================================================================

Maps each escalation signal to whether it *requires* legal analysis.
Only signals with legal implications should trigger RAG retrieval —
SIG_FORCE_POSTURE is a military fact, not a legal question.

This module sits **before** RAG retrieval and reduces retrieval budget
to signals that actually need treaty/statute interpretation.

Usage::

    from Core.legal.signal_legal_mapper import filter_legal_signals

    legal_signals = filter_legal_signals(observed_signals)
    # Only pass legal_signals to retrieve_legal_evidence()
"""

from __future__ import annotations

from typing import Dict, Set


# ═══════════════════════════════════════════════════════════════════════
# SIGNAL → LEGAL DOMAIN MAPPING
# ═══════════════════════════════════════════════════════════════════════
# Signals that require legal reasoning are mapped to the legal domain
# they invoke.  Signals NOT in this map are empirical facts that do not
# need treaty interpretation.

LEGAL_REQUIRED: Dict[str, str] = {
    # Use of force / sovereignty
    "SIG_MIL_ESCALATION":           "use_of_force",
    "SIG_ILLEGAL_COERCION":         "use_of_force",
    "SIG_SOVEREIGNTY_BREACH":       "use_of_force",
    "SIG_TERRITORIAL_INCURSION":    "use_of_force",
    "SIG_BORDER_CLASH":             "use_of_force",

    # WMD / nonproliferation
    "SIG_WMD_RISK":                 "nuclear_law",
    "SIG_NUCLEAR_ACTIVITY":         "nuclear_law",

    # Maritime
    "SIG_CHOKEPOINT_CONTROL":       "maritime_law",
    "SIG_BLOCKADE":                 "maritime_law",
    "SIG_MARITIME_VIOLATION":       "maritime_law",

    # Economic coercion / sanctions legality
    "SIG_SANCTIONS_ACTIVE":         "sanctions_law",
    "SIG_ECO_SANCTIONS_ACTIVE":     "sanctions_law",
    "SIG_ECONOMIC_PRESSURE":        "sanctions_law",

    # Diplomatic / treaty obligations
    "SIG_NEGOTIATION_BREAKDOWN":    "treaty_obligations",
    "SIG_DIP_HOSTILITY":            "treaty_obligations",
    "SIG_TREATY_BREAK":             "treaty_obligations",
    "SIG_DIP_BREAK":                "treaty_obligations",

    # Cyber sovereignty
    "SIG_CYBER_ACTIVITY":           "cyber_law",
    "SIG_CYBER_PREPARATION":        "cyber_law",

    # Alliance / collective defense
    "SIG_ALLIANCE_ACTIVATION":      "collective_defense",
    "SIG_ALLIANCE_SHIFT":           "collective_defense",

    # Coercive bargaining
    "SIG_COERCIVE_BARGAINING":      "coercive_diplomacy",
    "SIG_RETALIATORY_THREAT":       "coercive_diplomacy",
    "SIG_DETERRENCE_SIGNALING":     "coercive_diplomacy",

    # Human rights / internal
    "SIG_MILITARY_DEFECTION":       "human_rights",
}

# Signals that do NOT require legal analysis (empirical facts):
# SIG_FORCE_POSTURE, SIG_LOGISTICS_PREP, SIG_ECON_PRESSURE,
# SIG_ECO_PRESSURE_HIGH, SIG_INTERNAL_INSTABILITY,
# SIG_PUBLIC_PROTEST, SIG_ELITE_FRACTURE, SIG_DECEPTION_ACTIVITY,
# SIG_DIPLOMACY_ACTIVE, etc.


def filter_legal_signals(observed_signals: Set[str] | None) -> Set[str]:
    """
    Return only the signals that require legal analysis.

    Parameters
    ----------
    observed_signals : set[str]
        All observed signal codes from the pipeline.

    Returns
    -------
    set[str]
        Subset of signals that need legal/treaty interpretation.
    """
    if not observed_signals:
        return set()
    return {
        sig.strip().upper()
        for sig in observed_signals
        if sig.strip().upper() in LEGAL_REQUIRED
    }


def get_legal_domains(signals: Set[str] | None) -> Set[str]:
    """
    Return the set of legal domains triggered by the given signals.

    Useful for metadata filtering in RAG retrieval.
    """
    if not signals:
        return set()
    return {
        LEGAL_REQUIRED[sig.strip().upper()]
        for sig in signals
        if sig.strip().upper() in LEGAL_REQUIRED
    }
