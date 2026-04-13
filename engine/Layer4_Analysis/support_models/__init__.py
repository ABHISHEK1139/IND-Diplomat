"""
Layer-4 support_models — compatibility shim.

Canonical location: Layer3_StateModel.providers
These models are measurement/world-modeling code and belong in Layer-3.
This package remains as a re-export shim so existing imports don't break.
"""

from . import context, country_model, investigation_outcome

__all__ = ["context", "country_model", "investigation_outcome"]
