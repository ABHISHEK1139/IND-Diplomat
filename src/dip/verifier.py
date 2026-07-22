"""
Verifier: Fuzzy Evidence Grounding Engine
==========================================

Uses fuzzy membership functions to grade claim verification instead
of a hard binary check. Each claim gets a fuzzy verification score
based on term overlap, source diversity, and corroboration strength.

Fuzzy verification = weighted combination of:
    - Term coverage (how many claim keywords appear in evidence)
    - Source diversity (how many independent sources support it)
    - Corroboration strength (belief support scores from Layer 3)

Final score undergoes fuzzy defuzzification to produce a crisp
verification_score in [0.0, 1.0].
"""

from typing import List
import math


# ── Fuzzy membership functions (inline to avoid circular imports) ──

def _rising(x: float, low: float, high: float) -> float:
    if x <= low:
        return 0.0
    if x >= high:
        return 1.0
    return max(0.0, min(1.0, (x - low) / (high - low)))


def _trapezoid(x: float, a: float, b: float, c: float, d: float) -> float:
    if x <= a or x >= d:
        return 0.0
    if b <= x <= c:
        return 1.0
    if a < x < b:
        return (x - a) / (b - a)
    return (d - x) / (d - c)


# ── Verification weight constants ────────────────────────────────

W_TERM_COVERAGE = 0.50     # How many claim terms appear in evidence
W_SOURCE_DIVERSITY = 0.25  # How many unique sources support claims
W_CORROBORATION = 0.25     # Belief accumulator support scores


def verify(session, claims: List[str]) -> bool:
    """
    Fuzzy verification of claims against the evidence corpus.

    Sets session.verification_score (0.0–1.0).
    Returns True if verification_score > 0.7 (strong grounding).

    Verification Equation:
        V = W_term * μ_term + W_source * μ_source + W_corr * μ_corr

    Where:
        μ_term   = fuzzy rising membership of term coverage ratio
        μ_source = fuzzy rising membership of unique source count
        μ_corr   = fuzzy trapezoid membership of avg belief support
    """
    if not claims:
        session.verification_score = 0.0
        return False

    # ── Build evidence corpus from multiple sources ──────────────
    evidence_parts = list(session.evidence_log)

    # Add matched signals from hypotheses
    for h in session.hypotheses:
        matched = getattr(h, "matched_signals", [])
        evidence_parts.extend(matched)
        htype = getattr(h, "hypothesis_type", getattr(h, "type", "hypothesis"))
        evidence_parts.append(htype)

    # Add signal actions from state context
    for s in session.state_context.current_signals:
        evidence_parts.append(s.action)
        evidence_parts.append(s.entity)
        if s.target:
            evidence_parts.append(s.target)

    corpus = " ".join(evidence_parts).lower()

    # ── 1. Term Coverage: fuzzy grade per claim ──────────────────
    claim_grades = []
    for claim in claims:
        terms = [
            t.lower().strip(".,;:!?\"'()")
            for t in claim.split()
            if len(t) > 3
        ]
        if not terms:
            claim_grades.append(1.0)  # Trivial claims pass
            continue

        matched = sum(1 for t in terms if t in corpus)
        ratio = matched / len(terms)
        # Fuzzy: even 20% term overlap gets partial credit
        grade = _rising(ratio, 0.10, 0.60)
        claim_grades.append(grade)

    avg_term_coverage = sum(claim_grades) / len(claim_grades)

    # ── 2. Source Diversity: count unique source types ────────────
    source_types = set()
    for s in session.state_context.current_signals:
        source_types.add(s.source_ref.split("_")[0] if "_" in s.source_ref else "unknown")
    # Fuzzy: 1 source = 0.2, 2 = 0.5, 3+ = 0.8+
    source_diversity = _rising(len(source_types), 0.5, 4.0)

    # ── 3. Corroboration: average belief support scores ──────────
    belief_scores = []
    if hasattr(session.state_context, 'beliefs') and session.state_context.beliefs:
        for b in session.state_context.beliefs:
            belief_scores.append(b.support_score)

    if belief_scores:
        avg_corroboration = sum(belief_scores) / len(belief_scores)
    else:
        # Fallback: use average signal confidence
        confidences = [s.confidence for s in session.state_context.current_signals]
        avg_corroboration = sum(confidences) / len(confidences) if confidences else 0.0

    # Fuzzy trapezoid: moderate corroboration (0.35–0.75) gets partial credit
    corroboration_grade = _trapezoid(avg_corroboration, 0.15, 0.35, 0.75, 1.0)

    # ── Fuzzy aggregation ────────────────────────────────────────
    score = (
        W_TERM_COVERAGE * avg_term_coverage +
        W_SOURCE_DIVERSITY * source_diversity +
        W_CORROBORATION * corroboration_grade
    )

    # Clamp to [0, 1]
    score = max(0.0, min(1.0, round(score, 3)))
    session.verification_score = score

    return score > 0.7
