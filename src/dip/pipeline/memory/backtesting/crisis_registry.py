"""
Crisis Registry (Layer 6)
=========================
Database of historical crises for backtesting.
Supports dynamic loading from JSON scenario files.
"""

import json
import logging
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("Layer6_Backtesting.crisis_registry")

SCENARIOS_DIR = Path(__file__).resolve().parent.parent / "data" / "scenarios"

class CrisisTimelineEvent(BaseModel):
    day: int
    signals: List[str]

class CrisisScenario(BaseModel):
    id: str = Field(..., description="Unique scenario ID")
    name: str
    start_date: str
    peak_date: str
    peak_threat_level: str
    timeline: List[CrisisTimelineEvent]

class CrisisRegistry:
    """Manages backtesting crisis scenarios."""

    def __init__(self, scenarios_dir: Path = SCENARIOS_DIR):
        self.scenarios_dir = scenarios_dir
        self.scenarios: Dict[str, CrisisScenario] = {}
        self._ensure_defaults()
        self.load_scenarios()

    def _ensure_defaults(self):
        """Write default scenarios if they don't exist."""
        os.makedirs(self.scenarios_dir, exist_ok=True)
        
        defaults = {
            "UKRAINE_2022": {
                "id": "UKRAINE_2022",
                "name": "Russian Invasion of Ukraine",
                "start_date": "2021-11-01",
                "peak_date": "2022-02-24",
                "peak_threat_level": "CRITICAL",
                "timeline": [
                    {"day": -90, "signals": ["SIG_MIL_ESCALATION", "SIG_FORCE_POSTURE"]},
                    {"day": -60, "signals": ["SIG_MIL_MOBILIZATION", "SIG_COERCIVE_BARGAINING"]},
                    {"day": -30, "signals": ["SIG_NEGOTIATION_BREAKDOWN", "SIG_DIP_HOSTILITY"]},
                    {"day": -5, "signals": ["SIG_MASS_MOBILIZATION", "SIG_PUBLIC_STATEMENT"]},
                    {"day": 0, "signals": ["SIG_MIL_ESCALATION", "SIG_MIL_ESCALATION", "SIG_INTERNAL_INSTABILITY"]}
                ]
            },
            "KARGIL_1999": {
                "id": "KARGIL_1999",
                "name": "Kargil War",
                "start_date": "1999-05-03",
                "peak_date": "1999-05-26",
                "peak_threat_level": "HIGH",
                "timeline": [
                    {"day": -20, "signals": ["SIG_MIL_ESCALATION"]},
                    {"day": -10, "signals": ["SIG_FORCE_POSTURE", "SIG_DIP_HOSTILITY"]},
                    {"day": 0, "signals": ["SIG_MIL_ESCALATION", "SIG_MIL_ESCALATION"]}
                ]
            }
        }
        
        for s_id, s_data in defaults.items():
            path = self.scenarios_dir / f"{s_id}.json"
            if not path.exists():
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(s_data, f, indent=2)

    def load_scenarios(self):
        """Load scenarios from JSON files in the scenarios directory."""
        self.scenarios.clear()
        if not self.scenarios_dir.exists():
            return
            
        for path in self.scenarios_dir.glob("*.json"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    
                # Use filename as ID if not provided
                if "id" not in data:
                    data["id"] = path.stem
                    
                scenario = CrisisScenario(**data)
                self.scenarios[scenario.id] = scenario
                logger.debug(f"Loaded scenario {scenario.id} from {path.name}")
            except Exception as e:
                logger.error(f"Failed to load scenario from {path}: {e}")

    def get_scenario(self, scenario_id: str) -> Optional[Dict[str, Any]]:
        """Return scenario dict format for backward compatibility."""
        scenario = self.scenarios.get(scenario_id)
        if not scenario:
            return None
        # Omit 'id' to match old CRISIS_DATABASE format exactly, though keeping it is harmless
        data = scenario.model_dump()
        data.pop("id", None)
        return data
        
    def list_scenarios(self) -> List[str]:
        return list(self.scenarios.keys())

# Global singleton to replace the module-level dict
registry = CrisisRegistry()

# Proxy object to maintain backward compatibility with code doing `CRISIS_DATABASE["UKRAINE_2022"]`
class _CrisisDatabaseProxy:
    def __getitem__(self, key):
        scenario = registry.get_scenario(key)
        if scenario is None:
            raise KeyError(key)
        return scenario
        
    def __contains__(self, key):
        return key in registry.scenarios
        
    def keys(self):
        return registry.scenarios.keys()
        
    def values(self):
        return [registry.get_scenario(k) for k in registry.scenarios.keys()]
        
    def items(self):
        return [(k, registry.get_scenario(k)) for k in registry.scenarios.keys()]
        
    def get(self, key, default=None):
        scenario = registry.get_scenario(key)
        return scenario if scenario is not None else default

CRISIS_DATABASE = _CrisisDatabaseProxy()
