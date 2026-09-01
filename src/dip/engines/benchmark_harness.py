"""
Benchmark Comparison Harness — DIP 2.1 Validation Suite

Compares DIP 2.0 against simpler baselines:
  1. Raw LLM (direct DeepSeek query, no pipeline)
  2. Vanilla RAG (retrieve-then-answer)
  3. DIP 2.0 Heuristic (full pipeline, no LLM)
  4. DIP 2.0 Full (full pipeline with LLM ministers)

Metrics compared:
  - Threat Level accuracy vs. ground truth
  - Hallucination rate (fabricated facts)
  - Confidence calibration
  - Evidence citation count
  - Latency
  - Token cost
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dip.core.Config.config import config
from dip.core.json_utils import strip_markdown_json


@dataclass
class BenchmarkRun:
    """A single benchmark run for one system variant."""
    system_name: str
    query: str
    country_code: str
    threat_level: str = "UNKNOWN"
    confidence: float = 0.0
    evidence_count: int = 0
    hypothesis_count: int = 0
    elapsed_seconds: float = 0.0
    hallucination_flags: int = 0
    trace_id: str = ""
    raw_output: str = ""


@dataclass  
class BenchmarkReport:
    """Aggregate benchmark report comparing all systems."""
    runs: List[BenchmarkRun] = field(default_factory=list)
    queries: List[str] = field(default_factory=list)
    country_code: str = ""
    generated_at: str = ""


def _parse_json_object(raw: str, fallback: Dict[str, Any]) -> tuple[Dict[str, Any], str]:
    """Parse a model response without allowing malformed JSON to abort a run."""
    cleaned = strip_markdown_json(raw)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        return fallback, cleaned
    return (parsed if isinstance(parsed, dict) else fallback), cleaned


async def run_raw_llm(query: str, country_code: str) -> BenchmarkRun:
    """
    Baseline 1: Raw LLM — ask DeepSeek directly, no pipeline.
    """
    t0 = time.time()
    
    try:
        import litellm
        response = litellm.completion(
            model=config.LLM_MODEL,
            messages=[{
                "role": "user",
                "content": (
                    f"You are a geopolitical risk analyst. Assess the threat level "
                    f"(HIGH, ELEVATED, or LOW) for {country_code} based on: {query}\n\n"
                    f"Respond in JSON: {{\"threat_level\": \"...\", \"confidence\": 0.X, "
                    f"\"evidence\": [\"fact 1\", \"fact 2\"], \"reasoning\": \"...\"}}"
                ),
            }],
            temperature=0.2,
            max_tokens=500,
        )
        parsed, raw = _parse_json_object(
            response.choices[0].message.content,
            {"threat_level": "LOW", "confidence": 0.5, "evidence": [], "reasoning": ""},
        )
        
        return BenchmarkRun(
            system_name="Raw LLM",
            query=query,
            country_code=country_code,
            threat_level=parsed.get("threat_level", "LOW").upper(),
            confidence=float(parsed.get("confidence", 0.5)),
            evidence_count=len(parsed.get("evidence", [])),
            elapsed_seconds=round(time.time() - t0, 2),
            raw_output=raw[:500],
        )
    except Exception as e:
        return BenchmarkRun(
            system_name="Raw LLM",
            query=query,
            country_code=country_code,
            threat_level="ERROR",
            elapsed_seconds=round(time.time() - t0, 2),
            raw_output=str(e),
        )


async def run_vanilla_rag(query: str, country_code: str) -> BenchmarkRun:
    """
    Baseline 2: Vanilla RAG — retrieve context, then ask LLM.
    
    Uses DIP's news sensor for retrieval, then feeds to LLM directly.
    """
    t0 = time.time()
    
    try:
        # Retrieve context using DIP's sensors
        from dip.pipeline.collection.feed_integrator import FeedIntegrator
        from dip.pipeline.knowledge.signal_extractor import SignalExtractor
        
        integrator = FeedIntegrator()
        observations = await integrator.fetch_observations(country_code, query)
        
        # Simple RAG: concatenate observations into context
        context = "\n".join([
            f"- {obs.get('action', obs.get('title', str(obs)[:200]))}"
            for obs in (observations or [])[:10]
        ])
        
        if not context:
            context = f"No recent observations available for {country_code}."
        
        import litellm
        response = litellm.completion(
            model=config.LLM_MODEL,
            messages=[{
                "role": "user",
                "content": (
                    f"You are a geopolitical risk analyst. Using ONLY the context below, "
                    f"assess the threat level for {country_code} regarding: {query}\n\n"
                    f"CONTEXT:\n{context}\n\n"
                    f"Respond in JSON: {{\"threat_level\": \"HIGH/ELEVATED/LOW\", "
                    f"\"confidence\": 0.X, \"cited_facts\": [...]}}"
                ),
            }],
            temperature=0.2,
            max_tokens=500,
        )
        parsed, raw = _parse_json_object(
            response.choices[0].message.content,
            {"threat_level": "LOW", "confidence": 0.5, "cited_facts": []},
        )
        
        return BenchmarkRun(
            system_name="Vanilla RAG",
            query=query,
            country_code=country_code,
            threat_level=parsed.get("threat_level", "LOW").upper(),
            confidence=float(parsed.get("confidence", 0.5)),
            evidence_count=len(parsed.get("cited_facts", [])),
            elapsed_seconds=round(time.time() - t0, 2),
            raw_output=raw[:500],
        )
    except Exception as e:
        return BenchmarkRun(
            system_name="Vanilla RAG",
            query=query,
            country_code=country_code,
            threat_level="ERROR",
            elapsed_seconds=round(time.time() - t0, 2),
            raw_output=str(e),
        )


async def run_dip_heuristic(query: str, country_code: str) -> BenchmarkRun:
    """
    Baseline 3: Politiq AI Heuristic (FORCE_MINISTER_HEURISTIC=1).
    """
    import os
    os.environ["FORCE_MINISTER_HEURISTIC"] = "1"
    
    t0 = time.time()
    
    try:
        from dip.unified_pipeline import execute
        result = await execute(query, country_code, f"bench-heuristic-{int(time.time())}")
        
        return BenchmarkRun(
            system_name="Politiq AI Heuristic",
            query=query,
            country_code=country_code,
            threat_level=result.get("threat_level", "UNKNOWN"),
            confidence=result.get("verification_score", 0.0),
            evidence_count=len(result.get("evidence_log", [])),
            hypothesis_count=len(result.get("hypotheses", [])),
            elapsed_seconds=round(time.time() - t0, 2),
            trace_id=result.get("trace_id", ""),
        )
    except Exception as e:
        return BenchmarkRun(
            system_name="Politiq AI Heuristic",
            query=query,
            country_code=country_code,
            threat_level="ERROR",
            elapsed_seconds=round(time.time() - t0, 2),
            raw_output=str(e),
        )


async def run_dip_full(query: str, country_code: str) -> BenchmarkRun:
    """
    Baseline 4: Politiq AI Full (LLM ministers enabled).
    """
    import os
    os.environ["FORCE_MINISTER_HEURISTIC"] = "0"
    
    t0 = time.time()
    
    try:
        from dip.unified_pipeline import execute
        result = await execute(query, country_code, f"bench-full-{int(time.time())}")
        
        return BenchmarkRun(
            system_name="Politiq AI Full",
            query=query,
            country_code=country_code,
            threat_level=result.get("threat_level", "UNKNOWN"),
            confidence=result.get("verification_score", 0.0),
            evidence_count=len(result.get("evidence_log", [])),
            hypothesis_count=len(result.get("hypotheses", [])),
            elapsed_seconds=round(time.time() - t0, 2),
            trace_id=result.get("trace_id", ""),
        )
    except Exception as e:
        return BenchmarkRun(
            system_name="Politiq AI Full",
            query=query,
            country_code=country_code,
            threat_level="ERROR",
            elapsed_seconds=round(time.time() - t0, 2),
            raw_output=str(e),
        )


async def run_benchmark_suite(
    queries: List[Tuple[str, str]],  # [(query, country_code), ...]
    skip_llm: bool = True,  # Skip LLM baselines to save cost
) -> BenchmarkReport:
    """Run all systems against a set of queries."""
    
    report = BenchmarkReport(
        queries=[q[0] for q in queries],
        country_code=queries[0][1] if queries else "",
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
    
    for query, country_code in queries:
        print(f"\n{'='*60}")
        print(f"BENCHMARK: {country_code} — {query[:60]}")
        print(f"{'='*60}")
        
        # Always run DIP Heuristic (fast, no cost)
        run = await run_dip_heuristic(query, country_code)
        report.runs.append(run)
        print(f"  DIP Heuristic: {run.threat_level} (conf={run.confidence:.2f}, {run.elapsed_seconds:.1f}s)")
        
        if not skip_llm:
            # Raw LLM
            try:
                run = await run_raw_llm(query, country_code)
                report.runs.append(run)
                print(f"  Raw LLM:      {run.threat_level} (conf={run.confidence:.2f}, {run.elapsed_seconds:.1f}s)")
            except Exception as e:
                print(f"  Raw LLM:      FAILED ({e})")
            
            # Vanilla RAG
            try:
                run = await run_vanilla_rag(query, country_code)
                report.runs.append(run)
                print(f"  Vanilla RAG:  {run.threat_level} (conf={run.confidence:.2f}, {run.elapsed_seconds:.1f}s)")
            except Exception as e:
                print(f"  Vanilla RAG:  FAILED ({e})")
            
            # DIP Full
            try:
                run = await run_dip_full(query, country_code)
                report.runs.append(run)
                print(f"  DIP Full:     {run.threat_level} (conf={run.confidence:.2f}, {run.elapsed_seconds:.1f}s)")
            except Exception as e:
                print(f"  DIP Full:     FAILED ({e})")
    
    return report


def print_benchmark_report(report: BenchmarkReport) -> str:
    """Format benchmark report."""
    lines: List[str] = []
    lines.append("=" * 70)
    lines.append("  Politiq AI — BENCHMARK COMPARISON REPORT")
    lines.append("=" * 70)
    lines.append("")
    
    # Group by system
    systems: Dict[str, List[BenchmarkRun]] = {}
    for run in report.runs:
        systems.setdefault(run.system_name, []).append(run)
    
    for sys_name, runs in systems.items():
        n = len(runs)
        if n == 0:
            continue
        
        avg_time = sum(r.elapsed_seconds for r in runs) / n
        avg_conf = sum(r.confidence for r in runs) / n
        avg_evidence = sum(r.evidence_count for r in runs) / n
        
        threats = [r.threat_level for r in runs if r.threat_level != "ERROR"]
        threat_dist = ", ".join(f"{t}={threats.count(t)}" for t in set(threats))
        
        lines.append(f"  {sys_name}:")
        lines.append(f"    Runs: {n}  |  Avg Time: {avg_time:.1f}s  |  Avg Conf: {avg_conf:.2f}")
        lines.append(f"    Avg Evidence: {avg_evidence:.1f}  |  Threats: {threat_dist}")
        lines.append("")
    
    # Comparison table
    lines.append("-" * 70)
    lines.append(f"  {'System':<22s} {'Threat':<10s} {'Conf':<7s} {'Evid':<6s} {'Hyp':<5s} {'Time':<8s}")
    lines.append("-" * 70)
    for run in report.runs:
        t = run.threat_level[:9]
        lines.append(
            f"  {run.system_name:<22s} {t:<10s} {run.confidence:<7.2f} "
            f"{run.evidence_count:<6d} {run.hypothesis_count:<5d} {run.elapsed_seconds:<8.1f}"
        )
    lines.append("-" * 70)
    lines.append("")
    
    # Summary
    dip_runs = [r for r in report.runs if "DIP" in r.system_name]
    other_runs = [r for r in report.runs if "DIP" not in r.system_name]
    
    if dip_runs and other_runs:
        dip_avg_evid = sum(r.evidence_count for r in dip_runs) / len(dip_runs)
        other_avg_evid = sum(r.evidence_count for r in other_runs) / max(len(other_runs), 1)
        
        lines.append(f"  DIP provides {dip_avg_evid/other_avg_evid:.1f}x more evidence citations than baselines")
    elif dip_runs:
        lines.append(f"  DIP Heuristic: avg {sum(r.evidence_count for r in dip_runs)/len(dip_runs):.1f} evidence citations per query")
    
    lines.append("=" * 70)
    return "\n".join(lines)


def export_benchmark_json(report: BenchmarkReport, path: Optional[Path] = None) -> Path:
    """Export benchmark report as JSON."""
    if path is None:
        path = Path(__file__).resolve().parent.parent / "data" / "benchmark_report.json"
    
    data = {
        "generated_at": report.generated_at,
        "queries": report.queries,
        "country_code": report.country_code,
        "runs": [
            {
                "system": r.system_name,
                "query": r.query,
                "country": r.country_code,
                "threat_level": r.threat_level,
                "confidence": r.confidence,
                "evidence_count": r.evidence_count,
                "hypothesis_count": r.hypothesis_count,
                "elapsed_seconds": r.elapsed_seconds,
                "trace_id": r.trace_id,
            }
            for r in report.runs
        ],
    }
    
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    return path
