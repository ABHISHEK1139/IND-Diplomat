"""
Convert retrieved documents into structured geopolitical signals.

Layer intent:
documents -> event labels -> canonical signals
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List

from engine.Layer2_Knowledge.cameo_mapper import map_to_cameo


_EVENT_RULES = {
    "MOBILIZATION": (
        "troop mobilization",
        "mobilization",
        "reserve call-up",
        "call-up",
        "troop movement",
    ),
    "MIL_EXERCISE": (
        "military exercise",
        "drill",
        "live-fire",
        "war game",
    ),
    "LOGISTICS": (
        "fuel stockpile",
        "logistics build-up",
        "supply convoy",
        "ammunition transfer",
    ),
    "SANCTION": (
        "sanction",
        "export control",
        "asset freeze",
        "embargo",
    ),
    "TRADE_SHOCK": (
        "trade suspension",
        "shipping halt",
        "port closure",
        "customs blockade",
    ),
    "HOSTILE_RHETORIC": (
        "hostile rhetoric",
        "threatened",
        "warned of consequences",
        "ultimatum",
    ),
    "NEGOTIATION_BREAKDOWN": (
        "talks collapsed",
        "negotiation breakdown",
        "dialogue suspended",
        "diplomatic breakdown",
    ),
    "CYBER_PREPARATION": (
        "cyber operation",
        "malware campaign",
        "network intrusion",
        "cyber attack preparation",
    ),
    "PROTEST_SURGE": (
        "mass protest",
        "civil unrest",
        "street clashes",
        "emergency crackdown",
    ),
}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _clip01(value: Any) -> float:
    return max(0.0, min(1.0, _safe_float(value, 0.0)))


def _excerpt(text: Any, limit: int = 260) -> str:
    token = str(text or "").strip().replace("\n", " ")
    if len(token) <= limit:
        return token
    return token[: max(1, limit - 3)] + "..."


def _printable_ratio(text: str) -> float:
    if not text:
        return 0.0
    printable = sum(1 for ch in text if ch.isprintable() and ch not in {"\x00", "\x01", "\x02"})
    return printable / float(len(text))


def _normalize_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    payload = dict(doc or {})
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}

    source = str(payload.get("source") or metadata.get("source") or "unknown").strip()
    url = str(payload.get("url") or metadata.get("url") or "").strip()
    content = str(payload.get("content") or payload.get("text") or "").strip()
    publication_date = str(
        payload.get("publication_date")
        or metadata.get("publication_date")
        or metadata.get("date")
        or ""
    ).strip()
    doc_id = str(payload.get("id") or metadata.get("id") or "").strip()
    score = _clip01(payload.get("score", metadata.get("score", 0.5)))
    source_type = str(payload.get("source_type") or metadata.get("type") or "").strip().lower()

    return {
        "id": doc_id,
        "source": source,
        "url": url,
        "content": content,
        "publication_date": publication_date,
        "score": score,
        "source_type": source_type,
        "metadata": metadata,
    }


def _is_noise(doc: Dict[str, Any]) -> bool:
    content = str(doc.get("content") or "")
    source = str(doc.get("source") or "").lower()
    url = str(doc.get("url") or "").strip().lower()
    source_type = str(doc.get("source_type") or "").lower()

    if len(content) < 40:
        return True
    if _printable_ratio(content) < 0.90:
        return True

    # Drop local/binary/legal-memory artifacts that are not operational OSINT.
    if (".pdf" in source or ".txt" in source) and not (url.startswith("http://") or url.startswith("https://")):
        return True
    if "legal_memory" in source or "un_mtdsg_full" in source:
        return True
    if source_type in {"treaty", "legal", "archive"} and not url.startswith(("http://", "https://")):
        return True

    return False


def _extract_events(text: str) -> List[str]:
    token = str(text or "").lower()
    events: List[str] = []
    for event, phrases in _EVENT_RULES.items():
        for phrase in phrases:
            if phrase in token:
                events.append(event)
                break

    # Regex enrichment for compact forms.
    if re.search(r"\btroop(s)?\b", token) and re.search(r"\bborder|forward|deployment\b", token):
        events.append("MOBILIZATION")
    if re.search(r"\bsanction(s)?\b", token):
        events.append("SANCTION")
    if re.search(r"\bexercise(s)?\b", token):
        events.append("MIL_EXERCISE")

    seen = set()
    ordered: List[str] = []
    for event in events:
        if event in seen:
            continue
        seen.add(event)
        ordered.append(event)
    return ordered


def ingest_documents(docs: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Returns structured signal hits from raw retrieved documents.

    Output schema:
    {
      "signal": "SIG_MIL_MOBILIZATION",
      "event": "MOBILIZATION",
      "source": "...",
      "url": "...",
      "publication_date": "YYYY-MM-DD",
      "excerpt": "...",
      "score": 0.0..1.0,
      "source_id": "..."
    }
    """
    hits: List[Dict[str, Any]] = []
    seen = set()

    for raw in list(docs or []):
        if not isinstance(raw, dict):
            continue
        doc = _normalize_doc(raw)
        if _is_noise(doc):
            continue

        events = _extract_events(doc.get("content", ""))
        if not events:
            continue
        signals = map_to_cameo(events)
        if not signals:
            continue

        excerpt = _excerpt(doc.get("content", ""))
        source = str(doc.get("source") or "unknown")
        url = str(doc.get("url") or "")
        publication_date = str(doc.get("publication_date") or "")
        source_id = str(doc.get("id") or "")
        score = _clip01(doc.get("score", 0.5))

        for event in events:
            mapped = map_to_cameo([event])
            for signal in mapped:
                key = (signal, source_id or source, publication_date, url)
                if key in seen:
                    continue
                seen.add(key)
                hits.append(
                    {
                        "signal": signal,
                        "event": event,
                        "source": source,
                        "url": url,
                        "publication_date": publication_date,
                        "excerpt": excerpt,
                        "score": score,
                        "source_id": source_id or f"{source}:{publication_date}:{signal}",
                    }
                )

    return hits


__all__ = ["ingest_documents"]

