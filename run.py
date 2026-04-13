"""
IND-Diplomat — Enhanced Entry Point
========================================
Key capabilities:
  1. Pre-checks Ollama before pipeline — clear error instead of 8x retry spam
  2. Shows full intelligence briefing (not just WITHHELD summary)
  3. Structured logging with proper formatting
  4. Execution log captured + --verbose flag
  5. Experiment runner built in (--experiment flag)

Usage (CLI)::

    python run.py "What is driving India-Pakistan tensions?"
    python run.py --country IND --date 2025-06-01 "Assess China-Taiwan risk"
    python run.py --verbose "Why is China near Taiwan?"
    python run.py --experiment all

Usage (import)::

    from run import diplomat_query, diplomat_query_sync
    result = await diplomat_query("Why is India …?", country_code="IND")
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re
import sys
import threading
import textwrap
import time
from dataclasses import asdict, dataclass, field, is_dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from Config.config import (
    LLM_MODEL,
    LLM_PROVIDER,
    OLLAMA_BASE_URL,
    OPENROUTER_API_KEY,
    OPENROUTER_MODEL,
    OPENROUTER_URL,
)

# ── Bootstrap ─────────────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parent

# Safe UTF-8 output on Windows
try:
    sys.stdout.reconfigure(errors="replace")
    sys.stderr.reconfigure(errors="replace")
except Exception:
    pass


# ── Logging ───────────────────────────────────────────────────────────
def _setup_logging(level: str = "INFO") -> None:
    """Configure structured logging with timestamps."""
    fmt = "%(asctime)s [%(name)s] %(levelname)s %(message)s"
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=fmt,
        datefmt="%H:%M:%S",
        stream=sys.stderr,
        force=True,
    )
    for name in ("httpx", "httpcore", "urllib3", "chromadb", "sentence_transformers"):
        logging.getLogger(name).setLevel(logging.WARNING)


_log = logging.getLogger("IND_Diplomat")

_SENSITIVE_KEY_MARKERS = {
    "api",
    "apikey",
    "auth",
    "authorization",
    "authtoken",
    "bearer",
    "credential",
    "jwt",
    "key",
    "openrouterapikey",
    "password",
    "privatekey",
    "refreshtoken",
    "secret",
    "token",
}


def _normalize_key_name(raw_key: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(raw_key).strip().lower())


def _is_sensitive_key(raw_key: str) -> bool:
    normalized = _normalize_key_name(raw_key)
    if not normalized:
        return False
    if normalized in _SENSITIVE_KEY_MARKERS:
        return True
    for marker in (
        "apikey",
        "authtoken",
        "accesstoken",
        "refreshtoken",
        "bearertoken",
        "privatekey",
        "secret",
        "password",
        "credential",
        "jwt",
    ):
        if marker in normalized:
            return True
    return False


def _env_truthy(name: str, default: bool = False) -> bool:
    token = str(os.getenv(name, "1" if default else "0")).strip().lower()
    return token in {"1", "true", "yes", "on"}


def _json_safe(value: Any, *, _depth: int = 0, _max_depth: int = 8) -> Any:
    if _depth >= _max_depth:
        return str(value)

    if isinstance(value, (str, int, float, bool, type(None))):
        return value

    if is_dataclass(value):
        return _json_safe(asdict(value), _depth=_depth + 1, _max_depth=_max_depth)

    if isinstance(value, dict):
        out: Dict[str, Any] = {}
        for k, v in value.items():
            key = str(k)
            if _is_sensitive_key(key):
                out[key] = "***REDACTED***"
            else:
                out[key] = _json_safe(v, _depth=_depth + 1, _max_depth=_max_depth)
        return out

    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v, _depth=_depth + 1, _max_depth=_max_depth) for v in value]

    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        try:
            return _json_safe(to_dict(), _depth=_depth + 1, _max_depth=_max_depth)
        except Exception:
            pass

    if hasattr(value, "__dict__"):
        raw = {k: v for k, v in vars(value).items() if not str(k).startswith("_")}
        return _json_safe(raw, _depth=_depth + 1, _max_depth=_max_depth)

    return str(value)


def _read_tail(path: Path, max_chars: int = 30000) -> str:
    try:
        if not path.exists():
            return ""
        text = path.read_text(encoding="utf-8", errors="replace")
        if len(text) <= int(max_chars):
            return text
        return text[-int(max_chars):]
    except Exception:
        return ""


def _llm_runtime_payload() -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    try:
        from engine.Layer4_Analysis.core.llm_client import get_llm_runtime_stats, llm_client

        payload["stats"] = _json_safe(get_llm_runtime_stats())
        payload["routing"] = _json_safe(llm_client.health())
    except Exception as exc:
        payload["error"] = f"llm_runtime_unavailable: {exc}"
    return payload


def _llm_trace_payload() -> Dict[str, Any]:
    default_trace_path = _ROOT / "runtime" / "llm_trace.txt"
    trace_path = Path(str(os.getenv("LLM_TRACE_PATH", str(default_trace_path)) or str(default_trace_path)))
    tail_chars = int(str(os.getenv("LLM_TRACE_TAIL_CHARS", "30000")).strip() or "30000")
    trace_enabled = _env_truthy("LLM_TRACE_ENABLED", default=False)
    trace_tail = _read_tail(trace_path, max_chars=max(1000, tail_chars))
    payload = {
        "enabled": trace_enabled,
        "path": str(trace_path),
        "exists": bool(trace_path.exists()),
        "tail_chars": max(1000, tail_chars),
        "tail": trace_tail,
    }
    if not trace_tail:
        payload["note"] = (
            "No trace content captured yet. Set LLM_TRACE_ENABLED=1 to record prompt/response traces."
        )
    return payload


# ── Path verification ────────────────────────────────────────────────
from project_root import verify_paths as _verify_paths  # noqa: E402

_path_status = _verify_paths(loud=False)
if not _path_status.get("GLOBAL_RISK_DIR"):
    _log.warning(
        "GLOBAL_RISK_DIR is MISSING — dataset providers will return empty "
        "results.  Run `python project_root.py` to diagnose."
    )


# ── Ollama health check ──────────────────────────────────────────────
# ── Result dataclass ──────────────────────────────────────────────────
def _check_ollama() -> dict:
    """
    Backward-compatible LLM health check used by the web/UI surfaces.
    Supports Ollama and temporary OpenRouter testing through env vars.
    """
    import urllib.request
    import urllib.error

    provider = str(LLM_PROVIDER or "ollama").strip().lower() or "ollama"
    default_model = str(os.getenv("LAYER4_MODEL", LLM_MODEL or "")).strip() or "unconfigured-model"
    result = {"ok": False, "provider": provider, "model": default_model, "error": ""}

    if provider == "openrouter":
        api_key = str(OPENROUTER_API_KEY or "").strip()
        base_url = str(OPENROUTER_URL or "https://openrouter.ai/api/v1/chat/completions").strip()
        models_url = base_url.rsplit("/", 2)[0] + "/models"
        result["endpoint"] = models_url
        result["model"] = str(OPENROUTER_MODEL or default_model).strip() or default_model

        if not api_key:
            result["error"] = "OPENROUTER_API_KEY is not configured"
            return result

        try:
            req = urllib.request.Request(
                models_url,
                method="GET",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                models = [m.get("id", "") for m in data.get("data", []) if isinstance(m, dict)]
                result["ok"] = resp.status < 400
                result["model_listed"] = result["model"] in models if models else None
                result["available_models"] = len(models)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            result["error"] = f"OpenRouter error {exc.code}: {detail[:200]}"
        except urllib.error.URLError as exc:
            result["error"] = f"OpenRouter not reachable at {models_url} - {exc.reason}"
        except Exception as exc:
            result["error"] = f"OpenRouter check failed: {exc}"
        return result

    base_url = str(OLLAMA_BASE_URL or "http://localhost:11434").strip()
    result["endpoint"] = f"{base_url}/api/tags"

    try:
        req = urllib.request.Request(f"{base_url}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            models = [m.get("name", "") for m in data.get("models", [])]
            result["ok"] = True
            result["model"] = ", ".join(models[:3]) if models else "no models loaded"
    except urllib.error.URLError as exc:
        result["error"] = f"Ollama not reachable at {base_url} - {exc.reason}"
    except Exception as exc:
        result["error"] = f"Ollama check failed: {exc}"

    return result


@dataclass
class DiplomatResult:
    """Simplified result exposed to all callers."""

    outcome: str                              # ASSESSMENT | INSUFFICIENT_EVIDENCE | OUT_OF_SCOPE
    answer: str = ""
    confidence: float = 0.0
    risk_level: Optional[str] = None
    sources: List[Dict[str, Any]] = field(default_factory=list)
    operational_warnings: List[str] = field(default_factory=list)
    trace_id: str = ""
    briefing: str = ""                        # Full intelligence briefing
    run_log: List[str] = field(default_factory=list)  # Pipeline execution log
    elapsed_seconds: float = 0.0              # Wall-clock time
    _raw: Optional[Any] = field(default=None, repr=False)

    @property
    def raw(self) -> Optional[Any]:
        """Read-only accessor for underlying pipeline payload."""
        return self._raw

    def _whitebox_payload(self) -> Dict[str, Any]:
        raw_obj = _json_safe(self._raw)
        if not isinstance(raw_obj, dict):
            raw_obj = {"raw_repr": str(self._raw)}

        return {
            "outcome": self.outcome,
            "risk_level": self.risk_level,
            "confidence": round(self.confidence, 4),
            "trace_id": self.trace_id,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "answer_visible_to_user": self.answer,
            "briefing_visible_to_user": self.briefing,
            "sources_all": _json_safe(self.sources),
            "operational_warnings": _json_safe(self.operational_warnings),
            "run_log": _json_safe(self.run_log),
            "pipeline_raw": raw_obj,
            "gate_verdict": raw_obj.get("gate_verdict"),
            "council_session": raw_obj.get("council_session"),
            "intelligence_report": raw_obj.get("intelligence_report"),
            "layer4_scope": raw_obj.get("layer4_scope"),
            "layer4_readiness": raw_obj.get("layer4_readiness"),
            "llm_runtime": _llm_runtime_payload(),
            "llm_trace": _llm_trace_payload(),
        }

    def to_dict(
        self,
        *,
        whitebox: bool = False,
        include_run_log: bool = False,
        include_briefing: bool = False,
    ) -> Dict[str, Any]:
        payload = {
            "outcome": self.outcome,
            "answer": self.answer,
            "confidence": round(self.confidence, 4),
            "risk_level": self.risk_level,
            "sources": self.sources[:10],
            "operational_warnings": self.operational_warnings,
            "trace_id": self.trace_id,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
        }
        if include_run_log:
            payload["run_log"] = self.run_log
        if include_briefing:
            payload["briefing"] = self.briefing
        if whitebox:
            payload["whitebox"] = self._whitebox_payload()
        return payload


# ── Log capture ───────────────────────────────────────────────────────
class _LogCapture(logging.Handler):
    """Captures log records into a list for inclusion in results."""

    def __init__(self):
        super().__init__(level=logging.INFO)
        self.records: List[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self.records.append(msg)
        except Exception:
            pass


# ── Core query function ──────────────────────────────────────────────
async def diplomat_query(
    query: str,
    *,
    country_code: str = "UNKNOWN",
    as_of_date: Optional[str] = None,
    use_red_team: bool = True,
    use_mcts: bool = False,
    max_investigation_loops: int = 1,
    enable_system_guardian: bool = True,
    **extra_flags,
) -> DiplomatResult:
    """
    Run a query through the full IND-Diplomat pipeline.

    Returns a ``DiplomatResult`` with one of three outcomes:
        ``ASSESSMENT``, ``INSUFFICIENT_EVIDENCE``, ``OUT_OF_SCOPE``.
    """
    t0 = time.time()

    capture = _LogCapture()
    capture.setFormatter(logging.Formatter("%(asctime)s [%(name)s] %(levelname)s %(message)s", "%H:%M:%S"))
    root_logger = logging.getLogger()
    root_logger.addHandler(capture)

    try:
        from engine.Layer4_Analysis.core.unified_pipeline import (
            UnifiedPipeline,
            OUTCOME_ASSESSMENT,
            OUTCOME_INSUFFICIENT_EVIDENCE,
            OUTCOME_OUT_OF_SCOPE,
        )

        pipeline = UnifiedPipeline()
        result = await pipeline.execute(
            query=query,
            country_code=country_code,
            as_of_date=as_of_date,
            use_red_team=use_red_team,
            use_mcts=use_mcts,
            enable_red_team=use_red_team,
            enable_mcts=use_mcts,
            max_investigation_loops=max_investigation_loops,
            enable_system_guardian=enable_system_guardian,
            **extra_flags,
        )

        # Build full briefing from pipeline result
        briefing = ""
        try:
            from engine.Layer6_Presentation.report_builder import build_user_report
            briefing = build_user_report(
                {
                    "answer": result.answer,
                    "confidence": result.confidence,
                    "risk_level": result.risk_level,
                    "sources": result.sources,
                    "intelligence_report": result.intelligence_report,
                    "gate_verdict": result.gate_verdict,
                    "council_session": result.council_session,
                    "operational_warnings": result.operational_warnings,
                    "early_warning_index": result.early_warning_index,
                    "escalation_sync": result.escalation_sync,
                },
                gate_verdict=result.gate_verdict,
            )
        except Exception as e:
            _log.debug("Briefing generation failed: %s", e)
            briefing = result.answer

        elapsed = time.time() - t0

        return DiplomatResult(
            outcome=result.outcome,
            answer=result.answer,
            confidence=result.confidence,
            risk_level=result.risk_level,
            sources=result.sources or [],
            operational_warnings=result.operational_warnings or [],
            trace_id=result.trace_id,
            briefing=briefing,
            run_log=list(capture.records),
            elapsed_seconds=elapsed,
            _raw=result,
        )
    finally:
        root_logger.removeHandler(capture)


def diplomat_query_sync(query: str, **kwargs) -> DiplomatResult:
    """Synchronous wrapper for ``diplomat_query``."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(diplomat_query(query, **kwargs))

    result_holder: Dict[str, DiplomatResult] = {}
    error_holder: Dict[str, BaseException] = {}

    def _thread_main() -> None:
        try:
            result_holder["result"] = asyncio.run(diplomat_query(query, **kwargs))
        except BaseException as exc:
            error_holder["error"] = exc

    thread = threading.Thread(target=_thread_main, name="diplomat-query-sync", daemon=True)
    thread.start()
    thread.join()

    if "error" in error_holder:
        raise error_holder["error"]
    return result_holder["result"]


# ── Experiment runner ─────────────────────────────────────────────────
def _run_experiment(name: str) -> None:
    """Run one or all experiments from the analysis framework."""
    from analysis.experiments import (
        CrisisReplayExperiment,
        AblationExperiment,
        LeadTimeExperiment,
        print_full_report,
    )

    if name == "all":
        print_full_report()
        return

    if name == "replay":
        exp = CrisisReplayExperiment()
        results = exp.replay_all()
        exp.print_all_replays(results)
    elif name == "ablation":
        exp = AblationExperiment()
        for crisis in exp.timelines:
            report = exp.run_full_ablation(crisis)
            exp.print_ablation_report(report)
    elif name == "leadtime":
        exp = LeadTimeExperiment()
        for threshold in ["ELEVATED", "HIGH", "CRITICAL"]:
            report = exp.run_all_lead_times(threshold)
            exp.print_lead_time_report(report)
    else:
        print(f"Unknown experiment: {name}")
        print("Available: replay, ablation, leadtime, all")
        sys.exit(1)


# ── CLI ───────────────────────────────────────────────────────────────
def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run.py",
        description="IND-Diplomat: Geopolitical risk assessment engine.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            examples:
              python run.py "What is driving India-Pakistan tensions?"
              python run.py --country IND "Assess South Asian stability"
              python run.py --no-guardian --verbose "Why is China near Taiwan?"
              python run.py --experiment all
        """),
    )
    parser.add_argument(
        "query",
        nargs="?",
        default="What is driving India-Pakistan tensions?",
        help="Question to analyze.",
    )
    parser.add_argument("--country", "-c", default="UNKNOWN",
                        help="3-char country code (e.g. IND, CHN, USA).")
    parser.add_argument("--date", "-d", default=None,
                        help="As-of date YYYY-MM-DD for historical replay.")
    parser.add_argument("--no-guardian", action="store_true",
                        help="Skip operational health probe.")
    parser.add_argument("--no-red-team", action="store_true",
                        help="Disable the skeptic / red-team minister.")
    parser.add_argument("--mcts", action="store_true",
                        help="Enable MCTS hypothesis exploration.")
    parser.add_argument("--investigation-loops", type=int, default=1,
                        help="Max investigate/reconvene cycles.")
    parser.add_argument("--json", action="store_true",
                        help="Output full result as JSON.")
    parser.add_argument("--whitebox", action="store_true",
                        help="Include full transparent internals (LLM traces, gate data, council state) in JSON output.")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Show detailed pipeline execution log.")
    parser.add_argument("--brief", action="store_true",
                        help="Show only the quick summary (no full briefing).")
    parser.add_argument("--experiment", "-e", default=None,
                        choices=["replay", "ablation", "leadtime", "all"],
                        help="Run experimental validation instead of a query.")
    parser.add_argument("--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                        help="Log verbosity level.")
    return parser


def _print_result(result: DiplomatResult, *, as_json: bool = False,
                  verbose: bool = False, brief: bool = False, whitebox: bool = False) -> None:
    """Format and print the pipeline result."""
    if as_json:
        d = result.to_dict(
            whitebox=whitebox,
            include_run_log=verbose,
            include_briefing=not brief,
        )
        print(json.dumps(d, indent=2, ensure_ascii=False))
        return

    # ── Header ────────────────────────────────────────────────────
    outcome_icon = {
        "ASSESSMENT": "ASSESSMENT",
        "INSUFFICIENT_EVIDENCE": "INSUFFICIENT EVIDENCE",
        "OUT_OF_SCOPE": "OUT OF SCOPE",
    }.get(result.outcome, result.outcome)

    print(f"\n{'=' * 70}")
    print(f"  [{outcome_icon}]")
    print(f"{'=' * 70}")

    if result.risk_level:
        print(f"  Risk Level  : {result.risk_level}")
    print(f"  Confidence  : {result.confidence:.3f}")
    print(f"  Trace       : {result.trace_id}")
    print(f"  Elapsed     : {result.elapsed_seconds:.1f}s")

    if result.operational_warnings:
        print(f"\n  Operational warnings:")
        for w in result.operational_warnings:
            print(f"    * {w}")

    # ── Briefing ──────────────────────────────────────────────────
    if not brief and result.briefing:
        print(f"\n{'─' * 70}")
        print("  INTELLIGENCE BRIEFING")
        print(f"{'─' * 70}")
        for line in result.briefing.splitlines():
            print(f"  {line}")
        print(f"{'─' * 70}")
    elif result.answer:
        print(f"\n{'─' * 70}")
        answer_text = result.answer.strip()
        for line in answer_text.splitlines():
            for wrapped in textwrap.wrap(line, width=76) or [""]:
                print(f"  {wrapped}")
        print(f"{'─' * 70}")

    # ── Sources ───────────────────────────────────────────────────
    if result.sources:
        print(f"\n  Sources ({len(result.sources)}):")
        for i, src in enumerate(result.sources[:8], 1):
            name = src.get("source", src.get("id", "unknown"))
            score = src.get("score", "")
            print(f"    [{i}] {name}  (score: {score})")

    # ── Execution log (verbose mode) ──────────────────────────────
    if verbose and result.run_log:
        print(f"\n{'=' * 70}")
        print("  EXECUTION LOG")
        print(f"{'=' * 70}")
        for entry in result.run_log:
            print(f"  {entry}")

    print()


async def _async_main(args: argparse.Namespace) -> int:
    """Main async entry point."""
    _setup_logging(args.log_level)

    # ── Experiment mode ───────────────────────────────────────────
    if args.experiment:
        _run_experiment(args.experiment)
        return 0

    # ── Pre-flight: Check Ollama ──────────────────────────────────
    if not args.no_guardian:
        print("[IND-Diplomat] Checking configured LLM provider...")
        ollama = _check_ollama()
        provider_label = str(ollama.get("provider", "ollama")).upper()
        if ollama["ok"]:
            print(f"[IND-Diplomat] {provider_label} OK: {ollama['model']}")
        else:
            print(f"[IND-Diplomat] WARNING: {ollama['error']}")
            print("[IND-Diplomat] Pipeline will use pressure-based fallback (no LLM reasoning)")
            print()

    # ── Run query ─────────────────────────────────────────────────
    print(f"[IND-Diplomat] Query: {args.query}")
    print(f"[IND-Diplomat] Country: {args.country.upper()}")
    if args.date:
        print(f"[IND-Diplomat] As-of: {args.date}")
    print()

    result = await diplomat_query(
        query=args.query,
        country_code=args.country.upper(),
        as_of_date=args.date,
        use_red_team=not args.no_red_team,
        use_mcts=args.mcts,
        max_investigation_loops=args.investigation_loops,
        enable_system_guardian=not args.no_guardian,
    )

    whitebox_enabled = bool(args.whitebox or _env_truthy("DIPLOMAT_WHITEBOX_OUTPUT", default=True))
    _print_result(
        result,
        as_json=args.json,
        verbose=args.verbose,
        brief=args.brief,
        whitebox=whitebox_enabled,
    )
    return 0 if result.outcome == "ASSESSMENT" else 1


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    return asyncio.run(_async_main(args))


if __name__ == "__main__":
    raise SystemExit(main())
