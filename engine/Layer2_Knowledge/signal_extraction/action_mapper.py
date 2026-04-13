"""
Layer-2 diplomatic action mapper.

Maps CAMEO event codes into directed diplomatic actions for statement building.
"""

from __future__ import annotations

from typing import Dict


# Fine-grained CAMEO mappings (3+ digit codes) used first.
EVENT_ACTION_MAP: Dict[str, str] = {
    "012": "consulted",
    "013": "negotiated",
    "033": "cooperated",
    "040": "made_statement",
    "111": "criticized",
    "112": "accused",
    "113": "rejected",
    "131": "threatened",
    "138": "warned",
    "145": "sanctioned",
    "190": "military_action",
}


# Root-code fallback when specific mapping is unavailable.
ROOT_ACTION_MAP: Dict[str, str] = {
    "01": "made_statement",
    "02": "consulted",
    "03": "cooperated",
    "04": "consulted",
    "05": "cooperated",
    "06": "cooperated",
    "07": "provided_aid",
    "08": "cooperated",
    "09": "observed",
    "10": "pressured",
    "11": "criticized",
    "12": "rejected",
    "13": "warned",
    "14": "protested",
    "15": "mobilized",
    "16": "sanctioned",
    "17": "coerced",
    "18": "attacked",
    "19": "military_action",
    "20": "mass_violence",
}


def map_event_to_action(
    event_code: str = "",
    event_root_code: str = "",
    default: str = "made_statement",
) -> str:
    """
    Convert CAMEO code fields to a Layer-2 diplomatic action label.

    Priority:
    1) exact event code
    2) event-code prefix (first 3 chars)
    3) root code
    """
    code = "".join(ch for ch in str(event_code or "").strip() if ch.isdigit())
    root = "".join(ch for ch in str(event_root_code or "").strip() if ch.isdigit())

    if code and code in EVENT_ACTION_MAP:
        return EVENT_ACTION_MAP[code]
    if len(code) >= 3 and code[:3] in EVENT_ACTION_MAP:
        return EVENT_ACTION_MAP[code[:3]]

    if not root and len(code) >= 2:
        root = code[:2]
    if root and root in ROOT_ACTION_MAP:
        return ROOT_ACTION_MAP[root]

    return default


__all__ = ["EVENT_ACTION_MAP", "ROOT_ACTION_MAP", "map_event_to_action"]
