"""Run a real-world pipeline test."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from Config.pipeline import run_query_sync


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a real-world Layer-4 pipeline query.")
    parser.add_argument(
        "--query",
        default="What factors indicate conflict escalation risk between China and Taiwan?",
        help="Query to execute.",
    )
    parser.add_argument(
        "--country",
        default="CHN",
        help="ISO-like country code used for Layer-3 state build.",
    )
    parser.add_argument(
        "--as-of-date",
        default=None,
        help="Optional YYYY-MM-DD runtime date override (historical replay).",
    )
    parser.add_argument(
        "--probe-llm",
        action="store_true",
        help="Run a one-token connectivity probe to local LLM before pipeline execution.",
    )
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    llm_probe = None

    if bool(args.probe_llm):
        from engine.Layer4_Analysis.core.llm_client import LocalLLM

        llm = LocalLLM()
        llm_probe = llm.generate(
            system_prompt="Reply with a single token: OK",
            user_prompt="Connection check",
            temperature=0.0,
            timeout=120,
        )

    result = run_query_sync(
        query=str(args.query or ""),
        country_code=str(args.country or "UNKNOWN"),
        as_of_date=str(args.as_of_date) if args.as_of_date else None,
        use_red_team=True,
        use_mcts=False,
        max_investigation_loops=2,
    )

    if llm_probe is not None:
        print("LLM PROBE:", str(llm_probe)[:120].replace("\n", " "))
    print("FINAL DECISION:")
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
