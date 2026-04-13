from dataclasses import dataclass


def _clip01(value: float) -> float:
    return max(0.0, min(1.0, float(value or 0.0)))


@dataclass
class SignalBelief:
    signal: str
    belief: float
    uncertainty: float
    source_agreement: float
    temporal_stability: float

    def __post_init__(self) -> None:
        self.signal = str(self.signal or "").strip().upper()
        self.belief = _clip01(self.belief)
        self.uncertainty = _clip01(self.uncertainty)
        self.source_agreement = _clip01(self.source_agreement)
        self.temporal_stability = _clip01(self.temporal_stability)

