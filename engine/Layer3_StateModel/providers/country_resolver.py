"""
Deterministic country resolver for Layer-3 providers.
"""

from __future__ import annotations

import csv
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from Config.paths import PROJECT_ROOT, GLOBAL_RISK_DATA_PATH

try:
    from engine.Layer2_Knowledge.normalization.entity_registry import entity_registry
except Exception:  # pragma: no cover - fallback path
    entity_registry = None


# CAMEO 3-letter codes that differ from standard ISO 3166-1 alpha-3.
# GDELT uses CAMEO codes; we must correct them to standard ISO3.
CAMEO_TO_ISO3: Dict[str, str] = {
    "ROM": "ROU",  # Romania
    "TMP": "TLS",  # East Timor / Timor-Leste
    "MTN": "MNE",  # Montenegro
    "IMY": "IMN",  # Isle of Man (not standard ISO3 but map it)
    "COL": "COL",  # CAMEO spells Colombia as "Columbia" but code is same
    # Regional codes (not countries — skip these for country-level resolution)
    "WSB": None, "BAG": None, "GZS": None, "AFR": None, "ASA": None,
    "BLK": None, "CRB": None, "CAU": None, "CFR": None, "CAS": None,
    "CEU": None, "EIN": None, "EAF": None, "EEU": None, "EUR": None,
    "LAM": None, "MEA": None, "MDT": None, "NAF": None, "NMR": None,
    "PGS": None, "SCN": None, "SAM": None, "SAS": None, "SEA": None,
    "SAF": None, "WAF": None, "WST": None,
}

# FIPS to ISO2 mapping for GDELT geo fields (Actor1Geo_CountryCode, etc)
# which use FIPS 10-4 codes, not ISO.
FIPS_TO_ISO2: Dict[str, str] = {
    "AS": "AU",  # Australia
    "BM": "MM",  # Myanmar/Burma
    "CE": "LK",  # Sri Lanka (Ceylon)
    "CH": "CN",  # China
    "EI": "IE",  # Ireland (Eire)
    "GM": "DE",  # Germany
    "IN": "IN",  # India (same)
    "JA": "JP",  # Japan
    "KN": "KP",  # North Korea
    "KS": "KR",  # South Korea
    "PK": "PK",  # Pakistan (same)
    "RS": "RU",  # Russia
    "SN": "SG",  # Singapore
    "TU": "TR",  # Turkey
    "TW": "TW",  # Taiwan (same)
    "UK": "GB",  # United Kingdom
    "UP": "UA",  # Ukraine
}

ISO2_TO_ISO3: Dict[str, str] = {
    "US": "USA",
    "GB": "GBR",
    "CN": "CHN",
    "IN": "IND",
    "RU": "RUS",
    "TR": "TUR",
    "TW": "TWN",
    "KP": "PRK",
    "KR": "KOR",
    "IR": "IRN",
    "SY": "SYR",
    "CU": "CUB",
    "VE": "VEN",
    "MM": "MMR",
    "BY": "BLR",
    "AU": "AUS",
    "JP": "JPN",
    "DE": "DEU",
    "FR": "FRA",
    "IE": "IRL",
    "UA": "UKR",
    "SG": "SGP",
    "LK": "LKA",
    "PK": "PAK",
}

NAME_TO_ISO3: Dict[str, str] = {
    "UNITED STATES": "USA",
    "UNITED STATES OF AMERICA": "USA",
    "U S A": "USA",
    "US": "USA",
    "USA": "USA",
    "AMERICA": "USA",
    "UNITED KINGDOM": "GBR",
    "GREAT BRITAIN": "GBR",
    "BRITAIN": "GBR",
    "ENGLAND": "GBR",
    "RUSSIAN FEDERATION": "RUS",
    "RUSSIA": "RUS",
    "PEOPLES REPUBLIC OF CHINA": "CHN",
    "PEOPLE S REPUBLIC OF CHINA": "CHN",
    "CHINA": "CHN",
    "PRC": "CHN",
    "TAIWAN": "TWN",
    "REPUBLIC OF CHINA": "TWN",
    "TURKEY": "TUR",
    "TURKIYE": "TUR",
    "REPUBLIC OF TURKEY": "TUR",
    "REPUBLIC OF TURKIYE": "TUR",
    "KOREA NORTH": "PRK",
    "NORTH KOREA": "PRK",
    "DPRK": "PRK",
    "KOREA SOUTH": "KOR",
    "SOUTH KOREA": "KOR",
    "REPUBLIC OF KOREA": "KOR",
    "KOREA": "KOR",
    "IRAN": "IRN",
    "ISLAMIC REPUBLIC OF IRAN": "IRN",
    "SYRIA": "SYR",
    "SYRIAN ARAB REPUBLIC": "SYR",
    "CUBA": "CUB",
    "VENEZUELA": "VEN",
    "BOLIVARIAN REPUBLIC OF VENEZUELA": "VEN",
    "BURMA": "MMR",
    "MYANMAR": "MMR",
    "BELARUS": "BLR",
    "IRAQ": "IRQ",
    "LEBANON": "LBN",
    "BALKANS": "SRB",
    "CONGO": "COD",
    "DRCONGO": "COD",
    "DR CONGO": "COD",
    "DEMOCRATIC REPUBLIC OF CONGO": "COD",
    "CAR": "CAF",
    "CENTRAL AFRICAN REPUBLIC": "CAF",
    "NICARAGUA": "NIC",
    "YEMEN": "YEM",
    "LIBYA": "LBY",
    "SOMALIA": "SOM",
    "ZIMBABWE": "ZWE",
    "SAUDI ARABIA": "SAU",
    "INDIA": "IND",
    "JAPAN": "JPN",
    "PAKISTAN": "PAK",
    "BANGLADESH": "BGD",
    "AFGHANISTAN": "AFG",
    "UKRAINE": "UKR",
    "GERMANY": "DEU",
    "FRANCE": "FRA",
    "AUSTRALIA": "AUS",
    "CANADA": "CAN",
    "MEXICO": "MEX",
    "BRAZIL": "BRA",
    "SOUTH AFRICA": "ZAF",
    "ISRAEL": "ISR",
    "EGYPT": "EGY",
    "ALGERIA": "DZA",
    "NEW ZEALAND": "NZL",
    "ORGANIZATION OF AMERICAN STATES": "OAS",
    "LEAGUE OF ARAB STATES": "LAS",
    "COCOM": "CCM",
}

# Base COW mapping with optional expansion from local static map.
COW_TO_ISO3: Dict[int, str] = {
    2: "USA",
    20: "CAN",
    31: "BHS",
    40: "CUB",
    70: "MEX",
    90: "GTM",
    91: "HND",
    93: "NIC",
    94: "CRI",
    95: "PAN",
    100: "COL",
    101: "VEN",
    130: "ECU",
    135: "PER",
    140: "BRA",
    145: "BOL",
    150: "PRY",
    155: "CHL",
    160: "ARG",
    165: "URY",
    200: "GBR",
    205: "IRL",
    210: "NLD",
    211: "BEL",
    220: "FRA",
    230: "ESP",
    235: "PRT",
    255: "DEU",
    260: "POL",
    265: "AUT",
    290: "POL",
    300: "ITA",
    310: "GRC",
    325: "HUN",
    339: "ALB",
    345: "YUG",
    350: "BGR",
    352: "ROU",
    355: "RUS",
    365: "RUS",
    369: "UKR",
    380: "SWE",
    385: "NOR",
    390: "DNK",
    560: "ZAF",
    625: "SDN",
    630: "IRN",
    640: "TUR",
    645: "IRQ",
    651: "EGY",
    652: "SYR",
    660: "JOR",
    663: "ISR",
    666: "ISR",
    670: "SAU",
    678: "YEM",
    690: "KWT",
    694: "QAT",
    698: "OMN",
    700: "AFG",
    710: "CHN",
    712: "MNG",
    713: "TWN",
    731: "PRK",
    732: "KOR",
    740: "JPN",
    750: "IND",
    760: "BTN",
    770: "PAK",
    771: "BGD",
    775: "MMR",
    780: "LKA",
    790: "NPL",
    800: "THA",
    811: "KHM",
    812: "LAO",
    816: "VNM",
    817: "MYS",
    820: "IDN",
    830: "PHL",
    840: "TLS",
    850: "PNG",
    900: "AUS",
    920: "NZL",
}

_OPTIONAL_COW_LOADED = False


def _strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def normalize_country_name(value: Any) -> str:
    token = _strip_accents(str(value or "").strip())
    token = token.replace("&", " AND ")
    token = token.replace("/", " ")
    token = token.replace("-", " ")
    token = token.replace(",", " ")
    token = re.sub(r"[\[\]\(\)\.:;\"']", " ", token)
    token = re.sub(r"\s+", " ", token).strip().upper()
    return token


def _load_optional_cow_map() -> None:
    global _OPTIONAL_COW_LOADED
    if _OPTIONAL_COW_LOADED:
        return
    _OPTIONAL_COW_LOADED = True
    candidates = [
        GLOBAL_RISK_DATA_PATH / "country_master_key.csv",
        PROJECT_ROOT / "data" / "global_risk" / "country_master_key.csv",
        PROJECT_ROOT / "global_risk_data" / "country_master_key.csv",
    ]
    for path in candidates:
        if not path.exists():
            continue
        try:
            with open(path, "r", encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                for row in reader:
                    cow = row.get("COW_ID")
                    iso3 = str(row.get("ISO3") or "").strip().upper()
                    if not cow or not iso3:
                        continue
                    try:
                        COW_TO_ISO3[int(float(cow))] = iso3
                    except Exception:
                        continue
        except Exception:
            continue


def _from_entity_registry(value: str) -> Optional[str]:
    if entity_registry is None:
        return None
    for candidate in (value, normalize_country_name(value)):
        resolved = entity_registry.resolve(candidate)
        if not resolved:
            continue
        token = str(resolved).strip().upper()
        if len(token) == 3 and token.isalpha():
            return token
    return None


def resolve_country_to_iso3(value: Any, extra_aliases: Optional[Dict[str, str]] = None) -> Optional[str]:
    """
    Resolve a country label/code into ISO3.
    """
    if value is None:
        return None

    _load_optional_cow_map()

    # Numeric COW handling.
    try:
        numeric = int(float(str(value).strip()))
        mapped = COW_TO_ISO3.get(numeric)
        if mapped:
            return mapped
    except Exception:
        pass

    raw = str(value).strip()
    if not raw:
        return None

    upper_raw = raw.upper()
    if len(upper_raw) == 3 and upper_raw.isalpha():
        # Check if it's a CAMEO code that needs correction
        if upper_raw in CAMEO_TO_ISO3:
            corrected = CAMEO_TO_ISO3[upper_raw]
            if corrected is None:
                return None  # Regional code, not a country
            return corrected
        return upper_raw
    if len(upper_raw) == 2 and upper_raw.isalpha():
        # Try FIPS first (GDELT geo fields), then ISO2
        fips_iso2 = FIPS_TO_ISO2.get(upper_raw)
        if fips_iso2:
            mapped = ISO2_TO_ISO3.get(fips_iso2)
            if mapped:
                return mapped
        mapped = ISO2_TO_ISO3.get(upper_raw)
        if mapped:
            return mapped

    normalized = normalize_country_name(raw)
    if not normalized:
        return None

    merged_aliases: Dict[str, str] = {}
    merged_aliases.update(NAME_TO_ISO3)
    if extra_aliases:
        for key, iso3 in extra_aliases.items():
            merged_aliases[normalize_country_name(key)] = str(iso3).strip().upper()

    mapped = merged_aliases.get(normalized)
    if mapped:
        return mapped

    resolved = _from_entity_registry(raw)
    if resolved:
        return resolved

    return None


def resolve_iso3_candidates_from_text(text: str) -> List[str]:
    """
    Extract one or more ISO3 candidates from noisy text.
    """
    if not text:
        return []
    tokens = re.split(r"[;\|/\[\]\(\),]", str(text))
    found: List[str] = []
    for token in tokens:
        piece = token.strip()
        if not piece or piece == "-0-":
            continue
        # OFAC programs often contain code suffixes like RUSSIA-EO14024.
        piece = re.sub(r"-EO\d+", "", piece, flags=re.IGNORECASE)
        piece = re.sub(r"\s+", " ", piece).strip()
        iso3 = resolve_country_to_iso3(piece)
        if iso3 and iso3 not in found:
            found.append(iso3)
            continue

        normalized = normalize_country_name(piece)
        words = normalized.split()
        # Backoff matching for noisy tokens like "CAATSA - RUSSIA".
        for word in words:
            iso3 = resolve_country_to_iso3(word)
            if iso3 and iso3 not in found:
                found.append(iso3)
        for idx in range(max(0, len(words) - 1)):
            pair = f"{words[idx]} {words[idx + 1]}"
            iso3 = resolve_country_to_iso3(pair)
            if iso3 and iso3 not in found:
                found.append(iso3)
    return found


def map_cow_to_iso3(value: Any) -> Optional[str]:
    _load_optional_cow_map()
    try:
        return COW_TO_ISO3.get(int(float(str(value).strip())))
    except Exception:
        return None


def normalize_iso3_list(values: Iterable[Any]) -> List[str]:
    ordered: List[str] = []
    for value in values:
        iso3 = resolve_country_to_iso3(value)
        if iso3 and iso3 not in ordered:
            ordered.append(iso3)
    return ordered
