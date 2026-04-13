"""War-room drill — integration test for all 6 steps."""
import asyncio
import logging
import shutil
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)

from run import diplomat_query
from test._support import output_path

QUERY = (
    "Assess the current risk of military escalation in the Persian Gulf "
    "region with focus on Iran nuclear program tensions"
)


async def main():
    t0 = time.perf_counter()
    raw = await diplomat_query(QUERY, country_code="IRN")
    elapsed = time.perf_counter() - t0

    # Normalize to dict regardless of return type
    if hasattr(raw, "_raw") and raw._raw is not None:
        # DiplomatResult wraps a PipelineResult
        pr = raw._raw
        result = vars(pr) if hasattr(pr, "__dict__") else {}
        result["answer"] = raw.answer
        result["outcome"] = raw.outcome
    elif hasattr(raw, "to_dict"):
        result = raw.to_dict()
    elif hasattr(raw, "__dict__"):
        result = vars(raw)
    elif isinstance(raw, dict):
        result = raw
    else:
        result = {"answer": str(raw)}

    print("\n" + "=" * 70)
    print("WAR-ROOM DRILL RESULT")
    print("=" * 70)
    print(f"Elapsed:              {elapsed:.1f}s")
    print(f"Status:               {result.get('status', '?')}")
    print(f"Risk level:           {result.get('risk_level', '?')}")
    print(f"Confidence:           {result.get('confidence', 0):.3f}")
    print(f"Analytic confidence:  {result.get('analytic_confidence', 0):.3f}")
    print(f"Epistemic confidence: {result.get('epistemic_confidence', 0):.3f}")

    gv = result.get("gate_verdict") or {}
    if hasattr(gv, "__dict__") and not isinstance(gv, dict):
        gv = vars(gv)
    if not isinstance(gv, dict):
        gv = {}
    print(f"Gate approved:        {gv.get('approved')}")
    print(f"Gate decision:        {gv.get('decision')}")
    if gv.get("collection_tasks"):
        print(f"Collection tasks:     {len(gv['collection_tasks'])}")
        for i, t in enumerate(gv["collection_tasks"][:5], 1):
            print(f"  TASK-{i}: [{t.get('priority')}] {t.get('signal')} via {t.get('modality')}")
    if gv.get("reasons"):
        print(f"Gate reasons ({len(gv['reasons'])}):")
        for r in gv["reasons"][:5]:
            print(f"  - {r[:120]}")

    # SRE details from council session
    cs = result.get("council_session", {})
    ministers = list(cs.get("minister_reports", {}).keys())
    print(f"Ministers:             {ministers}")
    print(f"Investigation rounds: {cs.get('investigation_rounds', 0)}")

    # Temporal trend info
    tt = cs.get("temporal_trend", {})
    if tt:
        print(f"Temporal trend:       esc_patterns={tt.get('trend_override_count', 0)} snapshots={tt.get('snapshot_count', 0)}")

    answer = str(result.get("answer", ""))
    print(f"\n--- Answer preview ({len(answer)} chars) ---")
    print(answer[:2000])
    print("--- end ---")

    # ── Formatted Intelligence Report ─────────────────────────────
    try:
        from engine.Layer5_Judgment.report_formatter import format_assessment
        report = format_assessment(result)
        print("\n")
        print(report)
        # Also write to file
        report_path = output_path("reports", "latest_assessment.txt")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"\n[Report written to {report_path}]")
    except Exception as e:
        print(f"\n[Report formatter error: {e}]")

    # ── Assessment Record (Layer-5 flight recorder) ───────────────
    try:
        from engine.Layer5_Judgment.assessment_record import build_assessment_record, write_assessment_record
        record = build_assessment_record(result)
        record_path = write_assessment_record(result)
        if record_path:
            copied_record_path = output_path("reports", Path(record_path).name)
            shutil.copy2(record_path, copied_record_path)
            record_path = copied_record_path
        print(f"\n[Assessment record written to {record_path}]")
    except Exception as e:
        print(f"\n[Assessment record error: {e}]")
        record = None

    # ── Layer-6 Intelligence Briefing ─────────────────────────────
    try:
        from engine.Layer6_Presentation.briefing_builder import build_full_briefing, write_briefing
        if record:
            briefing = build_full_briefing(record)
            briefing_path = write_briefing(record)
            if briefing_path:
                copied_briefing_path = output_path("reports", Path(briefing_path).name)
                shutil.copy2(briefing_path, copied_briefing_path)
                briefing_path = copied_briefing_path
            print(f"[Intelligence briefing written to {briefing_path}]")
            print("\n" + "=" * 70)
            print("LAYER-6 INTELLIGENCE BRIEFING")
            print("=" * 70)
            print(briefing)
        else:
            print("[Skipped briefing — no assessment record]")
    except Exception as e:
        print(f"\n[Briefing builder error: {e}]")

    # ── Phase 6: Learning Summary ────────────────────────────────
    try:
        cs = result.get("council_session", {})
        learning = cs.get("learning", {})
        if learning:
            print("\n" + "=" * 70)
            print("PHASE 6 — AUTONOMOUS CALIBRATION SUMMARY")
            print("=" * 70)
            fs = learning.get("forecast_summary", {})
            cal = learning.get("calibration", {})
            print(f"  Forecasts:  {fs.get('total_forecasts', 0)} total, "
                  f"{fs.get('total_resolved', 0)} resolved, "
                  f"{fs.get('newly_resolved', 0)} newly resolved")
            avg_b = cal.get("avg_brier")
            print(f"  Calibration: tier={cal.get('tier', 'N/A')}  "
                  f"avg_brier={f'{avg_b:.4f}' if avg_b is not None else 'N/A'}  "
                  f"eligible={'YES' if cal.get('eligible') else 'NO'}")
            print(f"  Conf Multiplier: {learning.get('confidence_multiplier', 1.0):.4f}")
            adj = learning.get("adjustments", {})
            if adj.get("proposed_deltas"):
                print(f"  Auto-Adjust: {len(adj['proposed_deltas'])} changes proposed")
            else:
                print(f"  Auto-Adjust: {adj.get('reason', 'none')}")
        else:
            print("\n[Phase 6 learning data not available]")
    except Exception as e:
        print(f"\n[Phase 6 learning summary error: {e}]")

    # ── Conflict State Classification ─────────────────────────────
    try:
        cs = result.get("council_session", {})
        global_model = cs.get("global_model", {})
        conflict = global_model.get("conflict_state", {})
        if conflict and conflict.get("state") not in (None, "UNKNOWN", ""):
            print("\n" + "=" * 70)
            print("CONFLICT STATE CLASSIFICATION (Bayesian)")
            print("=" * 70)
            print(f"  State:           {conflict.get('state', 'UNKNOWN')}")
            print(f"  Confidence:      {float(conflict.get('confidence', 0))*100:.1f}%")
            print(f"  Country:         {conflict.get('country', 'N/A')}")
            print(f"  Matrix:          {conflict.get('transition_source', 'expert')}")
            posterior = conflict.get("posterior", {})
            if posterior:
                print(f"  Posterior:        ", end="")
                print("  ".join(f"{s}={float(v)*100:.1f}%" for s, v in sorted(posterior.items(),
                      key=lambda x: ["PEACE","CRISIS","LIMITED_STRIKES","ACTIVE_CONFLICT","FULL_WAR"].index(x[0])
                      if x[0] in ["PEACE","CRISIS","LIMITED_STRIKES","ACTIVE_CONFLICT","FULL_WAR"] else 99)))
            forecast = conflict.get("forecast_14d", {})
            if forecast:
                print(f"  14d Forecast:    ", end="")
                print("  ".join(f"{s}={float(v)*100:.1f}%" for s, v in sorted(forecast.items(),
                      key=lambda x: ["PEACE","CRISIS","LIMITED_STRIKES","ACTIVE_CONFLICT","FULL_WAR"].index(x[0])
                      if x[0] in ["PEACE","CRISIS","LIMITED_STRIKES","ACTIVE_CONFLICT","FULL_WAR"] else 99)))
            p_active = float(conflict.get("p_active_or_higher_14d", 0.0))
            print(f"  P(ACTIVE+ 14d):  {p_active*100:.1f}%")
        else:
            print("\n[Conflict state data not available]")
    except Exception as e:
        print(f"\n[Conflict state summary error: {e}]")

    # ── Phase 7: Global Strategic Synchronization ─────────────────
    try:
        cs = result.get("council_session", {})
        global_model = cs.get("global_model", {})
        if global_model:
            print("\n" + "=" * 70)
            print("PHASE 7 — GLOBAL STRATEGIC SYNCHRONIZATION")
            print("=" * 70)
            risk = global_model.get("risk_summary", {})
            print(f"  Active Theaters:    {risk.get('active_count', 0)} / {risk.get('total_theaters', 0)}")
            print(f"  Total SRE:          {risk.get('total_sre', 0):.3f}")
            print(f"  Highest Risk:       {risk.get('max_theater', 'N/A')} (SRE={risk.get('max_sre', 0):.3f})")
            print(f"  Systemic Cascade:   {'YES' if global_model.get('systemic_cascade') else 'No'}")

            # Contagion
            contagion = global_model.get("contagion", {})
            if contagion:
                print(f"  Contagion Sources:  {len(contagion)}")
                for src, targets in sorted(contagion.items()):
                    target_str = ", ".join(f"{t}+{v:.3f}" for t, v in sorted(targets.items(), key=lambda x: -x[1]))
                    print(f"    {src} → {target_str}")
            else:
                print(f"  Contagion Sources:  0 (no cross-theater spillover)")

            # Adjusted forecast
            adj = global_model.get("adjusted_forecast", {})
            if adj:
                print(f"  Cross-Theater Adj:  Base={adj.get('base_prob', 0)*100:.1f}% "
                      f"+ Spillover={adj.get('spillover', 0)*100:.1f}% "
                      f"= Adjusted={adj.get('adjusted_prob', 0)*100:.1f}%")

            # Centrality
            centrality = global_model.get("centrality", {})
            if centrality:
                top3 = sorted(centrality.items(), key=lambda x: -x[1])[:3]
                print(f"  Top Centrality:     {', '.join(f'{cc}={v:.2f}' for cc, v in top3)}")

            # Collection priority
            coll = global_model.get("collection_priority", [])
            if coll:
                top3 = coll[:3]
                print(f"  Collection Priority: {', '.join(f'{cc}={v:.4f}' for cc, v in top3)}")
        else:
            print("\n[Phase 7 global model data not available]")
    except Exception as e:
        print(f"\n[Phase 7 global summary error: {e}]")

    # Exit 0 explicitly (avoid PowerShell NativeCommandError misread)
    sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
