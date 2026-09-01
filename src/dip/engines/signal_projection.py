"""Project signals forward to synthetic signals for simulation/wargame.
This is a lightweight projection used to seed Layer-8 synthetic signals.
"""
from __future__ import annotations

from typing import List
from .observed_signal import ObservedSignal


def project_signals(signals: List[ObservedSignal], horizon_days: int = 14) -> List[dict]:
    synthetic = []
    for s in signals:
        if s.intensity >= 0.6 and s.confidence >= 0.5:
            # amplify high-intensity signals into short-term synthetic signals
            synthetic.append({
                "entity": s.entity,
                "action": f"projected_{s.action}",
                "intensity": round(min(1.0, s.intensity * 1.2), 3),
                "confidence": round(min(1.0, s.confidence * 0.9), 3),
                "horizon_days": min(90, horizon_days),
            })
        else:
            # low intensity -> may decay or produce weak synthetic signals
            synthetic.append({
                "entity": s.entity,
                "action": f"projected_{s.action}",
                "intensity": round(max(0.0, s.intensity * 0.6), 3),
                "confidence": round(max(0.0, s.confidence * 0.8), 3),
                "horizon_days": min(30, horizon_days),
            })

    return synthetic
