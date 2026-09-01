"""
Adversary Intent Model (Theory of Mind)
=======================================
Analyzes signals to map them to perceived intent profiles.
"""

from typing import List, Dict
from dip.core.schema import Signal
from dip.core.fuzzy import _clamp

class IntentAnalyzer:
    def __init__(self):
        # Base intent categories
        self.intent_categories = {
            'internal_insecurity': 0.0,
            'external_expansionism': 0.0,
            'defensive_posturing': 0.0
        }

    def analyze(self, signals: List[Signal]) -> Dict[str, float]:
        intents = {k: [] for k in self.intent_categories.keys()}
        
        for sig in signals:
            code = sig.action.lower()
            
            # Internal Insecurity
            if "unrest" in code or "protest" in code or "crackdown" in code or "censorship" in code:
                intents["internal_insecurity"].append(sig.intensity * sig.confidence)
                
            # External Expansionism
            if "annex" in code or "invade" in code or "mil_build" in code or "threat" in code or "hostil" in code or "escalation" in code:
                intents["external_expansionism"].append(sig.intensity * sig.confidence)
                
            # Defensive Posturing
            if "defens" in code or "fortify" in code or "withdraw" in code or "sanction" in code:
                intents["defensive_posturing"].append(sig.intensity * sig.confidence)

        def fuzzy_agg(scores: List[float]) -> float:
            if not scores: return 0.0
            return min(1.0, max(scores) * 1.2)

        return {
            k: _clamp(fuzzy_agg(v)) for k, v in intents.items()
        }
