from __future__ import annotations

import os
from pathlib import Path

from dip.nextgen.observability import observability
from dip.nextgen.langgraph_adapter import create_langgraph_adapter
from dip.nextgen.prefect_adapter import create_prefect_adapter
from dip.nextgen.stix2_adapter import create_stix2_adapter
from dip.nextgen.networkx_adapter import create_networkx_adapter
from dip.nextgen.crisis_replay import CrisisReplayBenchmark, ReplayCase


def main() -> int:
    print("DIP 2.0 next-gen enhancement check")
    print("OpenTelemetry enabled:", observability._tracer is not None)
    print("MLflow enabled:", observability._mlflow_active)

    print("LangGraph adapter:", "available" if create_langgraph_adapter() else "disabled/not installed")
    print("Prefect adapter:", "available" if create_prefect_adapter() else "disabled/not installed")
    print("STIX2 adapter:", "available" if create_stix2_adapter() else "disabled/not installed")
    print("NetworkX adapter:", "available" if create_networkx_adapter() else "disabled/not installed")

    benchmark = CrisisReplayBenchmark([
        ReplayCase(name="baseline-1", query="brief border escalation", country="IND"),
    ])
    print("Benchmark cases:", len(benchmark.cases))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
