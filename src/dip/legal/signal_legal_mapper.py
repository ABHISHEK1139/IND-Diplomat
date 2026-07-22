"""
Legal Signal Mapper — Maps Geopolitical Signals to Treaty Articles
===================================================================

The crucial bridge: "troop_movement near Bhutan border" →
"India-Bhutan Friendship Treaty (2007), Article 2: Prior Consultation"

Port of DIP_8 Core/legal/signal_legal_mapper.py
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
import sys
from pathlib import Path

# Add project root to sys.path to allow importing layer2_knowledge
sys.path.append(str(Path(__file__).resolve().parent.parent))
from dip.layer2_knowledge.vector_store import get_vector_store

logger = logging.getLogger("Legal.signal_mapper")

# Signal → Treaty mapping table
# Format: {signal_action: [{treaty, article, relevance, threshold}]}
SIGNAL_TREATY_MAP: Dict[str, List[Dict[str, Any]]] = {
    "troop_movement": [
        {"treaty": "UN Charter", "article": "Article 2(4)", "relevance": "Prohibition on threat or use of force", "threshold": 0.6},
        {"treaty": "India-Bhutan Friendship Treaty", "article": "Article 2", "relevance": "Prior consultation required for border actions", "threshold": 0.5},
    ],
    "military_deployment": [
        {"treaty": "UN Charter", "article": "Article 51", "relevance": "Self-defense exception", "threshold": 0.7},
        {"treaty": "Geneva Conventions", "article": "Common Article 2", "relevance": "Applicability in armed conflict", "threshold": 0.6},
    ],
    "border_fortification": [
        {"treaty": "India-China Border Agreements", "article": "1993/1996/2005 Protocols", "relevance": "Border peace and tranquility", "threshold": 0.5},
        {"treaty": "UN Charter", "article": "Article 2(3)", "relevance": "Peaceful settlement of disputes", "threshold": 0.4},
    ],
    "naval_patrol": [
        {"treaty": "UNCLOS", "article": "Article 17-19", "relevance": "Innocent passage rights", "threshold": 0.5},
        {"treaty": "UNCLOS", "article": "Article 121", "relevance": "Island/reef territorial waters", "threshold": 0.4},
    ],
    "airspace_violation": [
        {"treaty": "Chicago Convention", "article": "Article 1", "relevance": "Sovereignty over airspace", "threshold": 0.7},
        {"treaty": "ICAO Rules", "article": "Annex 2", "relevance": "Rules of the air", "threshold": 0.5},
    ],
    "sanctions_imposed": [
        {"treaty": "WTO Agreements", "article": "Article XXI", "relevance": "Security exceptions for trade restrictions", "threshold": 0.6},
        {"treaty": "UN Charter", "article": "Article 41", "relevance": "Non-military sanctions framework", "threshold": 0.5},
    ],
    "diplomatic_recall": [
        {"treaty": "Vienna Convention", "article": "Article 9", "relevance": "Persona non grata and diplomatic relations", "threshold": 0.7},
    ],
    "expel_diplomats": [
        {"treaty": "Vienna Convention", "article": "Article 9", "relevance": "Persona non grata declaration", "threshold": 0.8},
    ],
    "trade_restriction": [
        {"treaty": "WTO/GATT", "article": "Article XI", "relevance": "Elimination of quantitative restrictions", "threshold": 0.6},
        {"treaty": "Bilateral Trade Agreements", "article": "MFN Clause", "relevance": "Most-favored-nation treatment", "threshold": 0.5},
    ],
    "cyber_attack": [
        {"treaty": "UN Charter", "article": "Article 2(4)", "relevance": "Cyber operations as use of force", "threshold": 0.7},
        {"treaty": "Tallinn Manual", "article": "Rule 30", "relevance": "Cyber operations as violation of sovereignty", "threshold": 0.5},
    ],
    "missile_test": [
        {"treaty": "UN Charter", "article": "Article 2(4)", "relevance": "Threat of force", "threshold": 0.6},
        {"treaty": "MTCR Guidelines", "article": "Guidelines", "relevance": "Missile technology proliferation", "threshold": 0.5},
    ],
    "nuclear_activity": [
        {"treaty": "NPT", "article": "Article II-III", "relevance": "Non-proliferation obligations", "threshold": 0.8},
        {"treaty": "CTBT", "article": "Article 1", "relevance": "Nuclear test ban", "threshold": 0.7},
        {"treaty": "IAEA Safeguards", "article": "INFCIRC/153", "relevance": "Safeguards agreement compliance", "threshold": 0.6},
    ],
    "refugee_flow": [
        {"treaty": "Refugee Convention", "article": "Article 33", "relevance": "Non-refoulement principle", "threshold": 0.8},
        {"treaty": "UN Charter", "article": "Article 55", "relevance": "Human rights obligations", "threshold": 0.5},
    ],
}


def map_signal_to_treaties(
    signal_action: str,
    intensity: float = 0.5,
    country: str = "",
    target: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Map a geopolitical signal to relevant treaty articles using semantic search.

    Args:
        signal_action: Canonical signal action (e.g., "troop_movement")
        intensity: Signal intensity [0-1], higher = more likely to trigger treaty
        country: Source country (for bilateral treaty lookup)
        target: Target country/entity

    Returns:
        List of {treaty, article, relevance, threshold, triggered}
    """
    results = []
    
    # 1. Semantic Search via Vector Store
    store = get_vector_store()
    try:
        search_query = f"{signal_action} {'between ' + country + ' and ' + target if country and target else ''}"
        semantic_matches = store.search("treaties", search_query, k=3)
        for sm in semantic_matches:
            if sm["score"] > 0.4:  # Threshold for semantic match
                meta = sm.get("metadata", {})
                results.append({
                    "treaty": meta.get("treaty", sm["id"]),
                    "article": meta.get("article", "Unknown"),
                    "relevance": sm["text"][:100] + "...",
                    "threshold": 0.5,
                    "triggered": intensity >= 0.5,
                    "intensity": intensity,
                })
    except Exception as e:
        logger.warning(f"Vector search failed in signal mapper: {e}")

    # 2. Hardcoded Lookup (Fallback / Augmentation)
    action_lower = signal_action.lower().replace("sig_", "").replace(" ", "_")
    matches = SIGNAL_TREATY_MAP.get(action_lower, [])

    # Fuzzy matching if no direct match
    if not matches:
        for key, entries in SIGNAL_TREATY_MAP.items():
            if key in action_lower or action_lower in key:
                matches = entries
                break

    for entry in matches:
        # Avoid duplicates from semantic search
        if not any(r["treaty"] == entry["treaty"] and r["article"] == entry["article"] for r in results):
            triggered = intensity >= entry.get("threshold", 0.5)
            results.append({
                "treaty": entry["treaty"],
                "article": entry["article"],
                "relevance": entry["relevance"],
                "threshold": entry["threshold"],
                "triggered": triggered,
                "intensity": intensity,
            })

    # 3. Add country-specific bilateral treaties if available
    if country and target:
        bilateral = _find_bilateral_treaty(country, target, signal_action)
        if bilateral:
            existing = next((r for r in results if r["treaty"] == bilateral["treaty"]), None)
            if existing:
                existing["bilateral"] = True
            else:
                results.append(bilateral)

    return sorted(results, key=lambda r: r["triggered"], reverse=True)


def _find_bilateral_treaty(country: str, target: str, action: str) -> Optional[Dict[str, Any]]:
    """Find bilateral treaties between two countries relevant to a signal."""
    # Known bilateral treaty pairs (extensible)
    bilateral_pairs = [
        ("IND", "BTN", "India-Bhutan Friendship Treaty", "Article 2"),
        ("IND", "NPL", "India-Nepal Treaty of Peace and Friendship", "Article 5"),
        ("IND", "BGD", "India-Bangladesh Land Boundary Agreement", "Article 1"),
        ("IND", "LKA", "India-Sri Lanka Free Trade Agreement", "Article 1"),
        ("IND", "CHN", "India-China Border Peace Agreements", "1993 Protocol"),
        ("USA", "JPN", "US-Japan Security Treaty", "Article 5"),
        ("USA", "KOR", "US-ROK Mutual Defense Treaty", "Article 3"),
    ]

    c1 = country.upper()[:3]
    c2 = target.upper()[:3] if target else ""

    for a, b, treaty, article in bilateral_pairs:
        if (c1 == a and c2 == b) or (c1 == b and c2 == a):
            if any(word in action.lower() for word in ["troop", "military", "deploy", "border"]):
                return {
                    "treaty": treaty,
                    "article": article,
                    "relevance": f"Bilateral treaty between {country} and {target}",
                    "threshold": 0.4,
                    "triggered": True,
                    "intensity": 0.7,
                    "bilateral": True,
                }

    return None


def get_all_relevant_treaties(signals: List[Dict[str, Any]], country: str = "") -> List[Dict[str, Any]]:
    """Get all relevant treaty articles for a set of signals."""
    all_treaties: List[Dict[str, Any]] = []
    seen: set = set()

    for signal in signals:
        action = signal.get("action", signal.get("signal_code", ""))
        intensity = float(signal.get("intensity", signal.get("confidence", 0.5)))
        target = signal.get("target", "")
        results = map_signal_to_treaties(action, intensity, country, target)

        for r in results:
            key = f"{r['treaty']}|{r['article']}"
            if key not in seen:
                seen.add(key)
                all_treaties.append(r)

    return sorted(all_treaties, key=lambda r: (r["triggered"], r.get("intensity", 0)), reverse=True)
