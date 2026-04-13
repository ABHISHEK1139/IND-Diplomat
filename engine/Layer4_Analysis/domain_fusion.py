# Layer4_Analysis/domain_fusion.py
"""
Strategic Domain Fusion — converts raw projected signals into four
strategic dimensions: capability, intent, stability, cost.

Phase 3 calibrations:
  - Intent split into rhetorical vs operational sub-scores
  - Cost inverted to be a constraint (high cost = dampens escalation)

This is the first stage of the Strategic Risk Engine (SRE).
Ministers explain *why*. The SRE decides *what*.
"""

import logging

_log = logging.getLogger("Layer4_Analysis.domain_fusion")

# ── Phase 3: Intent sub-classification ────────────────────────────
# Operational intent = irreversible preparatory posture
# Rhetorical intent  = diplomatic signaling / words
_OPERATIONAL_INTENT = {
    "SIG_ALLIANCE_ACTIVATION",
    "SIG_ALLIANCE_SHIFT",
    "SIG_NEGOTIATION_BREAKDOWN",
    "SIG_RETALIATORY_THREAT",
}
# Everything else in INTENT dimension is rhetorical by default.


def compute_domain_indices(projected_signals):
    """
    Aggregate individual signal confidences into 4 strategic dimensions.

    Only **empirical** signals (``namespace == "empirical"``) are admitted.
    Legal or derived-legal signals are hard-filtered here — they never
    influence the SRE regardless of how they were injected upstream.

    Phase 3 calibrations applied:
      1. INTENT split into rhetorical (capped 0.6) and operational;
         final intent = 0.6 * operational + 0.4 * rhetorical.
      2. COST inverted: ``cost_constraint = raw_cost``;
         SRE receives ``1 - cost_constraint`` so high sanctions
         *dampen* (not boost) escalation.

    Parameters
    ----------
    projected_signals : list
        Each element must have `.confidence` (float), `.dimension` (str),
        `.name` (str), and optionally `.namespace` (str, default ``"empirical"``).

    Returns
    -------
    dict  { "capability": float, "intent": float,
            "stability": float, "cost": float,
            "intent_rhetorical": float, "intent_operational": float,
            "cost_raw": float }
        Each value is normalised to [0.0, 1.0].
        ``cost`` is already inverted (1 - constraint).
    """

    # Raw accumulators (Deduplicated/Max'd via Dictionary)
    tracker = {
        "capability":         {},
        "intent_rhetorical":  {},
        "intent_operational": {},
        "stability":          {},
        "cost":               {},
    }

    counts = {"capability": 0, "intent": 0, "stability": 0, "cost": 0}
    rejected_legal = 0

    # ── SRE INPUT DIAGNOSTIC ──────────────────────────────────────
    _log.info("[SRE-INPUT] %d signal(s) presented to domain fusion:", len(projected_signals))
    for sig in projected_signals:
        ns   = str(getattr(sig, "namespace", "empirical")).lower()
        name = str(getattr(sig, "name", "?"))
        dim  = str(getattr(sig, "dimension", "UNKNOWN")).upper()
        conf = float(getattr(sig, "confidence", 0.0))
        _log.info("  %-32s  ns=%-10s  dim=%-12s  conf=%.3f", name, ns, dim, conf)

    for sig in projected_signals:
        # ── HARD NAMESPACE FILTER ─────────────────────────────────
        ns = str(getattr(sig, "namespace", "empirical")).lower()
        if ns != "empirical":
            rejected_legal += 1
            continue

        conf = float(getattr(sig, "confidence", 0.0))
        memb = float(getattr(sig, "membership", conf))   # fallback to conf
        dim  = str(getattr(sig, "dimension", "UNKNOWN")).upper()
        name = str(getattr(sig, "name", ""))
        
        # Consolidate Double Counting inside Hierarchy
        if name in ["SIG_SANCTIONS_ACTIVE", "SIG_ECO_SANCTIONS_ACTIVE", "SIG_ECONOMIC_PRESSURE", "SIG_ECO_PRESSURE_HIGH"]:
            name = "ECONOMIC_DOMAIN_CONSTRAINT"
            dim  = "COST"

        # ── WMD Risk Strict Evidence Weighting ────────────────────
        if name in ("SIG_WMD_RISK", "SIG_WMD_READINESS", "SIG_NUCLEAR_ALERT"):
            sources = list(getattr(sig, "sources", []))
            if len(sources) < 2 or conf < 0.65:
                # Nullify or massively dampen
                _log.info("[WMD-GATE] Dampening %s due to low confidence (%.2f) or insufficient single source: %s", name, conf, sources)
                conf *= 0.1
                memb *= 0.1

        # ── Phase 4.3: Softened confidence weighting ──────────────
        weighted = memb * (conf ** 0.5)

        if dim == "CAPABILITY":
            tracker["capability"][name] = max(tracker["capability"].get(name, 0.0), weighted)
            counts["capability"] += 1
        elif dim == "INTENT":
            counts["intent"] += 1
            if name in _OPERATIONAL_INTENT:
                tracker["intent_operational"][name] = max(tracker["intent_operational"].get(name, 0.0), weighted)
            else:
                tracker["intent_rhetorical"][name] = max(tracker["intent_rhetorical"].get(name, 0.0), weighted)
        elif dim == "STABILITY":
            tracker["stability"][name] = max(tracker["stability"].get(name, 0.0), weighted)
            counts["stability"] += 1
        elif dim == "COST":
            tracker["cost"][name] = max(tracker["cost"].get(name, 0.0), weighted)
            counts["cost"] += 1
            
    raw = {
        "capability": sum(tracker["capability"].values()),
        "intent_rhetorical": sum(tracker["intent_rhetorical"].values()),
        "intent_operational": sum(tracker["intent_operational"].values()),
        "stability": sum(tracker["stability"].values()),
        "cost": sum(tracker["cost"].values())
    }

    if rejected_legal > 0:
        _log.info("[SRE-FIREWALL] Rejected %d non-empirical signal(s) from SRE input", rejected_legal)

    # ── KINETIC OVERRIDE ──────────────────────────────────────────
    # When confirmed kinetic activity (strikes, casualties) is present,
    # boost raw capability so real war moves the model.  This prevents
    # mobilization_conf from staying at 0.099 during active bombing.
    kinetic_conf = 0.0
    for sig in projected_signals:
        ns = str(getattr(sig, "namespace", "empirical")).lower()
        if ns != "empirical":
            continue
        name = str(getattr(sig, "name", ""))
        if name == "SIG_KINETIC_ACTIVITY":
            kinetic_conf = max(kinetic_conf, float(getattr(sig, "confidence", 0.0)))
    if kinetic_conf > 0.0:
        kinetic_boost = kinetic_conf * 0.5
        raw["capability"] = max(raw["capability"], kinetic_boost * 3.0)  # ×3 because normalizer divides by 3
        _log.info(
            "[KINETIC-OVERRIDE] kinetic_conf=%.3f  boost=%.3f  "
            "raw_capability raised to %.3f",
            kinetic_conf, kinetic_boost, raw["capability"],
        )

    # ── Normalise ─────────────────────────────────────────────────
    # Phase 4.1: With conf×memb weighting, max theoretical single-signal
    # contribution is 1.0×1.0 = 1.0.  Divisor stays at 3.0 so 3 strong
    # signals still saturate, but weak signals contribute much less.
    # Phase 8: cost divisor widened from 3.0 to 5.0 to prevent LCI
    # injection from saturating cost dimension and zeroing cost_for_sre.
    cap_norm  = min(raw["capability"] / 3.0, 1.0)
    stab_norm = min(raw["stability"]  / 3.0, 1.0)
    cost_norm = min(raw["cost"]       / 5.0, 1.0)  # Phase 8: was /3.0

    # ── Phase 3 §1: Intent split ──────────────────────────────────
    intent_rhet = min(raw["intent_rhetorical"]  / 3.0, 1.0)
    intent_oper = min(raw["intent_operational"] / 3.0, 1.0)
    # Cap rhetorical contribution (Phase 6: overridable by auto-adjuster)
    _rhet_cap = getattr(
        __import__("sys").modules.get(__name__),
        "_RHETORICAL_INTENT_CAP_OVERRIDE", 0.6
    ) if __import__("sys").modules.get(__name__) else 0.6
    intent_rhet = min(intent_rhet, _rhet_cap)
    # Blended intent
    intent_final = 0.6 * intent_oper + 0.4 * intent_rhet
    intent_final = min(intent_final, 1.0)

    # ── Phase 3 §2: Cost inversion ────────────────────────────────
    # cost_norm represents degree of constraint (sanctions, pressure).
    # High constraint DAMPENS escalation likelihood.
    # SRE will use (1 - cost_constraint).
    # Phase 8: floor of 0.10 so cost never contributes zero to SRE,
    # even when sanctions/pressure fully saturate.
    cost_constraint = cost_norm
    cost_for_sre    = max(0.10, 1.0 - cost_constraint)  # Phase 8: floor 0.10

    _log.info(
        "[INTENT-SPLIT] rhetorical=%.3f (capped)  operational=%.3f  "
        "→ blended_intent=%.3f",
        intent_rhet, intent_oper, intent_final,
    )
    _log.info(
        "[COST-INVERSION] raw_cost=%.3f  cost_constraint=%.3f  "
        "→ cost_for_sre=%.3f  (high constraint dampens escalation)",
        cost_norm, cost_constraint, cost_for_sre,
    )

    domains = {
        "capability":         cap_norm,
        "intent":             intent_final,
        "stability":          stab_norm,
        "cost":               cost_for_sre,
        # Sub-scores exposed for reporting / Layer 5
        "intent_rhetorical":  intent_rhet,
        "intent_operational": intent_oper,
        "cost_raw":           cost_norm,
    }

    _log.info(
        "[DOMAIN-FUSION] capability=%.3f  intent=%.3f  "
        "stability=%.3f  cost=%.3f  (signals: cap=%d int=%d stab=%d cost=%d)",
        domains["capability"], domains["intent"],
        domains["stability"], domains["cost"],
        counts["capability"], counts["intent"],
        counts["stability"], counts["cost"],
    )

    return domains
