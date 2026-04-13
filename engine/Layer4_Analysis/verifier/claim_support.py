"""
Decision-level claim support policy.
"""

from __future__ import annotations

from typing import Optional, Tuple


REQUIRED_ATOMS = {
    "CRITICAL": 4,
    "HIGH": 4,
    "ELEVATED": 2,
    "GUARDED": 2,
    "RHETORICAL_POSTURING": 2,
    "LOW": 1,
}


def check_claim_support(decision: str, atom_count: int) -> Tuple[bool, int]:
    token = str(decision or "LOW").strip().upper()
    required = int(REQUIRED_ATOMS.get(token, REQUIRED_ATOMS["LOW"]))
    supported = int(atom_count or 0) >= required
    return supported, required


__all__ = [
    "check_claim_support",
    "REQUIRED_ATOMS",
]
