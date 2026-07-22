"""
Latency & Throughput Dashboard — DIP 2.1 Validation Suite

Aggregates per-step timing data from the step tracer and produces:
  - Per-layer latency breakdown
  - Throughput (queries/minute)
  - Bottleneck identification
  - Timeline visualization data

Reads from data/traces/ for historical data and can run live benchmarks.
"""

from __future__ import annotations

import json
import statistics
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ── Layer definitions for aggregation ────────────────────────────

LAYER_MAP = {
    "START": ("Layer 0", "Pipeline Init"),
    "COLLECTION": ("Layer 1", "Data Collection"),
    "SRE_COMPUTATION": ("Layer 3", "Strategic Risk Engine"),
    "COUNCIL": ("Layer 4", "Council of Ministers"),
    "ASSESSMENT_GATE": ("Layer 5", "Assessment Gate"),
    "TRAJECTORY": ("Layer 5", "Trajectory Forecast"),
    "BRIEFING": ("Layer 6", "Executive Briefing"),
    "NARRATIVE": ("Layer 6", "Strategic Narrative"),
    "LEARNING": ("Layer 6", "Learning Engine"),
    "CONTAGION": ("Layer 7", "Global Contagion"),
}

LAYER_ORDER = [
    "Layer 0",
    "Layer 1",
    "Layer 2",
    "Layer 3",
    "Layer 4",
    "Layer 5",
    "Layer 6",
    "Layer 7",
]


@dataclass
class StepTiming:
    """Timing for a single pipeline step."""
    step_name: str
    source_file: str
    timestamp: str
    elapsed_from_start: float
    step_duration: float = 0.0  # Computed from adjacent steps


@dataclass
class LayerTiming:
    """Aggregate timing for one layer."""
    layer: str
    layer_name: str
    total_duration: float
    avg_duration: float
    min_duration: float
    max_duration: float
    call_count: int
    p50: float
    p95: float
    p99: float
    percent_of_total: float


@dataclass
class LatencyReport:
    """Full latency analysis report."""
    trace_id: str = ""
    total_duration: float = 0.0
    step_count: int = 0
    layer_timings: List[LayerTiming] = field(default_factory=list)
    bottleneck_layer: str = ""
    bottleneck_pct: float = 0.0
    generated_at: str = ""


def parse_trace_file(trace_dir: Path) -> List[StepTiming]:
    """
    Parse all step JSON files from a trace directory.
    
    Expected files: 0001_START.json, 0002_COLLECTION.json, etc.
    """
    steps: List[StepTiming] = []
    
    if not trace_dir.exists():
        return steps
    
    json_files = sorted(trace_dir.glob("[0-9]*_*.json"))
    
    for jf in json_files:
        try:
            with open(jf, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            steps.append(StepTiming(
                step_name=data.get("step", "UNKNOWN"),
                source_file=data.get("source_file", ""),
                timestamp=data.get("timestamp", ""),
                elapsed_from_start=data.get("elapsed_from_start", 0.0),
            ))
        except (json.JSONDecodeError, KeyError):
            continue
    
    # Compute step durations from adjacent elapsed_from_start values
    for i in range(len(steps)):
        if i < len(steps) - 1:
            steps[i].step_duration = round(
                steps[i + 1].elapsed_from_start - steps[i].elapsed_from_start, 3
            )
        else:
            # Last step — use its own elapsed as duration estimate
            steps[i].step_duration = steps[i].elapsed_from_start if len(steps) == 1 else 0.0
    
    return steps


def aggregate_layer_timings(steps: List[StepTiming], total_duration: float) -> List[LayerTiming]:
    """
    Aggregate individual step timings into per-layer statistics.
    """
    layer_steps: Dict[str, List[float]] = defaultdict(list)
    layer_names: Dict[str, str] = {}
    
    for step in steps:
        layer_info = LAYER_MAP.get(step.step_name, ("Unknown", step.step_name))
        layer_id = layer_info[0]
        layer_name = layer_info[1]
        
        layer_steps[layer_id].append(step.step_duration)
        layer_names[layer_id] = layer_name
    
    layer_timings: List[LayerTiming] = []
    
    for layer_id in LAYER_ORDER:
        durations = layer_steps.get(layer_id, [])
        if not durations:
            continue
        
        total = sum(durations)
        avg = statistics.mean(durations)
        sorted_d = sorted(durations)
        p50 = sorted_d[len(sorted_d) // 2]
        p95_idx = int(len(sorted_d) * 0.95)
        p99_idx = int(len(sorted_d) * 0.99)
        p95 = sorted_d[min(p95_idx, len(sorted_d) - 1)]
        p99 = sorted_d[min(p99_idx, len(sorted_d) - 1)]
        
        layer_timings.append(LayerTiming(
            layer=layer_id,
            layer_name=layer_names.get(layer_id, layer_id),
            total_duration=round(total, 3),
            avg_duration=round(avg, 3),
            min_duration=round(min(durations), 3),
            max_duration=round(max(durations), 3),
            call_count=len(durations),
            p50=round(p50, 3),
            p95=round(p95, 3),
            p99=round(p99, 3),
            percent_of_total=round(100 * total / total_duration, 1) if total_duration > 0 else 0.0,
        ))
    
    # Also handle unknown layers
    for layer_id in layer_steps:
        if layer_id not in LAYER_ORDER:
            durations = layer_steps[layer_id]
            total = sum(durations)
            layer_timings.append(LayerTiming(
                layer=layer_id,
                layer_name=layer_names.get(layer_id, layer_id),
                total_duration=round(total, 3),
                avg_duration=round(statistics.mean(durations), 3),
                min_duration=round(min(durations), 3),
                max_duration=round(max(durations), 3),
                call_count=len(durations),
                p50=round(sorted(durations)[len(durations) // 2], 3),
                p95=round(sorted(durations)[int(len(durations) * 0.95)], 3) if len(durations) > 1 else round(durations[0], 3),
                p99=round(sorted(durations)[int(len(durations) * 0.99)], 3) if len(durations) > 1 else round(durations[0], 3),
                percent_of_total=round(100 * total / total_duration, 1) if total_duration > 0 else 0.0,
            ))
    
    return layer_timings


def analyze_trace(trace_id: str) -> Optional[LatencyReport]:
    """
    Analyze a single trace directory for latency metrics.
    """
    traces_root = Path(__file__).resolve().parent.parent / "data" / "traces"
    trace_dir = traces_root / trace_id
    
    if not trace_dir.exists():
        return None
    
    steps = parse_trace_file(trace_dir)
    if not steps:
        return None
    
    total_duration = steps[-1].elapsed_from_start if steps else 0.0
    layer_timings = aggregate_layer_timings(steps, total_duration)
    
    # Find bottleneck
    bottleneck = max(layer_timings, key=lambda lt: lt.total_duration) if layer_timings else None
    
    return LatencyReport(
        trace_id=trace_id,
        total_duration=round(total_duration, 3),
        step_count=len(steps),
        layer_timings=layer_timings,
        bottleneck_layer=bottleneck.layer if bottleneck else "",
        bottleneck_pct=bottleneck.percent_of_total if bottleneck else 0.0,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


def analyze_all_traces() -> List[LatencyReport]:
    """Analyze all trace directories in data/traces/."""
    traces_root = Path(__file__).resolve().parent.parent / "data" / "traces"
    
    if not traces_root.exists():
        return []
    
    reports: List[LatencyReport] = []
    
    for trace_dir in sorted(traces_root.iterdir()):
        if not trace_dir.is_dir():
            continue
        
        report = analyze_trace(trace_dir.name)
        if report:
            reports.append(report)
    
    return reports


def aggregate_across_traces(reports: List[LatencyReport]) -> Dict[str, Any]:
    """
    Aggregate latency metrics across multiple traces.
    
    Returns stats useful for throughput and stability analysis.
    """
    if not reports:
        return {"error": "No trace reports available"}
    
    total_durations = [r.total_duration for r in reports]
    step_counts = [r.step_count for r in reports]
    
    # Per-layer aggregation
    layer_aggs: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))
    
    for report in reports:
        for lt in report.layer_timings:
            layer_aggs[lt.layer]["total"].append(lt.total_duration)
            layer_aggs[lt.layer]["avg"].append(lt.avg_duration)
            layer_aggs[lt.layer]["pct"].append(lt.percent_of_total)
    
    aggregated_layers = {}
    for layer_id, metrics in layer_aggs.items():
        aggregated_layers[layer_id] = {
            "avg_total_ms": round(statistics.mean(metrics["total"]) * 1000, 1),
            "avg_pct": round(statistics.mean(metrics["pct"]), 1),
            "count": len(metrics["total"]),
        }
    
    # Identify persistent bottlenecks
    bottleneck_counts = defaultdict(int)
    for report in reports:
        if report.bottleneck_layer:
            bottleneck_counts[report.bottleneck_layer] += 1
    
    return {
        "traces_analyzed": len(reports),
        "avg_total_duration_s": round(statistics.mean(total_durations), 2),
        "min_duration_s": round(min(total_durations), 2),
        "max_duration_s": round(max(total_durations), 2),
        "p50_duration_s": round(sorted(total_durations)[len(total_durations) // 2], 2),
        "avg_step_count": round(statistics.mean(step_counts), 1),
        "throughput_per_minute": round(60 / statistics.mean(total_durations), 2) if total_durations else 0,
        "layer_breakdown": aggregated_layers,
        "persistent_bottleneck": max(bottleneck_counts, key=bottleneck_counts.get, default=""),
        "bottleneck_frequency": max(bottleneck_counts.values(), default=0) / len(reports) if reports else 0,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def print_latency_report(report: LatencyReport) -> str:
    """Format a single trace latency report."""
    lines: List[str] = []
    lines.append("=" * 70)
    lines.append(f"  DIP 2.0 — LATENCY REPORT (Trace: {report.trace_id})")
    lines.append("=" * 70)
    lines.append(f"  Total Duration: {report.total_duration:.3f}s")
    lines.append(f"  Steps: {report.step_count}")
    lines.append("")
    lines.append("-" * 70)
    lines.append(f"  {'Layer':<12s} {'Name':<25s} {'Total':<9s} {'Avg':<9s} {'P50':<9s} {'P95':<9s} {'%':<6s} {'Calls':<6s}")
    lines.append("-" * 70)
    
    for lt in report.layer_timings:
        lines.append(
            f"  {lt.layer:<12s} {lt.layer_name:<25s} {lt.total_duration:<9.3f} "
            f"{lt.avg_duration:<9.3f} {lt.p50:<9.3f} {lt.p95:<9.3f} "
            f"{lt.percent_of_total:<5.1f}% {lt.call_count:<6d}"
        )
    
    lines.append("-" * 70)
    lines.append("")
    lines.append(f"  [BOTTLENECK] BOTTLENECK: {report.bottleneck_layer} ({report.bottleneck_pct:.1f}% of total)")
    lines.append("=" * 70)
    
    return "\n".join(lines)


def print_aggregate_latency(agg: Dict[str, Any]) -> str:
    """Format aggregate latency analysis."""
    lines: List[str] = []
    lines.append("=" * 70)
    lines.append("  DIP 2.0 — AGGREGATE LATENCY ANALYSIS")
    lines.append("=" * 70)
    lines.append(f"  Traces Analyzed:   {agg.get('traces_analyzed', 0)}")
    lines.append(f"  Avg Duration:      {agg.get('avg_total_duration_s', 0):.2f}s")
    lines.append(f"  Min/Max Duration:  {agg.get('min_duration_s', 0):.2f}s / {agg.get('max_duration_s', 0):.2f}s")
    lines.append(f"  P50 Duration:      {agg.get('p50_duration_s', 0):.2f}s")
    lines.append(f"  Throughput:        {agg.get('throughput_per_minute', 0):.1f} queries/min")
    lines.append("")
    
    layer_breakdown = agg.get("layer_breakdown", {})
    if layer_breakdown:
        lines.append("  Layer Breakdown (avg across all traces):")
        for layer_id in LAYER_ORDER:
            if layer_id in layer_breakdown:
                lb = layer_breakdown[layer_id]
                lines.append(f"    {layer_id:<12s} — {lb['avg_total_ms']:>7.1f}ms ({lb['avg_pct']:>5.1f}%)")
    
    lines.append("")
    bottleneck = agg.get("persistent_bottleneck", "")
    bottleneck_freq = agg.get("bottleneck_frequency", 0)
    if bottleneck:
        lines.append(f"  [BOTTLENECK] Persistent Bottleneck: {bottleneck} ({bottleneck_freq:.0%} of traces)")
        lines.append(f"     → Consider optimizing or parallelizing this layer")
    
    lines.append("=" * 70)
    return "\n".join(lines)


def export_latency_json(path: Optional[Path] = None) -> Path:
    """Export aggregate latency report as JSON."""
    if path is None:
        path = Path(__file__).resolve().parent.parent / "data" / "latency_report.json"
    
    reports = analyze_all_traces()
    agg = aggregate_across_traces(reports)
    
    data = {
        **agg,
        "individual_traces": [
            {
                "trace_id": r.trace_id,
                "total_duration": r.total_duration,
                "step_count": r.step_count,
                "bottleneck": r.bottleneck_layer,
                "layers": [
                    {"layer": lt.layer, "name": lt.layer_name, "total_s": lt.total_duration,
                     "avg_s": lt.avg_duration, "pct": lt.percent_of_total}
                    for lt in r.layer_timings
                ],
            }
            for r in reports
        ],
    }
    
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    return path
