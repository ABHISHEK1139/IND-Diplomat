"""
Ablation Study Framework — DIP 2.1 Validation Suite

Systematically disables one module at a time and measures the impact
on output quality. Answers: "Does this component actually improve results?"

Modules tested:
  1. Red Team (adversarial challenge)
  2. CRAG (evidence investigation)
  3. CoVe (claim verification)
  4. Assessment Gate (deterministic WITHHOLD/APPROVE)
  5. Council of Ministers (multi-perspective analysis)
  6. Strategic Narrative (executive synthesis)

Metrics per run:
  - Threat level consistency (does removing X change the threat level?)
  - Confidence shift (how much does confidence change?)
  - Hypothesis count delta
  - Evidence log size delta
  - Verification score delta
  - Gate verdict change
"""

from __future__ import annotations

import copy
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


@dataclass
class AblationResult:
    """Result of a single ablation run (module disabled)."""
    module_name: str
    module_description: str
    baseline: Dict[str, Any]           # Full pipeline result
    ablated: Dict[str, Any]            # Pipeline result with module disabled
    threat_level_changed: bool = False
    confidence_delta: float = 0.0
    hypothesis_count_delta: int = 0
    evidence_count_delta: int = 0
    verification_score_delta: float = 0.0
    gate_verdict_changed: bool = False
    elapsed_delta: float = 0.0


@dataclass
class AblationReport:
    """Aggregate ablation study report."""
    results: List[AblationResult] = field(default_factory=list)
    query: str = ""
    country_code: str = ""
    baseline_threat: str = ""
    baseline_confidence: float = 0.0
    total_modules_tested: int = 0
    impactful_modules: List[str] = field(default_factory=list)


def compute_ablation_delta(baseline: Dict[str, Any], ablated: Dict[str, Any],
                           module_name: str, module_desc: str) -> AblationResult:
    """Compute the difference between baseline and ablated run."""
    
    def _get_threat(r: Dict) -> str:
        return r.get("threat_level", "LOW")
    
    def _get_confidence(r: Dict) -> float:
        return r.get("verification_score", 0.5)
    
    def _get_hypothesis_count(r: Dict) -> int:
        return len(r.get("hypotheses", []))
    
    def _get_evidence_count(r: Dict) -> int:
        return len(r.get("evidence_log", []))
    
    def _get_gate(r: Dict) -> str:
        gv = r.get("gate_verdict", {})
        if isinstance(gv, dict):
            return gv.get("decision", "UNKNOWN")
        return str(gv)
    
    result = AblationResult(
        module_name=module_name,
        module_description=module_desc,
        baseline=baseline,
        ablated=ablated,
        threat_level_changed=_get_threat(baseline) != _get_threat(ablated),
        confidence_delta=round(_get_confidence(ablated) - _get_confidence(baseline), 4),
        hypothesis_count_delta=_get_hypothesis_count(ablated) - _get_hypothesis_count(baseline),
        evidence_count_delta=_get_evidence_count(ablated) - _get_evidence_count(baseline),
        verification_score_delta=round(
            ablated.get("verification_score", 0) - baseline.get("verification_score", 0), 4
        ),
        gate_verdict_changed=_get_gate(baseline) != _get_gate(ablated),
        elapsed_delta=round(
            ablated.get("elapsed_seconds", 0) - baseline.get("elapsed_seconds", 0), 2
        ),
    )
    
    return result


async def run_ablation_suite(
    execute_fn,
    query: str,
    country_code: str,
    modules_to_test: Optional[List[str]] = None,
) -> AblationReport:
    """
    Run full ablation study: baseline, then disable each module in turn.
    
    Args:
        execute_fn: async function(query, country_code, job_id) -> result dict
        query: Test query
        country_code: Country code
        modules_to_test: Which modules to ablate (None = all)
    """
    
    # Module registry: what to monkey-patch
    MODULES = {
        "red_team": {
            "desc": "Red Team adversarial challenge",
            "patch_target": "deliberation.red_team.challenge",
            "stub": lambda session: session,  # no-op
        },
        "crag": {
            "desc": "CRAG evidence investigation",
            "patch_target": "deliberation.crag.investigate",
            "stub": lambda session: session,
        },
        "cove": {
            "desc": "CoVe claim verification",
            "patch_target": "deliberation.cove.decompose",
            "stub": lambda session: [],
        },
        "assessment_gate": {
            "desc": "Assessment Gate (WITHHOLD/APPROVE)",
            "patch_target": "layer5_trajectory.assessment_gate.assess",
            "stub": lambda state: type('Verdict', (), {
                'approved': True, 'withheld': False, 'decision': 'APPROVE',
                'reasons': ['Gate bypassed for ablation study'],
                'mandatory_review': False, 'to_dict': lambda: {}
            })(),
        },
        "council": {
            "desc": "Council of Ministers (multi-perspective)",
            "patch_target": "layer4_reasoning.coordinator.run_council",
            "stub": lambda session: None,
        },
        "strategic_narrative": {
            "desc": "Strategic Narrative Synthesis",
            "patch_target": "layer6_presentation.strategic_narrative.synthesize_narrative",
            "stub": lambda session, result: {"executive_judgment": "Ablated", "generation_mode": "ablation"},
        },
    }
    
    if modules_to_test is None:
        modules_to_test = list(MODULES.keys())
    else:
        modules_to_test = [m for m in modules_to_test if m in MODULES]
    
    report = AblationReport(
        query=query,
        country_code=country_code,
        total_modules_tested=len(modules_to_test),
    )
    
    # ── 1. Baseline run ──
    print(f"\n{'='*60}")
    print(f"ABLATION STUDY: {country_code} — {query[:60]}")
    print(f"{'='*60}")
    print("\n[1] Running BASELINE (full pipeline)...")
    
    t0 = time.time()
    baseline = await execute_fn(query, country_code, "ablation-baseline")
    baseline_time = time.time() - t0
    
    report.baseline_threat = baseline.get("threat_level", "UNKNOWN")
    report.baseline_confidence = baseline.get("verification_score", 0.0)
    
    print(f"  Baseline Threat: {report.baseline_threat}")
    print(f"  Baseline Confidence: {report.baseline_confidence:.3f}")
    print(f"  Baseline Time: {baseline_time:.1f}s")
    print(f"  Hypotheses: {len(baseline.get('hypotheses', []))}")
    print(f"  Evidence: {len(baseline.get('evidence_log', []))}")
    
    # ── 2. Ablate each module ──
    for i, mod_name in enumerate(modules_to_test, 1):
        mod_info = MODULES[mod_name]
        print(f"\n[{i+1}] Ablating: {mod_name} — {mod_info['desc']}")
        
        import importlib
        target = mod_info["patch_target"]
        stub_fn = mod_info["stub"]
        
        # Split "module.path.function"
        parts = target.rsplit(".", 1)
        module_path = parts[0]
        func_name = parts[1] if len(parts) > 1 else target
        
        try:
            mod = importlib.import_module(module_path)
            original = getattr(mod, func_name, None)
            
            if original is None:
                print(f"  SKIP: Could not find {func_name} in {module_path}")
                continue
            
            # Monkey-patch
            setattr(mod, func_name, stub_fn)
            
            # Run
            t1 = time.time()
            ablated_result = await execute_fn(query, country_code, f"ablation-{mod_name}")
            ablated_time = time.time() - t1
            
            # Restore
            setattr(mod, func_name, original)
            
            # Compute delta
            delta = compute_ablation_delta(baseline, ablated_result, mod_name, mod_info["desc"])
            report.results.append(delta)
            
            # Print
            threat_icon = "⚠" if delta.threat_level_changed else "✓"
            gate_icon = "⚠" if delta.gate_verdict_changed else "✓"
            print(f"  Threat: {ablated_result.get('threat_level','?')} {threat_icon} (changed={delta.threat_level_changed})")
            print(f"  Gate: {delta.gate_verdict_changed} {gate_icon}")
            print(f"  ΔConfidence: {delta.confidence_delta:+.4f}")
            print(f"  ΔHypotheses: {delta.hypothesis_count_delta:+d}")
            print(f"  ΔEvidence: {delta.evidence_count_delta:+d}")
            print(f"  ΔTime: {delta.elapsed_delta:+.1f}s")
            
            # Track impactful modules
            if delta.threat_level_changed or delta.gate_verdict_changed or abs(delta.confidence_delta) > 0.1:
                report.impactful_modules.append(mod_name)
                
        except Exception as e:
            print(f"  ERROR: {e}")
    
    # ── 3. Summary ──
    print(f"\n{'='*60}")
    print(f"ABLATION SUMMARY")
    print(f"{'='*60}")
    print(f"  Modules tested: {len(report.results)}")
    print(f"  Impactful (changed threat/gate or >10% confidence): {len(report.impactful_modules)}")
    
    if report.impactful_modules:
        print(f"  Key modules: {', '.join(report.impactful_modules)}")
    else:
        print(f"  No single module dramatically changed the output — architecture is robust")
    
    return report


def print_ablation_report(report: AblationReport) -> str:
    """Format ablation report as string."""
    lines: List[str] = []
    lines.append("=" * 70)
    lines.append("  DIP 2.0 — ABLATION STUDY REPORT")
    lines.append("=" * 70)
    lines.append(f"  Query: {report.query[:60]}")
    lines.append(f"  Country: {report.country_code}")
    lines.append(f"  Baseline Threat: {report.baseline_threat}")
    lines.append(f"  Baseline Confidence: {report.baseline_confidence:.3f}")
    lines.append("")
    lines.append("-" * 70)
    lines.append(f"  {'Module':<25s} {'ΔThreat':<10s} {'ΔGate':<8s} {'ΔConf':<10s} {'ΔHyp':<8s} {'ΔEvid':<8s}")
    lines.append("-" * 70)
    
    for r in report.results:
        t = "CHANGED" if r.threat_level_changed else "same"
        g = "CHANGED" if r.gate_verdict_changed else "same"
        lines.append(
            f"  {r.module_name:<25s} {t:<10s} {g:<8s} "
            f"{r.confidence_delta:+.4f}   {r.hypothesis_count_delta:+4d}    {r.evidence_count_delta:+4d}"
        )
    
    lines.append("-" * 70)
    lines.append("")
    
    if report.impactful_modules:
        lines.append(f"  ⚠ Modules with measurable impact: {', '.join(report.impactful_modules)}")
        lines.append(f"  These modules should be KEPT — removing them changes outputs.")
    else:
        lines.append(f"  ✓ No single module dramatically changed outputs — architecture shows redundancy.")
    
    lines.append("=" * 70)
    return "\n".join(lines)


def export_ablation_json(report: AblationReport, path: Optional[Path] = None) -> Path:
    """Export ablation report as JSON."""
    if path is None:
        path = Path(__file__).resolve().parent.parent / "data" / "ablation_report.json"
    
    data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "query": report.query,
        "country_code": report.country_code,
        "baseline_threat": report.baseline_threat,
        "baseline_confidence": report.baseline_confidence,
        "impactful_modules": report.impactful_modules,
        "results": [
            {
                "module": r.module_name,
                "description": r.module_description,
                "threat_level_changed": r.threat_level_changed,
                "confidence_delta": r.confidence_delta,
                "hypothesis_count_delta": r.hypothesis_count_delta,
                "evidence_count_delta": r.evidence_count_delta,
                "verification_score_delta": r.verification_score_delta,
                "gate_verdict_changed": r.gate_verdict_changed,
                "elapsed_delta": r.elapsed_delta,
            }
            for r in report.results
        ],
    }
    
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    return path
