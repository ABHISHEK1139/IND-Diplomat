"""
apply_fix123.py — Surgical patch for FIX 1 + FIX 2 + FIX 3.
Reads coordinator.py, applies 3 structural corrections, writes back.
Run once:  python Scripts/apply_fix123.py
"""
import pathlib, sys, re

COORD = pathlib.Path(__file__).resolve().parent.parent / "Layer4_Analysis" / "coordinator.py"
src = COORD.read_text(encoding="utf-8")
original = src  # keep for safety check

# ===================================================================
# FIX 3 — Legal Constraint Index (LCI) injection
# Inject AFTER  sre_domains = compute_domain_indices(projected_list)
# and BEFORE the temporal / EscalationInput block.
# ===================================================================
FIX3_ANCHOR = "sre_domains = compute_domain_indices(projected_list)"
FIX3_INSERT = """sre_domains = compute_domain_indices(projected_list)

                # ── FIX 3: Legal Constraint Index (LCI) ────────────
                # Hardcoded per-country legal friction injected into
                # cost dimension.  Raises constraint (cost_raw) so SRE
                # sees higher friction for legally-constrained states.
                _LCI_TABLE = {
                    "IRN": 0.35,  # NPT signatory + UNSC sanctions
                    "PRK": 0.40,  # NPT withdrawal + UNSC sanctions + bilateral
                    "RUS": 0.25,  # UNSC P5 + bilateral sanctions + arms treaties
                    "CHN": 0.15,  # UNSC P5 + trade restrictions + NPT
                    "SYR": 0.30,  # UNSC sanctions + CWC violations
                    "ISR": 0.10,  # Defense pact obligations
                    "PAK": 0.20,  # Non-NPT nuclear + FATF greylist
                    "IND": 0.10,  # Non-NPT nuclear
                    "SAU": 0.10,  # Arms trade treaties
                    "MMR": 0.20,  # UNSC sanctions + ICJ proceedings
                    "VEN": 0.15,  # OAS sanctions + bilateral
                    "CUB": 0.15,  # Embargo + bilateral
                    "LBY": 0.20,  # UNSC sanctions + arms embargo
                    "YEM": 0.15,  # UNSC embargo + humanitarian law
                    "SDN": 0.20,  # ICC referral + UNSC sanctions
                    "SSD": 0.15,  # UNSC sanctions + arms embargo
                    "AFG": 0.15,  # UNSC sanctions + terrorist financing
                    "IRQ": 0.15,  # Legacy UNSC + bilateral constraints
                    "SOM": 0.15,  # UNSC arms embargo + humanitarian
                    "ETH": 0.10,  # Arms embargo risk + humanitarian
                    "ERI": 0.15,  # Former UNSC sanctions + bilateral
                    "BLR": 0.15,  # EU/US sanctions + bilateral
                    "UKR": 0.05,  # Budapest memorandum obligations
                }
                _lci_country = str(getattr(session, "learning_country", None) or "IRN").upper()
                _lci_value = _LCI_TABLE.get(_lci_country, 0.0)
                if _lci_value > 0:
                    _old_cost_raw = sre_domains.get("cost_raw", 0.0)
                    _new_cost_raw = min(_old_cost_raw + _lci_value, 1.0)
                    sre_domains["cost_raw"] = _new_cost_raw
                    sre_domains["cost"] = 1.0 - _new_cost_raw
                    logger.info(
                        "[FIX3-LCI] country=%s LCI=%.2f cost_raw: %.3f->%.3f cost_for_sre: %.3f",
                        _lci_country, _lci_value, _old_cost_raw, _new_cost_raw, sre_domains["cost"],
                    )
                else:
                    logger.info("[FIX3-LCI] country=%s LCI=0.00 (no legal constraint entry)", _lci_country)
"""

count3 = src.count(FIX3_ANCHOR)
if count3 != 1:
    print(f"[FIX3] ERROR: anchor found {count3} times (expected 1). Abort.")
    sys.exit(1)
src = src.replace(FIX3_ANCHOR, FIX3_INSERT, 1)
print("[FIX3] Legal Constraint Index injected.")


# ===================================================================
# FIX 1 — Multiplicative confidence architecture
# Replace the old weighted-sum formula + structural penalties
# with base × evidence_mult × dim_mult × temporal_mult
# ===================================================================

# --- old block to replace (lines 1753-1787 area) ---
OLD_CONF_BLOCK = """        weighted_confidence = max(0.0, min(1.0,
            0.30 * float(sensor_score) +
            0.20 * v_score +
            0.15 * l_score +
            0.20 * meta_conf +
            0.15 * doc_conf
            - rt_penalty
        ))

        # ── Phase 3 §5: Structural confidence penalties ────────────
        # Penalise thin evidence and poor dimension balance.
        _struct_penalty = 0.0
        _num_sources = len(set(
            str(getattr(s, "source", ""))
            for s in projected_list
            if str(getattr(s, "source", "")).strip()
        )) if projected_list else 0
        if _num_sources < 3:
            _struct_penalty += 0.05
            logger.info("[CONF-PENALTY] evidence_sources=%d < 3 → -0.05", _num_sources)

        _dim_coverage = 0.0
        _sre_dom = getattr(session, "sre_domains", None) or {}
        if _sre_dom:
            _active_dims = sum(1 for d in ("capability", "intent", "stability", "cost")
                               if _sre_dom.get(d, 0.0) > 0.10)
            _dim_coverage = _active_dims / 4.0
        if _dim_coverage < 0.5:
            _struct_penalty += 0.05
            logger.info("[CONF-PENALTY] dimension_coverage=%.2f < 0.50 → -0.05", _dim_coverage)

        if _struct_penalty > 0:
            weighted_confidence = max(0.0, weighted_confidence - _struct_penalty)
            logger.info("[CONF-PENALTY] total structural penalty=%.2f → conf=%.3f",
                        _struct_penalty, weighted_confidence)"""

NEW_CONF_BLOCK = """        # ── FIX 1: Multiplicative confidence architecture ────────────
        # Step 1: Base confidence (legacy weighted sum minus red-team)
        base_confidence = max(0.0, min(1.0,
            0.30 * float(sensor_score) +
            0.20 * v_score +
            0.15 * l_score +
            0.20 * meta_conf +
            0.15 * doc_conf
            - rt_penalty
        ))

        # Step 2: Evidence multiplier — rewards diverse sourcing
        _num_sources = len(set(
            str(getattr(s, "source", ""))
            for s in projected_list
            if str(getattr(s, "source", "")).strip()
        )) if projected_list else 0
        _evidence_multiplier = 1.10 if _num_sources >= 4 else 1.00
        logger.info("[CONF-FIX1] evidence_sources=%d -> evidence_mult=%.2f",
                    _num_sources, _evidence_multiplier)

        # Step 3: Dimensional balance multiplier
        _sre_dom = getattr(session, "sre_domains", None) or {}
        _active_dims = 0
        if _sre_dom:
            _active_dims = sum(1 for d in ("capability", "intent", "stability", "cost")
                               if _sre_dom.get(d, 0.0) > 0.25)
        if _active_dims >= 3:
            _dim_multiplier = 1.05
        elif _active_dims <= 1:
            _dim_multiplier = 0.95
        else:
            _dim_multiplier = 1.00
        logger.info("[CONF-FIX1] active_dims=%d -> dim_mult=%.2f",
                    _active_dims, _dim_multiplier)

        # Step 4: Temporal support multiplier
        _sre_inp = getattr(session, "sre_input", None)
        _esc_patterns = int(getattr(_sre_inp, "escalation_patterns", 0)) if _sre_inp else 0
        _spk_count = int(getattr(_sre_inp, "spike_count", 0)) if _sre_inp else 0
        _temporal_multiplier = 1.00
        if _spk_count >= 2:
            _temporal_multiplier = 1.08
        elif _esc_patterns >= 2:
            _temporal_multiplier = 1.05
        logger.info("[CONF-FIX1] esc_patterns=%d spike_count=%d -> temporal_mult=%.2f",
                    _esc_patterns, _spk_count, _temporal_multiplier)

        # Multiplicative combination
        weighted_confidence = base_confidence * _evidence_multiplier * _dim_multiplier * _temporal_multiplier
        weighted_confidence = max(0.0, min(1.0, weighted_confidence))
        logger.info("[CONF-FIX1] base=%.3f x ev=%.2f x dim=%.2f x temp=%.2f -> conf=%.3f",
                    base_confidence, _evidence_multiplier, _dim_multiplier,
                    _temporal_multiplier, weighted_confidence)"""

# Handle mojibake arrow character in the old block
OLD_VARIANTS = [OLD_CONF_BLOCK]
# Also try with unicode arrows
mojibake_block = OLD_CONF_BLOCK.replace("\u2192", "\u2192").replace("\u2014", "\u2014")
if mojibake_block != OLD_CONF_BLOCK:
    OLD_VARIANTS.append(mojibake_block)


matched = False
for variant in OLD_VARIANTS:
    if variant in src:
        src = src.replace(variant, NEW_CONF_BLOCK, 1)
        matched = True
        print("[FIX1] Confidence architecture replaced (exact match).")
        break

if not matched:
    # Fallback: regex-based replacement
    # Find the block by key markers
    pattern = re.compile(
        r"(        weighted_confidence = max\(0\.0, min\(1\.0,\s*\n"
        r"            0\.30 \* float\(sensor_score\).*?"
        r"            - rt_penalty\s*\n"
        r"        \)\).*?"
        r"logger\.info\(\"\[CONF-PENALTY\] total structural penalty=.*?weighted_confidence\))",
        re.DOTALL
    )
    m = pattern.search(src)
    if m:
        src = src[:m.start()] + NEW_CONF_BLOCK + src[m.end():]
        matched = True
        print("[FIX1] Confidence architecture replaced (regex fallback).")
    else:
        print("[FIX1] ERROR: Could not find confidence block. Abort.")
        sys.exit(1)


# ===================================================================
# FIX 2 — Sensor anchoring bias correction
# Insert BEFORE  session.final_confidence = weighted_confidence
# ===================================================================
FIX2_ANCHOR = "        session.final_confidence = weighted_confidence"
FIX2_INSERT = """        # ── FIX 2: Sensor anchoring bias correction ────────────────
        _divergence = abs(weighted_confidence - float(sensor_score))
        if _divergence < 0.05:
            weighted_confidence *= 0.95
            weighted_confidence = max(0.0, min(1.0, weighted_confidence))
            logger.info(
                "[CONF-FIX2] SENSOR_ANCHORING: divergence=%.3f < 0.05 -> penalty x0.95 -> conf=%.3f",
                _divergence, weighted_confidence,
            )
        else:
            logger.info("[CONF-FIX2] No anchoring bias: divergence=%.3f", _divergence)

        session.final_confidence = weighted_confidence"""

count2 = src.count(FIX2_ANCHOR)
if count2 < 1:
    print(f"[FIX2] ERROR: anchor not found. Abort.")
    sys.exit(1)
# Replace only first occurrence
src = src.replace(FIX2_ANCHOR, FIX2_INSERT, 1)
print("[FIX2] Sensor anchoring bias correction injected.")


# ===================================================================
# Final write
# ===================================================================
if src == original:
    print("ERROR: No changes made! Aborting.")
    sys.exit(1)

COORD.write_text(src, encoding="utf-8")
print(f"\nAll 3 fixes applied to {COORD}")
print("Run drill_test.py to verify.")
