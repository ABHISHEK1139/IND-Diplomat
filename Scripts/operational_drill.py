"""
IND-Diplomat — Operational Drill Harness
=========================================
Analyst-grade tasking order through the canonical entry point.
Full verbose logging to stdout + file.  No system modifications.
"""

import asyncio
import logging
import sys
import traceback
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


QUERY = (
    "Provide an intelligence assessment of escalation dynamics between Iran and Israel. "
    "Focus on military capability indicators, economic pressure, domestic stability, "
    "and alliance behavior. "
    "List the key indicators that would change the assessment."
)


def _configure_logging():
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    fmt = logging.Formatter(
        "[%(asctime)s] %(levelname)-7s %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(fmt)
    root.addHandler(ch)

    for name in [
        "Layer4_Analysis.coordinator",
        "Layer4_Analysis.deliberation.red_team",
        "Layer4_Analysis.deliberation.cove",
        "Layer4_Analysis.core.unified_pipeline",
        "Layer3_StateModel",
        "diplomat.ops_health",
        "intelligence.pir",
        "intelligence.collection_bridge",
        "moltbot_agent",
    ]:
        logging.getLogger(name).setLevel(logging.DEBUG)


def log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


async def run_drill():
    from run import diplomat_query
    from engine.Layer6_Presentation.report_builder import build_report_from_pipeline_result

    log("OPERATIONAL DRILL — Analyst Tasking Order")
    log(f"QUERY: {QUERY}")
    print()

    result = await diplomat_query(
        QUERY,
        country_code="IRN",
        use_red_team=True,
        use_mcts=False,
        max_investigation_loops=1,
        enable_system_guardian=True,
    )

    # ── PRIMARY OUTPUT: Intelligence Briefing ─────────────────────
    print()
    report = build_report_from_pipeline_result(result._raw)
    print(report)

    # ── DIAGNOSTIC SECTION (for developer only) ──────────────────
    print()
    print("=" * 72)
    print("  DIAGNOSTIC LOG  (developer view — not shown to end users)")
    print("=" * 72)
    print(f"  Outcome            : {result.outcome}")
    print(f"  Confidence         : {result.confidence:.4f}")
    print(f"  Risk Level         : {result.risk_level}")
    print(f"  Trace ID           : {result.trace_id}")

    if result.operational_warnings:
        print(f"\n  Operational Warnings ({len(result.operational_warnings)}):")
        for w in result.operational_warnings:
            print(f"    WARNING: {w}")

    if result.sources:
        print(f"\n  Sources ({len(result.sources)}):")
        for i, src in enumerate(result.sources[:10], 1):
            name = src.get("source", src.get("id", "?"))
            score = src.get("score", "")
            url = src.get("url", "")
            print(f"    [{i:2d}] {name}  (score: {score})  {url}")
    print()

    # Raw pipeline fields
    raw = result._raw
    if raw:
        print("=" * 72)
        print("  RAW PIPELINE FIELDS")
        print("=" * 72)
        for attr in [
            "status", "layer4_allowed", "layer4_gate_reason",
            "analytic_confidence", "epistemic_confidence",
            "early_warning_index", "escalation_sync", "prewar_detected",
            "warning", "intelligence_report",
        ]:
            val = getattr(raw, attr, None)
            if val is not None:
                if attr == "intelligence_report" and isinstance(val, dict):
                    print(f"  {attr:30s}:")
                    for k, v in val.items():
                        if isinstance(v, list):
                            print(f"    {k}: {v[:8]}")
                        elif isinstance(v, str) and len(v) > 120:
                            print(f"    {k}: {v[:120]}...")
                        else:
                            print(f"    {k}: {v}")
                else:
                    print(f"  {attr:30s}: {val}")

        # Investigation metadata
        inv = getattr(raw, "investigation_meta", None) or getattr(raw, "escalation_trace", None)
        if inv:
            print(f"\n  Investigation metadata:")
            if isinstance(inv, dict):
                for k, v in inv.items():
                    print(f"    {k}: {v}")

    print()
    return result


def main():
    log("=" * 60)
    log("IND-Diplomat Operational Drill")
    log("Read-only — no system modifications")
    log("=" * 60)
    print()

    _configure_logging()

    try:
        result = asyncio.run(run_drill())
        log(f"Drill COMPLETED — outcome: {result.outcome}")
    except Exception:
        log("Drill raised an exception:")
        traceback.print_exc()

    log("Drill finished — system state preserved.")


if __name__ == "__main__":
    main()
