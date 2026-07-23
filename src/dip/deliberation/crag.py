from dip.Config.config import config
"""
CRAG — Corrective Retrieval-Augmented Generation investigator.

When ministers flag missing signals, CRAG runs an investigation loop:
  1. Reads session.missing_signals to identify evidence gaps.
  2. Generates investigation requests (what to look for, where).
  3. Simulates retrieval and logs evidence to session.evidence_log.

*** LAYER-4 GROUNDING RULE (CRITICAL) ***
CRAG MUST NOT fabricate evidence via LLM. When FORCE_MINISTER_HEURISTIC
is set, it uses deterministic pattern-matching against StateContext only.
In LLM mode, it requests the LLM to identify what evidence MIGHT exist —
but NEVER generates fake evidence as if it were real.

All reads/writes go through CouncilSession.
"""

import json
from typing import List

try:
    import litellm
except ImportError:
    litellm = None

from dip.Config.config import config
from dip.core.schema import StateContext
from dip.layer4_reasoning.council_session import CouncilSession
from dip.core.json_utils import strip_markdown_json
from dip.research.planner import ResearchPlanner

LLM_MODEL = config.LLM_MODEL

# Maximum number of investigation iterations
MAX_INVESTIGATION_ROUNDS = 3


async def investigate(session: CouncilSession) -> CouncilSession:
    """
    Investigation loop: repeatedly attempt to fill evidence gaps.

    When FORCE_MINISTER_HEURISTIC=1: uses deterministic signal-pattern
    matching against StateContext — NO LLM calls, NO document access.
    """
    if not session.missing_signals:
        session.evidence_log.append("CRAG: No missing signals to investigate.")
        return session

    # Deterministic heuristic mode
    if config.FORCE_MINISTER_HEURISTIC or litellm is None:
        return _heuristic_investigate(session)

    # LLM mode with fallback
    try:
        return await _llm_investigate(session)
    except Exception:
        return _heuristic_investigate(session)


def _heuristic_investigate(session: CouncilSession) -> CouncilSession:
    """
    Deterministic investigation — NO LLM, NO document access.
    
    Matches missing signals against StateContext patterns:
    - Checks if signal names match known observation categories
    - Checks if any existing signals partially corroborate the gap
    - NEVER fabricates evidence
    """
    sc = session.state_context
    remaining = list(session.missing_signals)
    
    # Pattern-match missing signals against known observation categories
    known_categories = {
        "military": ["military", "troop", "deployment", "exercise", "mobilization"],
        "diplomatic": ["diplomatic", "embassy", "envoy", "summit", "treaty", "negotiation"],
        "economic": ["economic", "sanction", "trade", "tariff", "embargo", "investment"],
        "cyber": ["cyber", "hack", "attack", "malware", "digital"],
        "political": ["political", "election", "protest", "coup", "regime", "government"],
        "alliance": ["alliance", "coalition", "nato", "pact", "partnership"],
    }
    
    for signal_name in list(remaining):
        signal_lower = signal_name.lower()
        
        # Check if any existing observation matches this category
        for category, keywords in known_categories.items():
            if any(kw in signal_lower for kw in keywords):
                matching_obs = sum(
                    1 for s in sc.current_signals
                    if any(kw in s.action.lower() for kw in keywords)
                )
                if matching_obs > 0:
                    session.evidence_log.append(
                        f"[CRAG] PARTIAL: {matching_obs} existing {category} observations "
                        f"may relate to missing signal '{signal_name}'"
                    )
                    remaining.remove(signal_name)
                    break
                else:
                    session.evidence_log.append(
                        f"[CRAG] GAP CONFIRMED: No {category} observations to corroborate '{signal_name}'"
                    )
                    remaining.remove(signal_name)
                    break
    
    # Remaining unmatched signals
    for sig in remaining:
        session.evidence_log.append(
            f"[CRAG] UNINVESTIGATED: '{sig}' — no matching category in StateContext"
        )
    
    session.missing_signals = remaining
    session.evidence_log.append(
        f"[CRAG] Heuristic investigation complete. "
        f"{len(session.missing_signals)} gaps remain, "
        f"{len(session.evidence_log)} findings logged."
    )
    return session


async def _llm_investigate(session: CouncilSession) -> CouncilSession:
    """LLM-based investigation (only when FORCE_MINISTER_HEURISTIC is off)."""
    remaining = list(session.missing_signals)

    for round_num in range(1, MAX_INVESTIGATION_ROUNDS + 1):
        if not remaining:
            break
        requests = await _generate_investigation_requests(remaining, session)
        evidence = await _retrieve_evidence(requests, session)
        for finding in evidence:
            session.evidence_log.append(f"[CRAG round {round_num}] {finding}")
        still_missing = await _check_remaining_gaps(remaining, evidence)
        remaining = still_missing

    session.missing_signals = remaining
    return session


async def _generate_investigation_requests(
    missing: List[str], session: CouncilSession
) -> List[str]:
    """Ask the LLM what specific evidence we should look for."""
    missing_block = "\n".join(f"  - {s}" for s in missing)

    prompt = (
        "You are an intelligence investigator. The following signals are "
        "predicted but NOT yet observed. For each, describe what specific "
        "evidence source or data point we should look for to confirm or "
        "refute it.\n\n"
        f"Country: {session.state_context.country}\n"
        f"Query: {session.query}\n\n"
        f"Missing signals:\n{missing_block}\n\n"
        "Return a JSON array of investigation-request strings, one per "
        "missing signal."
    )

    response = await litellm.acompletion(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=1000
    )

    raw = response.choices[0].message.content.strip()

    try:
        raw = strip_markdown_json(raw)
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(r) for r in parsed]
        elif isinstance(parsed, dict):
            for v in parsed.values():
                if isinstance(v, list):
                    return [str(r) for r in v]
        return [raw]
    except json.JSONDecodeError:
        return [f"Investigate: {s}" for s in missing]


async def _retrieve_evidence(
    requests: List[str], session: CouncilSession
) -> List[str]:
    """
    Retrieves evidence for each investigation request using the Autonomous Research Planner.
    This executes live web searches via DuckDuckGo, crawls the pages, extracts clean text,
    and returns verified evidence.
    """
    planner = ResearchPlanner()
    country = session.state_context.country if hasattr(session.state_context, 'country') else "Global"
    
    try:
        result = await planner.execute_from_gaps(requests, country=country, query_context=session.query)
        
        findings = []
        for r in requests:
            # Check if any evidence covers this request (simple heuristic)
            matching_evidence = [e for e in result.evidence if e.confidence > 0.4]
            if matching_evidence:
                # Combine the top pieces of evidence
                summary = " | ".join([f"[{e.publisher}] {e.text}" for e in matching_evidence[:2]])
                findings.append(summary)
            else:
                findings.append(f"GAP CONFIRMED: No evidence retrieved for: {r}")
                
        return findings
    except Exception as e:
        import logging
        logging.getLogger("CRAG").error(f"Research Planner failed: {e}")
        return [f"RETRIEVAL FAILED for: {r}" for r in requests]


async def _check_remaining_gaps(
    original_missing: List[str], evidence: List[str]
) -> List[str]:
    """
    Determine which missing signals are still unresolved after retrieval.
    Uses simple heuristic: if any evidence item contains 'GAP CONFIRMED'
    or 'RETRIEVAL FAILED', the corresponding signal remains missing.
    """
    still_missing: List[str] = []
    evidence_lower = [e.lower() for e in evidence]

    for i, signal in enumerate(original_missing):
        # Check if the corresponding evidence (by index) is a gap
        if i < len(evidence_lower):
            ev = evidence_lower[i]
            if "gap confirmed" in ev or "retrieval failed" in ev:
                still_missing.append(signal)
        else:
            # No evidence was generated for this signal
            still_missing.append(signal)

    return still_missing
