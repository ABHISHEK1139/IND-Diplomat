"""
Phase 7.1 — Global State Registry
====================================

Maintains a live registry of all active geopolitical theaters.
Each theater tracks its current SRE, trajectory probability,
velocity, and last-update timestamp.

Persists to ``data/global_state.json`` so the system retains
cross-session awareness of the global risk surface.

Supports EVERY sovereign state via ISO-3166-1 alpha-3 codes.
Any country code passed to ``update_theater()`` is accepted
dynamically — no whitelist restriction.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger("Layer7_GlobalModel.global_state")

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
_STATE_PATH = os.path.join(_DATA_DIR, "global_state.json")
_file_lock = threading.Lock()

# ── Comprehensive ISO-3166-1 alpha-3 country codes ──────────────
# The system accepts ANY valid country code dynamically.
# This reference list covers all sovereign states and key territories.
THEATER_CODES = [
    # ── Middle East & North Africa ────────────────────────────────
    "IRN",  # Iran               "ISR",  # Israel
    "SAU",  # Saudi Arabia       "ARE",  # UAE
    "IRQ",  # Iraq               "SYR",  # Syria
    "LBN",  # Lebanon            "JOR",  # Jordan
    "YEM",  # Yemen              "OMN",  # Oman
    "KWT",  # Kuwait             "BHR",  # Bahrain
    "QAT",  # Qatar              "PSE",  # Palestine
    "EGY",  # Egypt              "LBY",  # Libya
    "TUN",  # Tunisia            "DZA",  # Algeria
    "MAR",  # Morocco            "SDN",  # Sudan
    # ── Europe ───────────────────────────────────────────────────
    "GBR",  # United Kingdom     "FRA",  # France
    "DEU",  # Germany            "ITA",  # Italy
    "ESP",  # Spain              "POL",  # Poland
    "UKR",  # Ukraine            "ROU",  # Romania
    "NLD",  # Netherlands        "BEL",  # Belgium
    "CZE",  # Czechia            "GRC",  # Greece
    "PRT",  # Portugal           "SWE",  # Sweden
    "HUN",  # Hungary            "AUT",  # Austria
    "CHE",  # Switzerland        "BGR",  # Bulgaria
    "DNK",  # Denmark            "FIN",  # Finland
    "SVK",  # Slovakia           "NOR",  # Norway
    "IRL",  # Ireland            "HRV",  # Croatia
    "LTU",  # Lithuania          "SVN",  # Slovenia
    "LVA",  # Latvia             "EST",  # Estonia
    "CYP",  # Cyprus             "LUX",  # Luxembourg
    "MLT",  # Malta              "SRB",  # Serbia
    "BIH",  # Bosnia             "ALB",  # Albania
    "MKD",  # N. Macedonia       "MNE",  # Montenegro
    "MDA",  # Moldova            "BLR",  # Belarus
    "ISL",  # Iceland            "GEO",  # Georgia
    "ARM",  # Armenia            "AZE",  # Azerbaijan
    # ── Americas ─────────────────────────────────────────────────
    "USA",  # United States      "CAN",  # Canada
    "MEX",  # Mexico             "BRA",  # Brazil
    "ARG",  # Argentina          "COL",  # Colombia
    "CHL",  # Chile              "PER",  # Peru
    "VEN",  # Venezuela          "ECU",  # Ecuador
    "BOL",  # Bolivia            "PRY",  # Paraguay
    "URY",  # Uruguay            "GUY",  # Guyana
    "SUR",  # Suriname           "CUB",  # Cuba
    "HTI",  # Haiti              "DOM",  # Dominican Rep.
    "GTM",  # Guatemala          "HND",  # Honduras
    "SLV",  # El Salvador        "NIC",  # Nicaragua
    "CRI",  # Costa Rica         "PAN",  # Panama
    "JAM",  # Jamaica            "TTO",  # Trinidad
    # ── East & Southeast Asia ────────────────────────────────────
    "CHN",  # China              "JPN",  # Japan
    "KOR",  # South Korea        "PRK",  # North Korea
    "TWN",  # Taiwan             "MNG",  # Mongolia
    "VNM",  # Vietnam            "THA",  # Thailand
    "IDN",  # Indonesia          "MYS",  # Malaysia
    "PHL",  # Philippines        "SGP",  # Singapore
    "MMR",  # Myanmar            "KHM",  # Cambodia
    "LAO",  # Laos               "BRN",  # Brunei
    "TLS",  # Timor-Leste
    # ── South & Central Asia ─────────────────────────────────────
    "IND",  # India              "PAK",  # Pakistan
    "BGD",  # Bangladesh         "LKA",  # Sri Lanka
    "NPL",  # Nepal              "AFG",  # Afghanistan
    "KAZ",  # Kazakhstan         "UZB",  # Uzbekistan
    "TKM",  # Turkmenistan       "TJK",  # Tajikistan
    "KGZ",  # Kyrgyzstan
    # ── Russia & Eurasia ─────────────────────────────────────────
    "RUS",  # Russia             "TUR",  # Turkey
    # ── Sub-Saharan Africa ───────────────────────────────────────
    "NGA",  # Nigeria            "ZAF",  # South Africa
    "KEN",  # Kenya              "ETH",  # Ethiopia
    "GHA",  # Ghana              "TZA",  # Tanzania
    "UGA",  # Uganda             "AGO",  # Angola
    "MOZ",  # Mozambique         "MDG",  # Madagascar
    "CMR",  # Cameroon           "CIV",  # Ivory Coast
    "NER",  # Niger              "BFA",  # Burkina Faso
    "MLI",  # Mali               "MWI",  # Malawi
    "ZMB",  # Zambia             "SEN",  # Senegal
    "TCD",  # Chad               "SOM",  # Somalia
    "ZWE",  # Zimbabwe           "RWA",  # Rwanda
    "BEN",  # Benin              "BDI",  # Burundi
    "SSD",  # South Sudan        "TGO",  # Togo
    "SLE",  # Sierra Leone       "LBR",  # Liberia
    "CAF",  # Central African R. "COG",  # Congo
    "COD",  # DR Congo           "GAB",  # Gabon
    "MRT",  # Mauritania         "ERI",  # Eritrea
    "NAM",  # Namibia            "BWA",  # Botswana
    "LSO",  # Lesotho            "GMB",  # Gambia
    "GNB",  # Guinea-Bissau      "GIN",  # Guinea
    "SWZ",  # Eswatini           "DJI",  # Djibouti
    # ── Oceania ──────────────────────────────────────────────────
    "AUS",  # Australia          "NZL",  # New Zealand
    "PNG",  # Papua New Guinea   "FJI",  # Fiji
    "SLB",  # Solomon Islands
]


@dataclass
class TheaterState:
    """State snapshot of a single geopolitical theater."""
    country: str
    current_sre: float = 0.0
    prob_high_14d: float = 0.0
    velocity: float = 0.0
    ndi: float = 0.0
    expansion_mode: str = "IDLE"
    last_updated: Optional[str] = None   # ISO-8601
    contagion_received: float = 0.0      # accumulator from other theaters
    signal_summary: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "TheaterState":
        known = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in d.items() if k in known})


# ── In-memory registry ───────────────────────────────────────────
GLOBAL_THEATERS: Dict[str, TheaterState] = {}


def _ensure_loaded():
    """Load persisted state on first access."""
    if GLOBAL_THEATERS:
        return
    _load_from_disk()


def update_theater(
    country: str,
    sre: float,
    prob_high: float,
    velocity: float = 0.0,
    ndi: float = 0.0,
    expansion_mode: str = "IDLE",
    signal_summary: Optional[Dict[str, float]] = None,
) -> TheaterState:
    """Upsert a theater's state and persist.

    Called once per analysis cycle with the target country's metrics.
    """
    _ensure_loaded()
    cc = country.upper().strip()
    if not cc:
        cc = "UNKNOWN"

    now = datetime.now(timezone.utc).isoformat()

    if cc in GLOBAL_THEATERS:
        t = GLOBAL_THEATERS[cc]
        t.current_sre = round(float(sre), 4)
        t.prob_high_14d = round(float(prob_high), 4)
        t.velocity = round(float(velocity), 4)
        t.ndi = round(float(ndi), 4)
        t.expansion_mode = str(expansion_mode)
        t.last_updated = now
        if signal_summary:
            t.signal_summary = signal_summary
    else:
        GLOBAL_THEATERS[cc] = TheaterState(
            country=cc,
            current_sre=round(float(sre), 4),
            prob_high_14d=round(float(prob_high), 4),
            velocity=round(float(velocity), 4),
            ndi=round(float(ndi), 4),
            expansion_mode=str(expansion_mode),
            last_updated=now,
            signal_summary=signal_summary or {},
        )

    _save_to_disk()
    logger.info(
        "[GLOBAL] Theater %s updated: SRE=%.3f  P(HIGH)=%.1f%%  vel=%.3f",
        cc, sre, prob_high * 100, velocity,
    )
    return GLOBAL_THEATERS[cc]


def get_theater(country: str) -> Optional[TheaterState]:
    """Get a single theater's state."""
    _ensure_loaded()
    return GLOBAL_THEATERS.get(country.upper().strip())


def get_all_theaters() -> Dict[str, TheaterState]:
    """Get all registered theaters."""
    _ensure_loaded()
    return dict(GLOBAL_THEATERS)


def get_active_theaters(sre_threshold: float = 0.01) -> Dict[str, TheaterState]:
    """Get theaters with SRE above a minimum threshold."""
    _ensure_loaded()
    return {
        cc: t for cc, t in GLOBAL_THEATERS.items()
        if t.current_sre > sre_threshold
    }


def decay_contagion(factor: float = 0.80):
    """Decay the contagion_received accumulator each cycle.

    Prevents stale contagion from previous cycles from
    persisting indefinitely.  Default decay = 20% per cycle.
    """
    _ensure_loaded()
    for t in GLOBAL_THEATERS.values():
        t.contagion_received = round(t.contagion_received * factor, 6)


def reset_contagion():
    """Zero out all contagion accumulators."""
    _ensure_loaded()
    for t in GLOBAL_THEATERS.values():
        t.contagion_received = 0.0


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Persistence
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def _load_from_disk():
    """Load global_state.json into GLOBAL_THEATERS."""
    with _file_lock:
        if not os.path.exists(_STATE_PATH):
            return
        try:
            with open(_STATE_PATH, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                for cc, d in data.items():
                    if isinstance(d, dict):
                        GLOBAL_THEATERS[cc] = TheaterState.from_dict(d)
            logger.info("[GLOBAL] Loaded %d theaters from disk", len(GLOBAL_THEATERS))
        except (json.JSONDecodeError, IOError) as exc:
            logger.warning("[GLOBAL] Failed to load state: %s", exc)


def _save_to_disk():
    """Persist GLOBAL_THEATERS to JSON."""
    with _file_lock:
        os.makedirs(os.path.dirname(_STATE_PATH), exist_ok=True)
        payload = {cc: t.to_dict() for cc, t in GLOBAL_THEATERS.items()}
        with open(_STATE_PATH, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)
