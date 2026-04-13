"""
Knowledge-gap driven investigation controller (collection tasking mode).
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from engine.Layer4_Analysis.evidence.signal_ontology import canonicalize_signal_token, descriptor_for_signal
from engine.Layer4_Analysis.investigation.investigation_request import InvestigationRequest
from engine.Layer4_Analysis.investigation.epistemic_evaluator import would_change_decision
from engine.Layer4_Analysis.investigation.observability_rules import is_observable
from engine.layer4_reasoning.signal_queries import SIGNAL_COLLECTION_MAP


class InvestigationController:
    COVERAGE_THRESHOLD = 0.60
    MAX_INVESTIGATION_ROUNDS = 3
    BELIEF_INVESTIGATION_THRESHOLD = 0.35

    def __init__(self, retriever: Optional[Any] = None, extractor: Optional[Any] = None):
        # Layer-4 firewall: investigation planning only.
        # No direct retrieval/parsing is allowed in Layer-4.
        _ = retriever, extractor
        self.retriever = None
        self.extractor = None

    def needs_investigation(self, gap_result: Dict[str, Any]) -> bool:
        coverage = float(gap_result.get("coverage", 0.0) or 0.0)
        return coverage < self.COVERAGE_THRESHOLD

    def signals_needing_investigation(
        self,
        *,
        predicted_signals: Iterable[str],
        belief_map: Dict[str, float],
        threshold: Optional[float] = None,
    ) -> List[str]:
        """
        Select predicted signals that have weak support from soft evidence.
        """
        cutoff = self.BELIEF_INVESTIGATION_THRESHOLD if threshold is None else float(threshold)
        cutoff = max(0.0, min(1.0, cutoff))

        selected: List[str] = []
        seen = set()
        weights = dict(belief_map or {})
        for sig in list(predicted_signals or []):
            raw = str(sig or "").strip()
            if not raw:
                continue
            token = canonicalize_signal_token(raw) or raw.upper().replace("-", "_").replace(" ", "_")
            if not token or token in seen:
                continue

            score = weights.get(token, weights.get(raw, 0.0))
            try:
                belief = max(0.0, min(1.0, float(score or 0.0)))
            except Exception:
                belief = 0.0
            if belief < cutoff:
                selected.append(token)
                seen.add(token)
        return selected

    def select_investigations(
        self,
        session: Any,
        *,
        candidate_signals: Optional[Iterable[str]] = None,
    ) -> List[str]:
        """
        Select only critical and observable investigations:
        - must be decision-sensitive (would change decision)
        - must be realistically observable
        """
        candidates: List[str] = []
        seen = set()

        if candidate_signals is not None:
            for signal in list(candidate_signals or []):
                token = canonicalize_signal_token(str(signal or "").strip()) or str(signal or "").strip().upper()
                if not token or token in seen:
                    continue
                seen.add(token)
                candidates.append(token)

        if not candidates:
            for hypothesis in list(getattr(session, "hypotheses", []) or []):
                for signal in list(getattr(hypothesis, "missing_signals", []) or []):
                    token = canonicalize_signal_token(str(signal or "").strip()) or str(signal or "").strip().upper()
                    if not token or token in seen:
                        continue
                    seen.add(token)
                    candidates.append(token)

        critical_requests: List[str] = []
        for token in candidates:
            if not is_observable(token):
                continue
            if would_change_decision(session, token):
                critical_requests.append(token)
        return critical_requests

    def build_collection_tasks(self, missing_signals: Iterable[str]) -> List[InvestigationRequest]:
        tasks: List[InvestigationRequest] = []
        seen = set()

        for sig in list(missing_signals or []):
            raw = str(sig or "").strip()
            if not raw:
                continue
            token = canonicalize_signal_token(raw) or raw
            if token in seen:
                continue
            seen.add(token)

            # Prefer raw key first (legacy aliases), then canonical token.
            mapped_query = SIGNAL_COLLECTION_MAP.get(raw)
            if not mapped_query:
                mapped_query = SIGNAL_COLLECTION_MAP.get(token)
            if not mapped_query:
                continue

            tasks.append(
                InvestigationRequest(
                    signal_token=token,
                    collection_target="OSINT_FEEDS",
                    priority="HIGH",
                    query=mapped_query,
                )
            )
        return tasks

    def generate_queries(
        self,
        *,
        question: str,
        hypothesis: str,
        missing_signals: Iterable[str],
        discriminatory_signals: Iterable[str] | None = None,
        max_queries: int = 6,
    ) -> List[str]:
        """
        Compatibility API used by tests/tools.
        Produces query strings from collection tasks.
        """
        clean_question = " ".join(str(question or "").split()).strip()
        clean_hypothesis = " ".join(str(hypothesis or "").split()).strip()
        queries: List[str] = []

        if clean_question:
            queries.append(clean_question)
        if clean_question and clean_hypothesis:
            queries.append(f"{clean_question} evidence for {clean_hypothesis}")

        for signal in list(discriminatory_signals or []):
            token = canonicalize_signal_token(str(signal or "").strip()) or str(signal or "").strip()
            if not token:
                continue
            descriptor = SIGNAL_COLLECTION_MAP.get(token, descriptor_for_signal(token) or token.replace("_", " "))
            queries.append(f"differentiating evidence {descriptor}")

        for task in self.build_collection_tasks(missing_signals):
            queries.append(task.query)

        deduped: List[str] = []
        seen = set()
        for item in queries:
            query = " ".join(str(item).split()).strip()
            if not query:
                continue
            token = query.lower()
            if token in seen:
                continue
            seen.add(token)
            deduped.append(query)
            if len(deduped) >= max(1, int(max_queries)):
                break
        return deduped

    def collect_observations(self, missing_signals: Iterable[str], top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Layer-4 firewall mode:
        Return investigation intents only. Retrieval/parsing is delegated outside Layer-4.
        """
        tasks = self.build_collection_tasks(missing_signals)
        if not tasks:
            return []

        planned: List[Dict[str, Any]] = []
        for task in tasks:
            planned.append(
                {
                    "task_signal": str(task.signal_token),
                    "task_query": str(task.query),
                    "collection_target": str(task.collection_target),
                    "priority": str(task.priority),
                }
            )
        return planned[: max(1, int(top_k or 1))]


__all__ = ["InvestigationController"]
