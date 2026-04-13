"""
Anomaly Sentinel.
Detects genuine "Black Swan" events where standard models fail to explain observed reality.

FIX-1: Raised MIN_SIGNAL_VOLUME 4→6, added hypothesis-existence guard.
Zero hypotheses with low coverage = analytical ambiguity, NOT anomaly.
Genuine anomaly requires: high signal volume + ministers DID produce hypotheses
+ high contradictions + very low coverage simultaneously.
"""
from typing import Set
from engine.Layer4_Analysis.council_session import CouncilSession


class AnomalySentinel:
    # FIX-1: Raised from 4 to 6 — require genuinely high signal density
    MIN_SIGNAL_VOLUME = 6
    MIN_EVIDENCE_BACKING_RATIO = 0.35

    @staticmethod
    def _evidence_backing_ratio(session: CouncilSession, observed_signals: Set[str]) -> float:
        if not observed_signals:
            return 0.0

        state_context = getattr(session, "state_context", None)
        signal_evidence = dict(getattr(state_context, "signal_evidence", {}) or {}) if state_context else {}
        evidence_ctx = getattr(state_context, "evidence", None) if state_context else None
        signal_provenance = dict(getattr(evidence_ctx, "signal_provenance", {}) or {}) if evidence_ctx else {}

        backed = 0
        for signal in list(observed_signals or []):
            token = str(signal or "").strip().upper()
            if not token:
                continue
            if list(signal_evidence.get(token, []) or []) or list(signal_provenance.get(token, []) or []):
                backed += 1

        return backed / max(len(observed_signals), 1)

    @staticmethod
    def _has_sparse_data(session: CouncilSession) -> bool:
        state_context = getattr(session, "state_context", None)
        meta = getattr(state_context, "meta", None) if state_context else None
        try:
            source_count = int(getattr(meta, "source_count", 0) or 0)
        except Exception:
            source_count = 0
        try:
            data_confidence = float(getattr(meta, "data_confidence", 0.0) or 0.0)
        except Exception:
            data_confidence = 0.0
        return source_count < 5 and data_confidence < 0.45

    def check_for_anomaly(self, session: CouncilSession, observed_signals: Set[str], coverage: float) -> bool:
        """
        Returns True ONLY for genuine Black Swan anomalies.

        FIX-1: No longer triggers when ministers simply have low coverage.
        Zero hypotheses = analytical ambiguity, not anomaly.
        Requires ALL of:
          1. High signal volume (≥6 observed signals)
          2. Ministers DID produce hypotheses (someone tried to explain)
          3. High contradictions (>2 conflicts) AND very low coverage (<0.15)
        """
        signal_volume = len(observed_signals)

        # Gate 1: Need genuinely high signal density
        if signal_volume < self.MIN_SIGNAL_VOLUME:
            return False

        # Gate 2: FIX-1 — If no hypotheses exist, this is ambiguity not anomaly.
        # The system should produce a fallback estimate, not shut down.
        hypotheses = list(getattr(session, "hypotheses", []) or [])
        if not hypotheses:
            return False

        evidence_backing_ratio = self._evidence_backing_ratio(session, observed_signals)
        if evidence_backing_ratio < self.MIN_EVIDENCE_BACKING_RATIO:
            return False

        if self._has_sparse_data(session) and coverage < 0.25:
            return False

        # Gate 3: Contradiction check — require genuine model confusion
        conflict_list = getattr(session, "identified_conflicts", None)
        if conflict_list is None:
            conflict_list = getattr(session, "conflicts", [])
        contradiction_count = len(list(conflict_list or []))

        # FIX-1: Only trigger on extreme contradiction + very low coverage
        # (ministers tried to explain but produced fundamentally contradictory results)
        if contradiction_count > 2 and coverage < 0.15:
            return True

        return False
