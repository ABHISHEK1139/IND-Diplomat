"""
Groupthink Detector — Anti-conformity guard for minister council.

Uses sentence embeddings (all-MiniLM-L6-v2) to compute semantic similarity
across minister reasoning outputs.  If average pairwise similarity > 0.80,
a conformity penalty is applied to confidence.

Fallback: Jaccard overlap of driver terms when sentence-transformers unavailable.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, List, Tuple
from Config.config import (
    GROUPTHINK_ALLOW_REMOTE_EMBEDDER_DOWNLOAD,
    GROUPTHINK_EMBEDDER_MODEL,
)

if TYPE_CHECKING:
    from engine.Layer4_Analysis.council_session import MinisterReport

logger = logging.getLogger(__name__)

# ── Thresholds ────────────────────────────────────────────────────────
GROUPTHINK_SIMILARITY_THRESHOLD = 0.80
GROUPTHINK_PENALTY = 0.05

# Lazy singleton
_embedder = None


def _get_embedder():
    """Lazy-load SentenceTransformer without hidden remote downloads by default."""
    global _embedder
    if _embedder is not None:
        return _embedder
    try:
        from sentence_transformers import SentenceTransformer
        _embedder = SentenceTransformer(
            GROUPTHINK_EMBEDDER_MODEL,
            local_files_only=not GROUPTHINK_ALLOW_REMOTE_EMBEDDER_DOWNLOAD,
        )
        logger.info("[GROUPTHINK] Loaded %s embedder", GROUPTHINK_EMBEDDER_MODEL)
        return _embedder
    except Exception as exc:
        mode = "remote-enabled" if GROUPTHINK_ALLOW_REMOTE_EMBEDDER_DOWNLOAD else "local-cache-only"
        logger.warning(
            "[GROUPTHINK] sentence-transformers unavailable (%s, model=%s): %s",
            mode,
            GROUPTHINK_EMBEDDER_MODEL,
            exc,
        )
        return None


def _minister_text(report: "MinisterReport") -> str:
    """Concatenate reasoning fields into a single text for embedding."""
    parts = []
    parts.append(getattr(report, "risk_level_adjustment", "maintain") or "maintain")
    for d in (getattr(report, "primary_drivers", []) or []):
        parts.append(str(d))
    for g in (getattr(report, "critical_gaps", []) or []):
        parts.append(str(g))
    for c in (getattr(report, "counterarguments", []) or []):
        parts.append(str(c))
    return " ".join(parts).strip()


def _eligible_reports(reports: List["MinisterReport"]) -> List["MinisterReport"]:
    eligible: List["MinisterReport"] = []
    for report in reports:
        reasoning_source = str(getattr(report, "reasoning_source", "") or "").lower()
        reasoning_degraded = bool(getattr(report, "reasoning_degraded", False))
        if reasoning_source != "llm" or reasoning_degraded:
            continue
        text = _minister_text(report)
        if not text.strip():
            continue
        eligible.append(report)
    return eligible


def _jaccard_fallback(reports: List["MinisterReport"]) -> Tuple[bool, float, float]:
    """Fallback groupthink detection using Jaccard word overlap."""
    reports = _eligible_reports(reports)
    texts = [set(_minister_text(r).lower().split()) for r in reports]
    if len(texts) < 2:
        return False, 0.0, 0.0

    sims = []
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            union = texts[i] | texts[j]
            if not union:
                sims.append(0.0)
                continue
            sims.append(len(texts[i] & texts[j]) / len(union))

    mean_sim = sum(sims) / len(sims) if sims else 0.0
    flag = mean_sim > GROUPTHINK_SIMILARITY_THRESHOLD
    penalty = GROUPTHINK_PENALTY if flag else 0.0
    return flag, penalty, mean_sim


def detect_groupthink(
    reports: List["MinisterReport"],
) -> Tuple[bool, float, float]:
    """
    Detect conformity across minister reasoning outputs.

    Parameters
    ----------
    reports : list[MinisterReport]
        Round-2 (or round-1) minister reports with reasoning fields populated.

    Returns
    -------
    (flag, penalty, mean_similarity)
        flag : True if groupthink detected
        penalty : confidence penalty to apply (0.0 or GROUPTHINK_PENALTY)
        mean_similarity : pairwise mean cosine similarity (0–1)
    """
    if len(reports) < 2:
        return False, 0.0, 0.0

    reports = _eligible_reports(reports)
    if len(reports) < 2:
        logger.info("[GROUPTHINK] Skipping: fewer than 2 substantive LLM reasoning reports")
        return False, 0.0, 0.0

    embedder = _get_embedder()
    if embedder is None:
        logger.info("[GROUPTHINK] Using Jaccard fallback")
        return _jaccard_fallback(reports)

    try:
        texts = [_minister_text(r) for r in reports]
        # Filter out empty texts
        valid = [(i, t) for i, t in enumerate(texts) if t.strip()]
        if len(valid) < 2:
            return False, 0.0, 0.0

        embeddings = embedder.encode([t for _, t in valid], convert_to_tensor=False)

        # Compute pairwise cosine similarity
        import numpy as np
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms = np.maximum(norms, 1e-10)
        normed = embeddings / norms

        sims = []
        n = len(normed)
        for i in range(n):
            for j in range(i + 1, n):
                sim = float(np.dot(normed[i], normed[j]))
                sims.append(sim)

        mean_sim = sum(sims) / len(sims) if sims else 0.0
        flag = mean_sim > GROUPTHINK_SIMILARITY_THRESHOLD
        penalty = GROUPTHINK_PENALTY if flag else 0.0

        logger.info(
            "[GROUPTHINK] %d ministers, mean_similarity=%.3f, flag=%s, penalty=%.2f",
            len(valid), mean_sim, flag, penalty,
        )
        return flag, penalty, mean_sim

    except Exception as exc:
        logger.warning("[GROUPTHINK] Embedding failed, using Jaccard: %s", exc)
        return _jaccard_fallback(reports)
