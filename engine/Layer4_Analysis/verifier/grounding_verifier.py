"""
Grounding verifier: count independent signal types and evidence atoms.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple

from engine.Layer4_Analysis.evidence.evidence_atom import EvidenceAtom
from engine.Layer4_Analysis.evidence.signal_ontology import canonicalize_signal_token


def _normalize_signal(value: Any) -> str:
    """Delegate to the authoritative signal ontology normaliser."""
    canon = canonicalize_signal_token(str(value or ""))
    return canon if canon else str(value or "").strip().upper()


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _signal_type(signal: str) -> str:
    token = _normalize_signal(signal)
    if not token:
        return "UNKNOWN"
    if token.startswith("SIG_MIL_") or "FORCE_" in token or "LOGISTICS_" in token:
        return "MILITARY"
    if token.startswith("SIG_DIP_") or "ALLIANCE" in token or "NEGOTIATION" in token:
        return "DIPLOMATIC"
    if token.startswith("SIG_ECO_") or token.startswith("SIG_ECON_") or "SANCTION" in token:
        return "ECONOMIC"
    if token.startswith("SIG_DOM_") or "INTERNAL_INSTABILITY" in token or "PROTEST" in token:
        return "DOMESTIC"
    if (
        "SOVEREIGNTY" in token
        or "MARITIME" in token
        or "TREATY" in token
        or "LEGAL" in token
        or "VIOLATION" in token
    ):
        return "LEGAL"
    if token.startswith("SIG_CYBER_"):
        return "CYBER"
    return token


def build_evidence_atoms(sources: Iterable[Dict[str, Any]]) -> List[EvidenceAtom]:
    grouped: Dict[Tuple[str, str, str], EvidenceAtom] = {}
    for row in list(sources or []):
        if not isinstance(row, dict):
            continue
        source_id = _normalize_text(row.get("id"))
        source_name = _normalize_text(row.get("source"))
        publication_date = _normalize_text(row.get("publication_date"))
        source_type = _normalize_text(row.get("source_type") or source_name or "unknown")

        # One independent observation atom per source + publication date.
        atom_key = (
            source_name.lower(),
            publication_date,
            source_id or f"{source_name}:{publication_date}",
        )

        atom = grouped.get(atom_key)
        if atom is None:
            atom = EvidenceAtom(
                source_id=source_id or atom_key[2],
                source_type=source_type,
                timestamp=publication_date,
                signals=[],
            )
            grouped[atom_key] = atom

        signal = _normalize_signal(row.get("signal"))
        if signal and signal not in atom.signals:
            atom.signals.append(signal)

    return list(grouped.values())


def verify_grounding(
    *,
    sources: Iterable[Dict[str, Any]],
    min_atoms: int = 3,
) -> Tuple[bool, int, List[EvidenceAtom]]:
    atoms = build_evidence_atoms(sources)
    unique_signal_types = set()
    for atom in list(atoms or []):
        for signal in list(getattr(atom, "signals", []) or []):
            unique_signal_types.add(_signal_type(signal))
    signal_type_count = len(unique_signal_types)
    grounded = signal_type_count >= int(min_atoms or 0)
    return grounded, signal_type_count, atoms


__all__ = [
    "build_evidence_atoms",
    "verify_grounding",
]
