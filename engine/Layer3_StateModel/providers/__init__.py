"""
Layer-3 StateModel Providers.

This package contains data providers AND world-modeling support models:
- Dataset providers (GDELT, SIPRI, World Bank, etc.)
- Behavioral baselines (baseline_model)
- Intent/Capability analysis (intent_capability_model)
- Investigation outcome classification (investigation_outcome)

These are all measurement and world-modeling components that feed the StateContext.
They must NOT perform geopolitical reasoning — that belongs in Layer-4.
"""

from .baseline_model import BaselineModel, baseline_model, AnomalyResult
from .intent_capability_model import IntentCapabilityModel, IntentCapabilityProfile
from .investigation_outcome import classify_outcome, build_outcome_record

__all__ = [
    "BaselineModel",
    "baseline_model",
    "AnomalyResult",
    "IntentCapabilityModel",
    "IntentCapabilityProfile",
    "classify_outcome",
    "build_outcome_record",
]
