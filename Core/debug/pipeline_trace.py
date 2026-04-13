"""Simple runtime trace utility for pipeline stage visibility."""

from __future__ import annotations

from datetime import datetime


def trace(stage: str) -> None:
    stamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{stamp}] [PIPELINE] {stage}")


__all__ = ["trace"]
