"""
CoVe - Chain-of-Verification.

Decomposes the council's hypotheses into atomic, independently verifiable
claims. Each claim is a single factual statement that can be confirmed or
refuted by checking evidence.

All reads/writes go through CouncilSession.
"""

import json
import logging
from typing import List

try:
    import litellm
except ImportError:
    litellm = None

from dip.pipeline.deliberation.reasoning.council_session import CouncilSession
from dip.core.json_utils import strip_markdown_json
from dip.core.Config.config import config

LLM_MODEL = config.LLM_MODEL
logger = logging.getLogger('DIP.Deliberation.CoVe')


async def decompose(session: CouncilSession) -> List[str]:
    if not session.hypotheses:
        return []

    if config.FORCE_MINISTER_HEURISTIC or litellm is None:
        return _heuristic_decompose(session)

    try:
        return await _llm_decompose(session)
    except Exception:
        return _heuristic_decompose(session)


def _heuristic_decompose(session: CouncilSession) -> List[str]:
    claims: List[str] = []
    
    for h in session.hypotheses:
        minister = getattr(h, 'minister', getattr(h, 'minister_name', getattr(h, 'domain', 'Minister')))
        htype = getattr(h, 'hypothesis_type', getattr(h, 'type', 'hypothesis'))
        confidence = getattr(h, 'confidence', 0.5)
        matched_signals = getattr(h, 'matched_signals', [])
        missing_signals = getattr(h, 'missing_signals', [])
        
        claims.append(f"{minister} hypothesizes {htype} with confidence {confidence:.0%}")
        
        for sig in matched_signals[:3]:
            claims.append(f"CONFIRMED: {sig} supports {htype}")
        
        for sig in missing_signals[:3]:
            claims.append(f"UNVERIFIED: {sig} remains unobserved for {htype}")
        
        if confidence >= 0.8:
            claims.append(f"HIGH-CONFIDENCE: {minister} assessment exceeds 80% threshold")
        elif confidence < 0.3:
            claims.append(f"LOW-CONFIDENCE: {minister} assessment below 30%")
    
    if len(session.hypotheses) >= 2:
        types = [getattr(h, 'hypothesis_type', getattr(h, 'type', 'hypothesis')) for h in session.hypotheses]
        if len(set(types)) < len(types):
            claims.append("CONVERGENCE: Multiple ministers assess overlapping domains")
        confs = [getattr(h, 'confidence', 0.5) for h in session.hypotheses]
        if max(confs) - min(confs) > 0.5:
            claims.append("DIVERGENCE: Wide confidence gap between ministers")
    
    for claim in claims:
        session.evidence_log.append(f"[CoVe CLAIM] {claim}")
    
    if session.hypotheses:
        signals = getattr(session.state_context, "current_signals", []) or []
        evidence_quality = 0.5
        if signals:
            evidence_quality = sum(
                float(getattr(s, "confidence", 0.7) or 0.7) * float(getattr(s, "reliability_score", 0.8) or 0.8)
                for s in signals
            ) / len(signals)
        verified_ratio = sum(1 for h in session.hypotheses if getattr(h, 'matched_signals', [])) / len(session.hypotheses)
        avg_conf = sum(getattr(h, 'confidence', 0.5) for h in session.hypotheses) / len(session.hypotheses)
        session.verification_score = round(0.40 * verified_ratio + 0.35 * avg_conf + 0.25 * evidence_quality, 3)
    
    return claims


async def _llm_decompose(session: CouncilSession) -> List[str]:
    hypothesis_block = _format_hypotheses(session)
    evidence_block = _format_evidence(session)

    prompt = (
        "You are a verification analyst. Your job is to decompose the "
        "following intelligence hypotheses and supporting evidence into "
        "atomic, independently verifiable factual claims.\n\n"
        "Each claim MUST be:\n"
        "  - A single, specific factual statement.\n"
        "  - Testable against observable evidence.\n"
        "  - Free of hedging language (no might, could, possibly).\n\n"
        f"Hypotheses:\n{hypothesis_block}\n\n"
        f"Evidence gathered:\n{evidence_block}\n\n"
        "Return a JSON array of claim strings. Aim for 3-8 claims per hypothesis."
    )

    response = await litellm.acompletion(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=1000
    )

    raw = response.choices[0].message.content.strip()
    claims = _parse_claims(raw)

    for claim in claims:
        session.evidence_log.append(f"[CoVe CLAIM] {claim}")

    if session.hypotheses:
        avg_conf = sum(getattr(h, 'confidence', 0.5) for h in session.hypotheses) / len(session.hypotheses)
        verified_count = sum(1 for h in session.hypotheses if getattr(h, 'confidence', 0.5) >= avg_conf and getattr(h, 'matched_signals', []))
        session.verification_score = round(verified_count / len(session.hypotheses), 3)

    return claims


def _format_hypotheses(session: CouncilSession) -> str:
    lines: List[str] = []
    for h in session.hypotheses:
        minister = getattr(h, 'minister', getattr(h, 'minister_name', getattr(h, 'domain', 'Minister')))
        htype = getattr(h, 'hypothesis_type', getattr(h, 'type', 'hypothesis'))
        conf = getattr(h, 'confidence', 0.5)
        pred = getattr(h, 'predicted_signals', [])
        matched = getattr(h, 'matched_signals', [])
        missing = getattr(h, 'missing_signals', [])
        lines.append(
            f'  [{minister}] "{htype}"\n'
            f'    confidence: {conf:.2f}\n'
            f'    predicted: {pred}\n'
            f'    matched:   {matched}\n'
            f'    missing:   {missing}'
        )
    return "\n".join(lines)


def _format_evidence(session: CouncilSession) -> str:
    if not session.evidence_log:
        return "  (no evidence gathered yet)"
    return "\n".join(f"  - {e}" for e in session.evidence_log)


def _parse_claims(raw: str) -> List[str]:
    try:
        raw = strip_markdown_json(raw)
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(c) for c in parsed]
        elif isinstance(parsed, dict):
            for v in parsed.values():
                if isinstance(v, list):
                    return [str(c) for c in v]
        return [raw]
    except json.JSONDecodeError:
        return [f"CoVe raw response (unparseable): {raw}"]
