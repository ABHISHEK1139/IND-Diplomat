# Layer4_Analysis/escalation_index.py
"""
Escalation Index — the missing brain of the intelligence system.

Combines four strategic domain indices with temporal trend data
to produce a single escalation score in [0.0, 1.0].

Thresholds (Phase 8)
--------------------
  < 0.30  → LOW
  < 0.50  → ELEVATED
  < 0.75  → HIGH
  ≥ 0.75  → CRITICAL
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, asdict
from typing import Optional

_log = logging.getLogger("Layer4_Analysis.escalation_index")

# ── Weight vector (sums to 1.0 before trend bonus) ──────────────
W_CAPABILITY  = 0.35
W_INTENT      = 0.30
W_INSTABILITY = 0.20
W_COST        = 0.15

# ── Temporal bonuses (Phase 4: spike-responsive) ────────────────
# Phase 3: was min(0.15, 0.05×patterns + 0.05×spikes) — spikes had
#          zero marginal effect once patterns alone hit the cap.
# Phase 4: cap raised to 0.20, coefficients re-balanced so spikes
#          actually matter.  Plus, spike_severity adds proportional
#          weight: strong surges (high sigma) count more.
TREND_BONUS_PER_PATTERN = 0.04
TREND_BONUS_PER_SPIKE   = 0.03
TREND_BONUS_CAP         = 0.20

# Proportional spike severity: each unit of max_spike_sigma contributes
# this much to the trend bonus (before cap).  E.g. a 4σ spike adds 0.08.
SPIKE_SEVERITY_WEIGHT   = 0.02

# ── Phase 3: Capability floor rule ───────────────────────────────
# If no hard-power buildup exists, deflate escalation score.
# Prevents rhetorical spikes from triggering CRITICAL alone.
CAPABILITY_FLOOR        = 0.30
CAPABILITY_FLOOR_PENALTY = 0.85   # multiplier when cap < floor

# ── Phase 4.2: Hard mobilization trigger ─────────────────────────
# Real wars start with mobilization.  If SIG_MIL_MOBILIZATION is
# confirmed (conf > 0.60), boost escalation by a flat amount.
MOBILIZATION_TRIGGER_THRESHOLD = 0.60
MOBILIZATION_TRIGGER_BOOST     = 0.10

# Phase 4.3b: Logistics buildup accelerator
# Pre-positioning of supplies/fuel is a strong pre-war indicator.
LOGISTICS_TRIGGER_THRESHOLD    = 0.55
LOGISTICS_TRIGGER_BOOST        = 0.08


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  FROZEN CONTRACT — EscalationInput
#  Every field is empirical-only; no legal/derived data may enter.
#  If you add a field, you MUST update compute_escalation_index().
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@dataclass(frozen=True)
class EscalationInput:
    """Strict, typed input to the SRE.  All values in [0.0, 1.0]."""
    capability:          float
    intent:              float
    instability:         float
    cost:                float
    escalation_patterns: int   = 0
    spike_count:         int   = 0
    max_spike_severity:  float = 0.0   # Phase 4.4: max σ-score across spikes
    mobilization_conf:   float = 0.0   # Phase 4.2: SIG_MIL_MOBILIZATION conf
    logistics_conf:      float = 0.0   # Phase 4.3b: SIG_LOGISTICS_PREP conf

    def to_dict(self) -> dict:
        return asdict(self)

    def __post_init__(self):
        for field_name in ("capability", "intent", "instability", "cost"):
            v = getattr(self, field_name)
            if not (0.0 <= v <= 1.0):
                raise ValueError(f"EscalationInput.{field_name} must be in [0,1], got {v}")


def compute_escalation_index(
    domains,
    temporal=None,
    *,
    inp: Optional[EscalationInput] = None,
):
    """
    Parameters
    ----------
    domains : dict   (legacy path)
        Output of ``compute_domain_indices()`` — keys: capability,
        intent, stability, cost.  Each in [0, 1].
    temporal : object   (legacy path)
        Must expose ``escalation_patterns`` (int) and ``spike_count``
        (int).  If attributes are missing they default to 0.
    inp : EscalationInput   (preferred path)
        If supplied, *domains* and *temporal* are ignored.

    Returns
    -------
    float   Escalation score clamped to [0.0, 1.0].
    """

    # ── Prefer typed input ──────────────────────────────────────
    if inp is not None:
        capability   = inp.capability
        intent       = inp.intent
        instability  = inp.instability
        cost         = inp.cost
        esc_patterns = inp.escalation_patterns
        spike_count  = inp.spike_count
    else:
        # Legacy dict path (still used by coordinator today)
        capability  = domains.get("capability",  0.0)
        intent      = domains.get("intent",      0.0)
        instability = domains.get("stability",   0.0)
        cost        = domains.get("cost",        0.0)

        esc_patterns = getattr(temporal, "escalation_patterns", 0)
        if isinstance(esc_patterns, (list, tuple)):
            esc_patterns = len(esc_patterns)
        esc_patterns = int(esc_patterns) if esc_patterns else 0

        spike_count  = int(getattr(temporal, "spike_count", 0) or 0)

    # ── Phase 4: spike-responsive trend bonus ──────────────────
    # Spikes now contribute both by count AND by severity (sigma).
    max_spike_sev = getattr(inp, "max_spike_severity", 0.0) if inp else 0.0
    trend_bonus = min(
        TREND_BONUS_CAP,
        TREND_BONUS_PER_PATTERN * esc_patterns
        + TREND_BONUS_PER_SPIKE * spike_count
        + SPIKE_SEVERITY_WEIGHT * max_spike_sev,
    )

    # ── Bayesian sum logic (Weighted Probability) ───────────────
    # P(Escalation | Signals) logic
    # constraint works as a true dampener directly on the aggregate score.
    
    raw_escalation = (
        W_CAPABILITY  * capability  +
        W_INTENT      * intent      +
        W_INSTABILITY * instability
    )
    raw_escalation = min(raw_escalation, 1.0)
    
    # Cost acts as the braking constraint
    constraint_factor = cost * 0.5  # Adjust strength of economic brake

    # ── Phase 4.2: hard mobilization trigger ────────────────────
    mob_conf = getattr(inp, "mobilization_conf", 0.0) if inp else 0.0
    mob_triggered = False
    if mob_conf > MOBILIZATION_TRIGGER_THRESHOLD:
        raw_escalation += MOBILIZATION_TRIGGER_BOOST
        mob_triggered = True

    # ── Phase 4.3b: logistics buildup trigger ───────────────────
    log_conf = getattr(inp, "logistics_conf", 0.0) if inp else 0.0
    log_triggered = False
    if log_conf > LOGISTICS_TRIGGER_THRESHOLD:
        raw_escalation += LOGISTICS_TRIGGER_BOOST
        log_triggered = True

    raw_escalation += trend_bonus
    
    # ── Phase 6: Apply brakes ───────────────────────────────────
    # adjusted_score = raw_score * (1 - constraint_factor)
    escalation = raw_escalation * (1.0 - constraint_factor)
    escalation = max(0.0, min(escalation, 1.0))

    _log.info(
        "[SRE] cap=%.3f  int=%.3f  stab=%.3f  cost=%.3f  "
        "trend_bonus=%.2f (esc_pat=%d spike=%d sev=%.2f)  "
        "mob=%s  log=%s  cap_floor=%s  → escalation=%.3f",
        capability, intent, instability, cost,
        trend_bonus, esc_patterns, spike_count, max_spike_sev,
        "TRIGGERED(+%.2f)" % MOBILIZATION_TRIGGER_BOOST if mob_triggered else "no",
        "TRIGGERED(+%.2f)" % LOGISTICS_TRIGGER_BOOST if log_triggered else "no",
        "APPLIED(-15%)" if cap_floor_applied else "ok",
        escalation,
    )

    return escalation


def escalation_to_risk(score):
    """Map a raw escalation score to a named risk level.

    Phase 8: thresholds lowered to account for structural ceiling
    effects (cost floor, trend cap) that compress practical SRE range.
    OLD: <0.35 LOW, <0.60 ELEVATED, <0.80 HIGH, ≥0.80 CRITICAL
    NEW: <0.30 LOW, <0.50 ELEVATED, <0.75 HIGH, ≥0.75 CRITICAL
    """
    if score < 0.30:
        return "LOW"
    elif score < 0.50:
        return "ELEVATED"
    elif score < 0.75:
        return "HIGH"
    else:
        return "CRITICAL"
