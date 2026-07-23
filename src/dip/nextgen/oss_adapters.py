"""Optional open-source adapter registry for DIP 2.0 next-gen.

This module does not require the optional packages at import time.  It tells the
runtime which custom code should be replaced by mature open-source components
when those components are installed.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from importlib.util import find_spec
from typing import Dict, List


@dataclass(frozen=True)
class OSSCapability:
    name: str
    package: str
    replaces: str
    dip_use: str
    required: bool = False

    @property
    def installed(self) -> bool:
        return find_spec(self.package) is not None

    def to_dict(self) -> Dict[str, object]:
        payload = asdict(self)
        payload["installed"] = self.installed
        return payload


DEFAULT_STACK: List[OSSCapability] = [
    OSSCapability(
        name="LangGraph",
        package="langgraph",
        replaces="custom pipeline graph, resume logic, HITL pauses",
        dip_use="durable assessment graph with interruptible human review nodes",
    ),
    OSSCapability(
        name="Prefect",
        package="prefect",
        replaces="custom schedulers and background workflow glue",
        dip_use="ingestion, backtesting, forecast resolution, calibration, guardian audits",
    ),
    OSSCapability(
        name="OpenTelemetry",
        package="opentelemetry",
        replaces="custom tracing and ad hoc phase timing",
        dip_use="assessment spans, phase metrics, provider failures, gate-failure counters",
    ),
    OSSCapability(
        name="MLflow",
        package="mlflow",
        replaces="custom experiment registry and promotion notes",
        dip_use="threshold experiments, prompt versions, model/provider eval runs",
    ),
    OSSCapability(
        name="Evidently",
        package="evidently",
        replaces="custom drift and data-quality reports",
        dip_use="source drift, signal drift, fuzzy threshold stability monitoring",
    ),
    OSSCapability(
        name="DuckDuckGo Search",
        package="duckduckgo_search",
        replaces="local PDF/OCR treaty pipeline",
        dip_use="live web search for treaty text, legal precedents, and news feeds",
    ),
    OSSCapability(
        name="Instructor",
        package="instructor",
        replaces="raw LLM JSON parsing and ad hoc retry repair",
        dip_use="Pydantic-validated minister, red-team, CRAG, CoVe, and synthesis outputs",
    ),
    OSSCapability(
        name="Outlines",
        package="outlines",
        replaces="post-hoc schema parsing for local/open LLMs",
        dip_use="token-level constrained decoding for exact Pydantic/JSON/grammar outputs",
    ),
    OSSCapability(
        name="Z3",
        package="z3",
        replaces="informal treaty/legal consistency checks",
        dip_use="SMT proofs for treaty constraints, escalation preconditions, and contradiction gates",
    ),
    OSSCapability(
        name="pyDatalog",
        package="pyDatalog",
        replaces="manual structural anomaly queries",
        dip_use="deductive queries over StateContext, actors, claims, and treaty facts",
    ),
    OSSCapability(
        name="NeMo Guardrails",
        package="nemoguardrails",
        replaces="regex-only narrative safety checks",
        dip_use="semantic input/output rails for final briefing and refusal gate",
    ),
    OSSCapability(
        name="STIX2",
        package="stix2",
        replaces="hand-built intelligence bundle serialization",
        dip_use="STIX-style export/import for entities, indicators, reports, relationships",
    ),
    OSSCapability(
        name="NetworkX",
        package="networkx",
        replaces="custom graph propagation primitives",
        dip_use="theater contagion, actor networks, causal path scoring",
        required=True,
    ),
]


class OSSAdapterRegistry:
    """Runtime view of available open-source replacement capabilities."""

    def __init__(self, capabilities: List[OSSCapability] | None = None):
        self.capabilities = list(capabilities or DEFAULT_STACK)

    def status(self) -> List[Dict[str, object]]:
        return [capability.to_dict() for capability in self.capabilities]

    def installed(self) -> List[OSSCapability]:
        return [capability for capability in self.capabilities if capability.installed]

    def missing_required(self) -> List[OSSCapability]:
        return [
            capability
            for capability in self.capabilities
            if capability.required and not capability.installed
        ]

    def replacement_map(self) -> Dict[str, str]:
        return {
            capability.replaces: capability.name
            for capability in self.capabilities
        }
