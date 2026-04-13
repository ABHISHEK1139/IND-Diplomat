"""
Layer4_Analysis/conflict_state.py — Hybrid Conflict-State Detector
===================================================================
Classifies the **present** conflict state from projected signals.

Architecture:  Hybrid (State Machine + Bayesian Transition Probability)
- State machine provides discrete, actionable classification
- Bayesian priors + signal evidence yield posterior transition P

States (ordered):
  PEACE  →  CRISIS  →  LIMITED_STRIKES  →  ACTIVE_CONFLICT  →  FULL_WAR

This module answers:  "What is happening right now?"
The SRE answers:      "Where is this heading?"

Together they form the dual-state model.

Author: IND-DIPLOMAT system  |  Phase: Conflict State Layer
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("Layer4.conflict_state")

# ══════════════════════════════════════════════════════════════════════
#  CONFLICT STATES
# ══════════════════════════════════════════════════════════════════════

CONFLICT_STATES = ("PEACE", "CRISIS", "LIMITED_STRIKES", "ACTIVE_CONFLICT", "FULL_WAR")

# Index for ordering
_STATE_IDX = {s: i for i, s in enumerate(CONFLICT_STATES)}

# ══════════════════════════════════════════════════════════════════════
#  SIGNAL → STATE EVIDENCE MAPPING
# ══════════════════════════════════════════════════════════════════════
# Each signal contributes evidence toward one or more states.
# Format:  signal_name → list of (state, weight)
# Weight is how strongly that signal's presence (at full confidence)
# supports the given state classification.

_SIGNAL_STATE_EVIDENCE: Dict[str, List[Tuple[str, float]]] = {
    # ── Military signals ──
    "SIG_MIL_ESCALATION": [
        ("CRISIS", 0.3), ("LIMITED_STRIKES", 0.5), ("ACTIVE_CONFLICT", 0.7),
    ],
    "SIG_MIL_MOBILIZATION": [
        ("CRISIS", 0.5), ("LIMITED_STRIKES", 0.3), ("ACTIVE_CONFLICT", 0.4),
    ],
    "SIG_FORCE_POSTURE": [
        ("CRISIS", 0.4), ("LIMITED_STRIKES", 0.3),
    ],
    "SIG_FORCE_CONCENTRATION": [
        ("CRISIS", 0.4), ("LIMITED_STRIKES", 0.4), ("ACTIVE_CONFLICT", 0.3),
    ],
    "SIG_MIL_FORWARD_DEPLOYMENT": [
        ("CRISIS", 0.3), ("LIMITED_STRIKES", 0.4), ("ACTIVE_CONFLICT", 0.5),
    ],
    "SIG_MIL_BORDER_CLASHES": [
        ("LIMITED_STRIKES", 0.6), ("ACTIVE_CONFLICT", 0.5),
    ],
    "SIG_MIL_EXERCISE_ESCALATION": [
        ("CRISIS", 0.4), ("LIMITED_STRIKES", 0.2),
    ],
    "SIG_LOGISTICS_PREP": [
        ("CRISIS", 0.3), ("LIMITED_STRIKES", 0.3), ("ACTIVE_CONFLICT", 0.4),
    ],
    "SIG_LOGISTICS_SURGE": [
        ("CRISIS", 0.3), ("ACTIVE_CONFLICT", 0.5), ("FULL_WAR", 0.3),
    ],

    # ── WMD / Nuclear ──
    "SIG_WMD_RISK": [
        ("CRISIS", 0.5), ("LIMITED_STRIKES", 0.4), ("ACTIVE_CONFLICT", 0.3),
        ("FULL_WAR", 0.2),
    ],

    # ── Diplomatic signals ──
    "SIG_DIP_HOSTILITY": [
        ("CRISIS", 0.5), ("LIMITED_STRIKES", 0.2),
    ],
    "SIG_DIP_HOSTILE_RHETORIC": [
        ("CRISIS", 0.4),
    ],
    "SIG_COERCIVE_BARGAINING": [
        ("CRISIS", 0.4),
    ],
    "SIG_COERCIVE_PRESSURE": [
        ("CRISIS", 0.3),
    ],
    "SIG_NEGOTIATION_BREAKDOWN": [
        ("CRISIS", 0.5), ("LIMITED_STRIKES", 0.3),
    ],
    "SIG_RETALIATORY_THREAT": [
        ("CRISIS", 0.4), ("LIMITED_STRIKES", 0.4),
    ],
    "SIG_ALLIANCE_ACTIVATION": [
        ("CRISIS", 0.3), ("ACTIVE_CONFLICT", 0.3),
    ],

    # ── De-escalation (negative evidence for high states) ──
    "SIG_DIPLOMACY_ACTIVE": [
        ("PEACE", 0.4), ("CRISIS", 0.1),  # slightly supports crisis (talks happen during crises)
    ],
    "SIG_DETERRENCE_SIGNALING": [
        ("CRISIS", 0.3),  # deterrence means crisis, not war
    ],

    # ── Stability / Domestic ──
    "SIG_INTERNAL_INSTABILITY": [
        ("CRISIS", 0.3),
    ],
    "SIG_PUBLIC_PROTEST": [
        ("CRISIS", 0.2),
    ],
    "SIG_ELITE_FRACTURE": [
        ("CRISIS", 0.3),
    ],
    "SIG_MILITARY_DEFECTION": [
        ("ACTIVE_CONFLICT", 0.4), ("FULL_WAR", 0.3),
    ],
    "SIG_DECEPTION_ACTIVITY": [
        ("CRISIS", 0.3), ("LIMITED_STRIKES", 0.3),
    ],

    # ── Economic ──
    "SIG_ECON_PRESSURE": [
        ("CRISIS", 0.2),
    ],
    "SIG_ECONOMIC_PRESSURE": [
        ("CRISIS", 0.2),
    ],
    "SIG_SANCTIONS_ACTIVE": [
        ("CRISIS", 0.2),
    ],

    # ── Cyber ──
    "SIG_CYBER_ACTIVITY": [
        ("CRISIS", 0.3), ("LIMITED_STRIKES", 0.3),
    ],
    "SIG_CYBER_PREPARATION": [
        ("CRISIS", 0.3), ("LIMITED_STRIKES", 0.2),
    ],
}


# ══════════════════════════════════════════════════════════════════════
#  BAYESIAN TRANSITION PRIORS
# ══════════════════════════════════════════════════════════════════════
# Prior probability of being in each state given NO evidence.
# Heavily weighted toward PEACE — most countries most of the time.

_BASE_PRIOR: Dict[str, float] = {
    "PEACE":            0.50,
    "CRISIS":           0.25,
    "LIMITED_STRIKES":  0.12,
    "ACTIVE_CONFLICT":  0.08,
    "FULL_WAR":         0.05,
}

# Country-specific prior overrides (shift priors for countries in
# known crisis/conflict zones)
_COUNTRY_PRIOR_SHIFT: Dict[str, Dict[str, float]] = {
    # Active conflict zones — shift prior away from PEACE
    "IRN": {"PEACE": -0.15, "CRISIS": +0.10, "LIMITED_STRIKES": +0.05},
    "ISR": {"PEACE": -0.20, "CRISIS": +0.05, "LIMITED_STRIKES": +0.10, "ACTIVE_CONFLICT": +0.05},
    "UKR": {"PEACE": -0.30, "CRISIS": -0.05, "LIMITED_STRIKES": +0.05, "ACTIVE_CONFLICT": +0.20, "FULL_WAR": +0.10},
    "RUS": {"PEACE": -0.20, "CRISIS": +0.05, "LIMITED_STRIKES": +0.05, "ACTIVE_CONFLICT": +0.10},
    "SYR": {"PEACE": -0.25, "CRISIS": +0.05, "LIMITED_STRIKES": +0.10, "ACTIVE_CONFLICT": +0.10},
    "YEM": {"PEACE": -0.25, "CRISIS": +0.05, "LIMITED_STRIKES": +0.10, "ACTIVE_CONFLICT": +0.10},
    "MMR": {"PEACE": -0.20, "CRISIS": +0.05, "LIMITED_STRIKES": +0.05, "ACTIVE_CONFLICT": +0.10},
    "SDN": {"PEACE": -0.25, "CRISIS": +0.05, "LIMITED_STRIKES": +0.05, "ACTIVE_CONFLICT": +0.10, "FULL_WAR": +0.05},
    "SOM": {"PEACE": -0.20, "CRISIS": +0.10, "LIMITED_STRIKES": +0.05, "ACTIVE_CONFLICT": +0.05},
    "LBY": {"PEACE": -0.20, "CRISIS": +0.10, "LIMITED_STRIKES": +0.05, "ACTIVE_CONFLICT": +0.05},
    "AFG": {"PEACE": -0.15, "CRISIS": +0.10, "LIMITED_STRIKES": +0.05},
    "PRK": {"PEACE": -0.10, "CRISIS": +0.10},
    "ETH": {"PEACE": -0.15, "CRISIS": +0.10, "LIMITED_STRIKES": +0.05},
    "IRQ": {"PEACE": -0.15, "CRISIS": +0.10, "LIMITED_STRIKES": +0.05},
    "SSD": {"PEACE": -0.20, "CRISIS": +0.05, "LIMITED_STRIKES": +0.05, "ACTIVE_CONFLICT": +0.10},
    "COD": {"PEACE": -0.15, "CRISIS": +0.10, "LIMITED_STRIKES": +0.05},
    "PSE": {"PEACE": -0.25, "CRISIS": +0.05, "LIMITED_STRIKES": +0.10, "ACTIVE_CONFLICT": +0.10},
}


# ══════════════════════════════════════════════════════════════════════
#  STATE TRANSITION CONSTRAINTS (State Machine Rules)
# ══════════════════════════════════════════════════════════════════════
# Minimum signal thresholds to allow classification into each state.
# These are hard gates — even if Bayesian posterior is high, the state
# won't be classified unless these mandatory signal conditions are met.

_STATE_GATE: Dict[str, Dict[str, Any]] = {
    "PEACE": {
        # PEACE requires: no strong military signals
        "max_mil_confidence": 0.30,     # mil signals must be below this
        "max_hostility_confidence": 0.40,
    },
    "CRISIS": {
        "min_total_signals": 2,         # at least 2 active signals
    },
    "LIMITED_STRIKES": {
        "min_mil_confidence": 0.40,     # military signal must be meaningful
        "min_total_signals": 3,
    },
    "ACTIVE_CONFLICT": {
        "min_mil_confidence": 0.60,     # strong military evidence
        "min_mil_signals": 2,           # multiple military signals
        "min_total_signals": 4,
    },
    "FULL_WAR": {
        "min_mil_confidence": 0.75,     # very strong military evidence
        "min_mil_signals": 3,           # many military signals
        "min_total_signals": 5,
        "require_logistics": True,      # logistics must be confirmed
    },
}


# ══════════════════════════════════════════════════════════════════════
#  RESULT DATA CLASS
# ══════════════════════════════════════════════════════════════════════

@dataclass
class ConflictStateResult:
    """Result of conflict state classification."""
    state: str                                  # classified state
    confidence: float                           # posterior confidence in classified state
    posterior: Dict[str, float] = field(default_factory=dict)   # full posterior distribution
    evidence_summary: Dict[str, float] = field(default_factory=dict)  # signal contributions
    gate_pass: Dict[str, bool] = field(default_factory=dict)   # which state gates passed
    country: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state,
            "confidence": round(self.confidence, 4),
            "posterior": {k: round(v, 4) for k, v in self.posterior.items()},
            "evidence_summary": {k: round(v, 4) for k, v in self.evidence_summary.items()},
            "gate_pass": self.gate_pass,
            "country": self.country,
        }


# ══════════════════════════════════════════════════════════════════════
#  CORE CLASSIFIER
# ══════════════════════════════════════════════════════════════════════

def classify_conflict_state(
    projected_signals: Dict[str, Any],
    country: str = "",
    sre_domains: Optional[Dict[str, float]] = None,
) -> ConflictStateResult:
    """
    Classify the current conflict state from projected signals.

    Parameters
    ----------
    projected_signals : dict
        Signal name -> signal object (must have .confidence attribute)
    country : str
        ISO-3 country code (for prior adjustment)
    sre_domains : dict, optional
        Domain indices (capability, intent, stability, cost)

    Returns
    -------
    ConflictStateResult
    """
    country = (country or "").upper().strip()

    # ── Step 1: Extract signal confidences ─────────────────────────
    sig_conf: Dict[str, float] = {}
    for name, sig in (projected_signals or {}).items():
        conf = float(getattr(sig, "confidence", 0.0) or 0.0)
        if conf > 0.0:
            sig_conf[name] = conf

    # ── Step 2: Compute raw evidence accumulation per state ────────
    state_evidence: Dict[str, float] = {s: 0.0 for s in CONFLICT_STATES}

    for sig_name, sig_confidence in sig_conf.items():
        mappings = _SIGNAL_STATE_EVIDENCE.get(sig_name, [])
        for target_state, weight in mappings:
            # Evidence contribution = signal_confidence * weight
            state_evidence[target_state] += sig_confidence * weight

    # ── Step 3: Bayesian posterior computation ─────────────────────
    # P(state | evidence) ∝ P(evidence | state) × P(state)
    # P(evidence | state) approximated by accumulated evidence score

    # Build prior
    prior = dict(_BASE_PRIOR)
    if country in _COUNTRY_PRIOR_SHIFT:
        shifts = _COUNTRY_PRIOR_SHIFT[country]
        for state, delta in shifts.items():
            prior[state] = max(0.01, prior[state] + delta)
        # Re-normalize
        total = sum(prior.values())
        prior = {s: v / total for s, v in prior.items()}

    # Likelihood from evidence (softmax-style)
    import math
    _TEMP = 2.0  # temperature — lower = more decisive
    likelihood: Dict[str, float] = {}
    for state in CONFLICT_STATES:
        likelihood[state] = math.exp(state_evidence[state] / _TEMP)

    # Unnormalized posterior
    unnorm = {s: prior[s] * likelihood[s] for s in CONFLICT_STATES}
    total_post = sum(unnorm.values())
    posterior = {s: unnorm[s] / total_post if total_post > 0 else 0.2
                 for s in CONFLICT_STATES}

    # ── Step 4: State machine gate check ───────────────────────────
    # Compute gate-relevant metrics
    mil_signals = [
        (name, conf) for name, conf in sig_conf.items()
        if any(kw in name.upper() for kw in ("MIL", "FORCE", "LOGISTICS", "BORDER"))
    ]
    max_mil_conf = max((c for _, c in mil_signals), default=0.0)
    num_mil_signals = len(mil_signals)

    hostility_signals = [
        (name, conf) for name, conf in sig_conf.items()
        if any(kw in name.upper() for kw in ("HOSTIL", "HOSTILE", "COERCIVE", "RETALIA"))
    ]
    max_hostility_conf = max((c for _, c in hostility_signals), default=0.0)

    has_logistics = any(
        "LOGISTICS" in name.upper() and conf > 0.3
        for name, conf in sig_conf.items()
    )

    total_signals = len(sig_conf)

    gate_pass: Dict[str, bool] = {}
    for state in CONFLICT_STATES:
        gate = _STATE_GATE.get(state, {})
        passed = True

        if state == "PEACE":
            if max_mil_conf > gate.get("max_mil_confidence", 1.0):
                passed = False
            if max_hostility_conf > gate.get("max_hostility_confidence", 1.0):
                passed = False
        else:
            if total_signals < gate.get("min_total_signals", 0):
                passed = False
            if max_mil_conf < gate.get("min_mil_confidence", 0.0):
                passed = False
            if num_mil_signals < gate.get("min_mil_signals", 0):
                passed = False
            if gate.get("require_logistics", False) and not has_logistics:
                passed = False

        gate_pass[state] = passed

    # ── Step 5: Combine Bayesian + Gate → Final state ──────────────
    # Filter states by gate, then pick highest posterior
    eligible = {s: posterior[s] for s in CONFLICT_STATES if gate_pass[s]}

    if not eligible:
        # Fallback: relax to CRISIS (always defensible if signals exist)
        classified_state = "CRISIS" if total_signals > 0 else "PEACE"
        classified_conf = posterior.get(classified_state, 0.25)
    else:
        classified_state = max(eligible, key=eligible.get)
        classified_conf = eligible[classified_state]

    # ── Step 6: SRE cross-validation ───────────────────────────────
    # If SRE domains show very high capability+intent but state is low,
    # bump state up by one notch
    if sre_domains:
        cap = sre_domains.get("capability", 0.0)
        intent = sre_domains.get("intent", 0.0)
        if cap > 0.5 and intent > 0.5:
            state_idx = _STATE_IDX.get(classified_state, 0)
            if state_idx < 2:  # below LIMITED_STRIKES
                classified_state = CONFLICT_STATES[min(state_idx + 1, len(CONFLICT_STATES) - 1)]
                classified_conf = max(classified_conf, posterior.get(classified_state, 0.3))
                logger.info(
                    "[CONFLICT-STATE] SRE cross-val bump: cap=%.2f intent=%.2f -> %s",
                    cap, intent, classified_state,
                )

    result = ConflictStateResult(
        state=classified_state,
        confidence=classified_conf,
        posterior=posterior,
        evidence_summary=state_evidence,
        gate_pass=gate_pass,
        country=country,
    )

    logger.info(
        "[CONFLICT-STATE] %s (conf=%.3f) | posterior: %s | gates: %s",
        classified_state,
        classified_conf,
        " ".join(f"{s}={posterior[s]:.3f}" for s in CONFLICT_STATES),
        " ".join(f"{s}={'OK' if gate_pass[s] else 'FAIL'}" for s in CONFLICT_STATES),
    )

    return result


# ══════════════════════════════════════════════════════════════════════
#  FORMATTING HELPER
# ══════════════════════════════════════════════════════════════════════

_STATE_LABELS = {
    "PEACE":            "PEACE — No active conflict indicators",
    "CRISIS":           "CRISIS — Heightened tensions, no kinetic action confirmed",
    "LIMITED_STRIKES":  "LIMITED STRIKES — Targeted kinetic operations detected/probable",
    "ACTIVE_CONFLICT":  "ACTIVE CONFLICT — Sustained military operations underway",
    "FULL_WAR":         "FULL WAR — Large-scale conventional warfare ongoing",
}

_STATE_EMOJI = {
    "PEACE": "\u2705",            # ✅
    "CRISIS": "\u26A0\uFE0F",    # ⚠️
    "LIMITED_STRIKES": "\U0001F4A5",  # 💥
    "ACTIVE_CONFLICT": "\U0001F525",  # 🔥
    "FULL_WAR": "\u2622\uFE0F",  # ☢️
}


def format_conflict_state_section(csr: ConflictStateResult) -> str:
    """Format conflict state for report output."""
    label = _STATE_LABELS.get(csr.state, csr.state)

    lines = [
        "",
        "=" * 72,
        "  CONFLICT STATE ASSESSMENT  (Present-State Classification)",
        "=" * 72,
        "",
        f"  Classified State:   {label}",
        f"  State Confidence:   {csr.confidence*100:.1f}%",
        f"  Country:            {csr.country or 'N/A'}",
        "",
        "  Posterior Distribution:",
    ]

    # Posterior bar chart
    for state in CONFLICT_STATES:
        p = csr.posterior.get(state, 0.0)
        bar_len = int(p * 40)
        marker = " <<<" if state == csr.state else ""
        lines.append(f"    {state:18s} {p*100:5.1f}%  {'|' * bar_len}{marker}")

    # Gate status
    lines.append("")
    lines.append("  State Gate Status:")
    for state in CONFLICT_STATES:
        passed = csr.gate_pass.get(state, False)
        status = "PASS" if passed else "FAIL"
        lines.append(f"    {state:18s} {status}")

    # Evidence summary
    if any(v > 0 for v in csr.evidence_summary.values()):
        lines.append("")
        lines.append("  Signal Evidence Accumulation:")
        for state in CONFLICT_STATES:
            ev = csr.evidence_summary.get(state, 0.0)
            if ev > 0:
                lines.append(f"    {state:18s} {ev:.3f}")

    lines.append("")
    return "\n".join(lines)
