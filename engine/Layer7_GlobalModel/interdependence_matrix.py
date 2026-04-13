"""
Phase 7.2 — Interdependence Matrix
=====================================

Defines geopolitical coupling strengths between theaters.

How strongly escalation in State A influences State B.

Two sources:
    1. Expert-defined weights (hand-coded domain knowledge)
    2. Empirical seed from tension_history.json correlations

Final weight = 0.70 × expert + 0.30 × empirical (when available).

Matrix is directional: (A → B) can differ from (B → A).
Example: IRN escalation has 0.75 effect on ISR, but ISR escalation
has 0.65 effect on IRN (Israel is reactive, not causal, for Iran).

Covers 14 theaters with ~50 significant dyads.
"""

from __future__ import annotations

import json
import logging
import os
import math
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("Layer7_GlobalModel.interdependence_matrix")

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
_TENSION_PATH = os.path.join(_DATA_DIR, "tension_history.json")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  EXPERT-DEFINED COUPLING WEIGHTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Format: (source, target) → weight ∈ [0, 1]
# Weight = strength of escalation contagion from source → target.
#
# These represent structural geopolitical realities:
#   - Alliance obligations
#   - Proxy relationships
#   - Geographic adjacency
#   - Trade/energy dependency
#   - Historical conflict coupling

EXPERT_WEIGHTS: Dict[Tuple[str, str], float] = {
    # ── Iran axis ─────────────────────────────────────────────────
    ("IRN", "ISR"): 0.75,    # Direct adversary
    ("ISR", "IRN"): 0.65,    # Israel reactive to Iran
    ("IRN", "USA"): 0.60,    # US–Iran strategic competition
    ("USA", "IRN"): 0.55,    # US influence on Iran lower
    ("IRN", "SAU"): 0.50,    # Regional rivalry
    ("SAU", "IRN"): 0.45,    # Saudi reactive
    ("IRN", "LBN"): 0.65,    # Hezbollah proxy link
    ("LBN", "IRN"): 0.30,    # Lebanon has weak return effect
    ("IRN", "SYR"): 0.55,    # Syrian theater proxy
    ("SYR", "IRN"): 0.25,    # Syria minor return

    # ── Israel axis ───────────────────────────────────────────────
    ("ISR", "LBN"): 0.70,    # Direct border adversary
    ("LBN", "ISR"): 0.60,    # Hezbollah actions affect Israel
    ("ISR", "USA"): 0.40,    # Israel–US influence
    ("USA", "ISR"): 0.50,    # US policy affects Israel theater
    ("ISR", "SYR"): 0.45,    # Golan dimension
    ("SYR", "ISR"): 0.35,    # Limited reverse

    # ── Russia–Ukraine axis ───────────────────────────────────────
    ("RUS", "UKR"): 0.90,    # Primary conflict dyad
    ("UKR", "RUS"): 0.80,    # Strong reverse coupling
    ("RUS", "USA"): 0.45,    # Superpower competition
    ("USA", "RUS"): 0.40,    # US influence on Russia limited
    ("RUS", "TUR"): 0.30,    # Black Sea dimension
    ("TUR", "RUS"): 0.25,    # Limited reverse

    # ── China–Taiwan axis ─────────────────────────────────────────
    ("CHN", "TWN"): 0.85,    # Unification pressure
    ("TWN", "CHN"): 0.50,    # Taiwan's effect is reactive
    ("CHN", "USA"): 0.55,    # Great power competition
    ("USA", "CHN"): 0.50,    # Mutual pressure
    ("CHN", "IND"): 0.35,    # Border disputes
    ("IND", "CHN"): 0.30,    # India reactive

    # ── India–Pakistan axis ───────────────────────────────────────
    ("IND", "PAK"): 0.80,    # Kashmir / nuclear rivals
    ("PAK", "IND"): 0.75,    # Mutual deterrence
    ("PAK", "IRN"): 0.20,    # Minor border issues
    ("IRN", "PAK"): 0.15,    # Minimal

    # ── Korean Peninsula ──────────────────────────────────────────
    ("PRK", "USA"): 0.55,    # Nuclear threat
    ("USA", "PRK"): 0.45,    # US pressure on DPRK
    ("PRK", "CHN"): 0.35,    # China buffer state
    ("CHN", "PRK"): 0.40,    # China influence on DPRK

    # ── Turkey regional ───────────────────────────────────────────
    ("TUR", "SYR"): 0.55,    # Northern Syria operations
    ("SYR", "TUR"): 0.40,    # Refugee / Kurdish dimension
    ("TUR", "IRN"): 0.20,    # Minor competition
    ("TUR", "ISR"): 0.15,    # Diplomatic tension only
    ("TUR", "LBN"): 0.10,    # Minimal

    # ── Gulf dynamics ─────────────────────────────────────────────
    ("SAU", "USA"): 0.35,    # Oil/security partnership
    ("USA", "SAU"): 0.30,    # US influence on Saudi
    ("SAU", "ISR"): 0.20,    # Normalization factor

    # ── Yemen / Horn of Africa ────────────────────────────────────
    ("YEM", "SAU"): 0.65,    # Houthi–Saudi conflict
    ("SAU", "YEM"): 0.55,    # Saudi intervention
    ("YEM", "IRN"): 0.40,    # Iranian proxy support
    ("IRN", "YEM"): 0.35,    # Iran influence on Yemen
    ("YEM", "ARE"): 0.40,    # UAE involvement
    ("SOM", "ETH"): 0.35,    # Horn of Africa tensions
    ("ETH", "SOM"): 0.30,    # Border / Al-Shabaab
    ("ETH", "ERI"): 0.45,    # Historical rivals
    ("ERI", "ETH"): 0.40,    # Boundary dispute
    ("SDN", "SSD"): 0.55,    # Post-partition tensions
    ("SSD", "SDN"): 0.50,    # Oil transit dependency
    ("SDN", "EGY"): 0.35,    # Nile / border issues
    ("EGY", "SDN"): 0.30,    # GERD dynamics
    ("ETH", "EGY"): 0.40,    # GERD dam dispute
    ("EGY", "ETH"): 0.35,    # Water security

    # ── Iraq dynamics ─────────────────────────────────────────────
    ("IRQ", "IRN"): 0.55,    # Iranian influence in Iraq
    ("IRN", "IRQ"): 0.50,    # Proxy militias
    ("IRQ", "USA"): 0.40,    # US presence legacy
    ("USA", "IRQ"): 0.35,    # Counter-ISIS
    ("IRQ", "TUR"): 0.30,    # Kurdish dimension
    ("IRQ", "SYR"): 0.35,    # ISIS corridor

    # ── Libya & N. Africa ─────────────────────────────────────────
    ("LBY", "TUR"): 0.40,    # Turkish military support
    ("TUR", "LBY"): 0.30,    # Ankara intervention
    ("LBY", "EGY"): 0.35,    # Egyptian border / Haftar
    ("EGY", "LBY"): 0.30,    # Egyptian influence
    ("LBY", "RUS"): 0.25,    # Wagner presence
    ("DZA", "MAR"): 0.40,    # Western Sahara rivalry
    ("MAR", "DZA"): 0.35,    # Diplomatic freeze

    # ── European security ─────────────────────────────────────────
    ("RUS", "POL"): 0.30,    # NATO frontline
    ("RUS", "DEU"): 0.25,    # Energy dependency
    ("RUS", "GBR"): 0.30,    # Strategic rivalry
    ("RUS", "FRA"): 0.25,    # Diplomatic competition
    ("USA", "GBR"): 0.35,    # Special relationship
    ("GBR", "USA"): 0.30,    # Alliance coupling
    ("FRA", "DEU"): 0.30,    # EU axis coordination
    ("DEU", "FRA"): 0.25,    # EU policy coupling
    ("RUS", "MDA"): 0.45,    # Transnistria
    ("RUS", "GEO"): 0.50,    # Abkhazia / S. Ossetia
    ("GEO", "RUS"): 0.40,    # Territorial threat
    ("RUS", "BLR"): 0.60,    # Union state
    ("BLR", "RUS"): 0.50,    # Belarus dependency
    ("AZE", "ARM"): 0.70,    # Nagorno-Karabakh
    ("ARM", "AZE"): 0.65,    # Active conflict
    ("TUR", "AZE"): 0.40,    # Turkic alliance
    ("TUR", "GRC"): 0.30,    # Aegean / Cyprus disputes
    ("GRC", "TUR"): 0.30,    # Cyprus dimension

    # ── Sahel crisis belt ─────────────────────────────────────────
    ("MLI", "FRA"): 0.30,    # Former colonial / Barkhane
    ("MLI", "RUS"): 0.25,    # Wagner replacement
    ("BFA", "MLI"): 0.40,    # Sahel alliance
    ("NER", "MLI"): 0.35,    # Coup contagion
    ("NGA", "NER"): 0.30,    # ECOWAS intervention threat
    ("TCD", "SDN"): 0.35,    # Border spillover

    # ── Great Lakes Africa ────────────────────────────────────────
    ("COD", "RWA"): 0.55,    # M23 proxy conflict
    ("RWA", "COD"): 0.45,    # Eastern DRC involvement
    ("COD", "UGA"): 0.30,    # ADF presence
    ("BDI", "RWA"): 0.35,    # Regional rivalry

    # ── Latin America ─────────────────────────────────────────────
    ("VEN", "USA"): 0.40,    # Sanctions / regime pressure
    ("USA", "VEN"): 0.25,    # Oil considerations
    ("VEN", "COL"): 0.45,    # Border tensions / migration
    ("COL", "VEN"): 0.35,    # Security spillover
    ("CUB", "USA"): 0.35,    # Embargo / geopolitics
    ("MEX", "USA"): 0.30,    # Cartel / border / trade
    ("USA", "MEX"): 0.25,    # Bilateral dependency
    ("BRA", "ARG"): 0.20,    # Mercosur partnership
    ("GUY", "VEN"): 0.40,    # Essequibo dispute

    # ── SE Asia / South China Sea ─────────────────────────────────
    ("CHN", "PHL"): 0.45,    # South China Sea dispute
    ("PHL", "CHN"): 0.35,    # Scarborough / Spratlys
    ("CHN", "VNM"): 0.40,    # Paracel Islands
    ("VNM", "CHN"): 0.35,    # Maritime sovereignty
    ("CHN", "JPN"): 0.45,    # Senkaku / Diaoyu
    ("JPN", "CHN"): 0.40,    # Security competition
    ("JPN", "USA"): 0.35,    # Alliance coupling
    ("USA", "JPN"): 0.35,    # Indo-Pacific anchor
    ("KOR", "PRK"): 0.70,    # Korean peninsula
    ("PRK", "KOR"): 0.65,    # DMZ deterrence
    ("KOR", "JPN"): 0.25,    # Historical tensions
    ("MMR", "CHN"): 0.30,    # China influence
    ("CHN", "MMR"): 0.25,    # Border / resources
    ("PHL", "USA"): 0.30,    # MDT alliance
    ("USA", "PHL"): 0.25,    # EDCA bases
    ("USA", "KOR"): 0.35,    # USFK alliance
    ("KOR", "USA"): 0.30,    # Alliance coupling
    ("USA", "TWN"): 0.55,    # TRA / strategic ambiguity
    ("TWN", "USA"): 0.45,    # Security dependency
    ("IDN", "CHN"): 0.20,    # Natuna Sea disputes
    ("AUS", "CHN"): 0.30,    # Strategic competition
    ("CHN", "AUS"): 0.25,    # Trade / Pacific influence
    ("AUS", "USA"): 0.30,    # AUKUS alliance

    # ── South Asia extended ───────────────────────────────────────
    ("IND", "LKA"): 0.25,    # Indian Ocean influence
    ("IND", "BGD"): 0.20,    # Border / water sharing
    ("IND", "NPL"): 0.15,    # Buffer state
    ("AFG", "PAK"): 0.45,    # Taliban / border
    ("PAK", "AFG"): 0.40,    # TTP safe havens
    ("AFG", "IRN"): 0.25,    # Western border
    ("AFG", "USA"): 0.20,    # Post-withdrawal monitoring

    # ── Central Asia ──────────────────────────────────────────────
    ("KAZ", "RUS"): 0.35,    # Russian influence
    ("RUS", "KAZ"): 0.30,    # Energy partner
    ("UZB", "AFG"): 0.20,    # Border spillover
    ("TKM", "AFG"): 0.15,    # Border security
    ("KGZ", "TJK"): 0.40,    # Border conflicts
    ("TJK", "KGZ"): 0.35,    # Water disputes

    # ── UAE extended ──────────────────────────────────────────────
    ("ARE", "IRN"): 0.30,    # Gulf tension
    ("IRN", "ARE"): 0.25,    # Island disputes
    ("ARE", "SAU"): 0.30,    # Gulf coordination
    ("ARE", "ISR"): 0.25,    # Abraham Accords
}

# ── Effective matrix (expert + empirical blend) ──────────────────
_EFFECTIVE_MATRIX: Dict[Tuple[str, str], float] = {}
_MATRIX_INITIALIZED = False


def get_weight(source: str, target: str) -> float:
    """Get the coupling weight from source → target.

    Returns 0.0 if no coupling exists.
    """
    _ensure_initialized()
    return _EFFECTIVE_MATRIX.get((source.upper(), target.upper()), 0.0)


def get_neighbors(country: str) -> List[Tuple[str, float]]:
    """Get all theaters that `country`'s escalation affects.

    Returns list of (target_country, weight) pairs sorted by weight desc.
    """
    _ensure_initialized()
    cc = country.upper()
    neighbors = [
        (b, w) for (a, b), w in _EFFECTIVE_MATRIX.items()
        if a == cc and w > 0.01
    ]
    return sorted(neighbors, key=lambda x: -x[1])


def get_incoming(country: str) -> List[Tuple[str, float]]:
    """Get all theaters whose escalation affects `country`.

    Returns list of (source_country, weight) pairs sorted by weight desc.
    """
    _ensure_initialized()
    cc = country.upper()
    incoming = [
        (a, w) for (a, b), w in _EFFECTIVE_MATRIX.items()
        if b == cc and w > 0.01
    ]
    return sorted(incoming, key=lambda x: -x[1])


def get_matrix() -> Dict[Tuple[str, str], float]:
    """Return the full effective interdependence matrix."""
    _ensure_initialized()
    return dict(_EFFECTIVE_MATRIX)


def top_couplings(n: int = 10) -> List[Tuple[Tuple[str, str], float]]:
    """Return the N strongest couplings in the matrix."""
    _ensure_initialized()
    return sorted(_EFFECTIVE_MATRIX.items(), key=lambda x: -x[1])[:n]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Empirical Seeding from tension_history.json
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def seed_from_tension_history() -> Dict[Tuple[str, str], float]:
    """Compute pairwise Pearson correlation from historical tension data.

    Returns a dict of (country_a, country_b) → correlation ∈ [0, 1].
    Only positive correlations are returned (negative = decoupled).
    """
    if not os.path.exists(_TENSION_PATH):
        logger.info("[MATRIX] No tension_history.json found — skipping empirical seed")
        return {}

    try:
        with open(_TENSION_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, IOError):
        logger.warning("[MATRIX] Failed to read tension_history.json")
        return {}

    if not isinstance(data, dict):
        return {}

    # Build per-country time series
    country_series: Dict[str, List[float]] = {}
    dates = sorted(data.keys())

    for date in dates:
        day_data = data[date]
        if not isinstance(day_data, dict):
            continue
        for cc, entries in day_data.items():
            cc = cc.upper()
            if isinstance(entries, list) and entries:
                tension = float(entries[0].get("tension", 0.0))
            elif isinstance(entries, dict):
                tension = float(entries.get("tension", 0.0))
            else:
                continue
            if cc not in country_series:
                country_series[cc] = []
            country_series[cc].append(tension)

    # Compute pairwise Pearson correlation
    correlations: Dict[Tuple[str, str], float] = {}
    countries = sorted(country_series.keys())

    for i, ca in enumerate(countries):
        for cb in countries[i + 1:]:
            sa = country_series[ca]
            sb = country_series[cb]
            # Align to same length (min)
            n = min(len(sa), len(sb))
            if n < 3:
                continue
            corr = _pearson(sa[:n], sb[:n])
            if corr is not None and corr > 0.0:
                # Bidirectional: same correlation both ways from empirical
                correlations[(ca, cb)] = round(corr, 4)
                correlations[(cb, ca)] = round(corr, 4)

    logger.info(
        "[MATRIX] Computed %d empirical correlations from %d countries, %d dates",
        len(correlations), len(countries), len(dates),
    )
    return correlations


def _pearson(x: List[float], y: List[float]) -> Optional[float]:
    """Pearson correlation coefficient. Returns None if degenerate."""
    n = len(x)
    if n < 3:
        return None
    mx = sum(x) / n
    my = sum(y) / n
    sx = [xi - mx for xi in x]
    sy = [yi - my for yi in y]
    num = sum(a * b for a, b in zip(sx, sy))
    dx = math.sqrt(sum(a * a for a in sx))
    dy = math.sqrt(sum(b * b for b in sy))
    if dx < 1e-12 or dy < 1e-12:
        return None
    return num / (dx * dy)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Matrix Initialization
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EXPERT_BLEND = 0.70
EMPIRICAL_BLEND = 0.30


def _ensure_initialized():
    """Initialize the effective matrix once."""
    global _MATRIX_INITIALIZED
    if _MATRIX_INITIALIZED:
        return

    # Start with expert weights
    _EFFECTIVE_MATRIX.update(EXPERT_WEIGHTS)

    # Blend with empirical correlations
    empirical = seed_from_tension_history()
    for (a, b), emp_corr in empirical.items():
        expert_w = EXPERT_WEIGHTS.get((a, b), 0.0)
        if expert_w > 0:
            # Blend: 70% expert + 30% empirical
            blended = EXPERT_BLEND * expert_w + EMPIRICAL_BLEND * emp_corr
            _EFFECTIVE_MATRIX[(a, b)] = round(blended, 4)
        else:
            # No expert weight — use pure empirical but dampened
            if emp_corr > 0.30:  # only add if meaningful correlation
                _EFFECTIVE_MATRIX[(a, b)] = round(emp_corr * 0.5, 4)

    _MATRIX_INITIALIZED = True
    logger.info(
        "[MATRIX] Initialized: %d expert dyads + %d empirical → %d effective entries",
        len(EXPERT_WEIGHTS), len(empirical), len(_EFFECTIVE_MATRIX),
    )
