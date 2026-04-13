import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class DossierStore:
    """
    Lightweight dossier loader for on-device structured ground truth.
    Profiles live in JSON files under `data/dossiers/` with the shape:
        {
          "name": "India",
          "aliases": ["Republic of India", "IND"],
          "facts": [
             {"key": "steel_tariff", "value": "15%", "as_of": "2024-04-01", "source": "Customs Notification"}
          ],
          "alliances": ["Quad", "BRICS"]
        }
    """

    def __init__(self, base_path: Path = None):
        self.base_path = base_path or Path("data/dossiers")
        self.profiles: Dict[str, Dict] = {}
        self._load_all()

    def _load_all(self):
        if not self.base_path.exists():
            return
        for file in self.base_path.glob("*.json"):
            try:
                data = json.loads(file.read_text())
                name = data.get("name")
                if name:
                    self.profiles[name.lower()] = data
                    for alias in data.get("aliases", []):
                        self.profiles[alias.lower()] = data
            except Exception:
                # Keep loading others even if one fails
                continue

    def get_profile(self, name: str) -> Optional[Dict]:
        return self.profiles.get(name.lower())

    def match_query(self, query: str) -> List[Tuple[str, Dict]]:
        """Return dossier profiles whose name/alias appears in the query."""
        hits = []
        q_lower = query.lower()
        for key, profile in self.profiles.items():
            if key in q_lower:
                hits.append((profile.get("name", key), profile))
        return hits

    def as_sources(self, profiles: List[Tuple[str, Dict]]) -> List[Dict]:
        """Convert dossier facts to RAG-compatible sources."""
        sources = []
        for name, profile in profiles:
            for fact in profile.get("facts", []):
                sources.append(
                    {
                        "id": f"dossier::{name}::{fact.get('key','fact')}",
                        "content": f"{name}: {fact.get('key')}: {fact.get('value')}",
                        "metadata": {
                            "source": "dossier",
                            "entity": name,
                            "as_of": fact.get("as_of"),
                            "provenance": fact.get("source"),
                            "confidence": 0.95,
                        },
                    }
                )
        return sources
