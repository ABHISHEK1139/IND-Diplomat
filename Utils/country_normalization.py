"""
Shared country normalization helpers.

These helpers keep country handling consistent across search, relevance
filtering, and GDELT queries. The project mostly reasons in ISO-3 codes,
but some collection paths use human-readable names for search quality.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Dict, List, Optional

# Canonical search/display names for the countries the runtime currently
# handles explicitly across collection and directed-search paths.
ISO_TO_NAME: Dict[str, str] = {
    "AFG": "Afghanistan",
    "ARE": "United Arab Emirates",
    "BRA": "Brazil",
    "CAN": "Canada",
    "CHE": "Switzerland",
    "CHN": "China",
    "COD": "Democratic Republic of the Congo",
    "COG": "Republic of the Congo",
    "CUB": "Cuba",
    "CZE": "Czechia",
    "DEU": "Germany",
    "EGY": "Egypt",
    "ECU": "Ecuador",
    "ETH": "Ethiopia",
    "ESP": "Spain",
    "FRA": "France",
    "GBR": "United Kingdom",
    "IDN": "Indonesia",
    "IND": "India",
    "IRN": "Iran",
    "IRQ": "Iraq",
    "ISR": "Israel",
    "ITA": "Italy",
    "JPN": "Japan",
    "KOR": "South Korea",
    "LBN": "Lebanon",
    "LBY": "Libya",
    "MEX": "Mexico",
    "MMR": "Myanmar",
    "NLD": "Netherlands",
    "PAK": "Pakistan",
    "PRK": "North Korea",
    "RUS": "Russia",
    "SAU": "Saudi Arabia",
    "SYR": "Syria",
    "TUR": "Turkey",
    "TWN": "Taiwan",
    "UKR": "Ukraine",
    "USA": "United States",
    "VEN": "Venezuela",
    "YEM": "Yemen",
}


def _normalize_country_key(value: str) -> str:
    """Normalize country labels for tolerant exact matching."""
    raw = unicodedata.normalize("NFKD", str(value or ""))
    raw = raw.encode("ascii", "ignore").decode("ascii")
    raw = raw.upper().strip()
    raw = raw.replace("&", " AND ")
    raw = re.sub(r"[^\w\s]", " ", raw)
    raw = re.sub(r"\s+", " ", raw).strip()
    return raw


NAME_TO_ISO: Dict[str, str] = {
    _normalize_country_key(name): iso
    for iso, name in ISO_TO_NAME.items()
}
NAME_TO_ISO.update(
    {
        "AMERICA": "USA",
        "BRITAIN": "GBR",
        "CONGO BRAZZAVILLE": "COG",
        "CONGO KINSHASA": "COD",
        "COTE D IVOIRE": "CIV",
        "CZECH REPUBLIC": "CZE",
        "DEMOCRATIC PEOPLE S REPUBLIC OF KOREA": "PRK",
        "DEMOCRATIC REPUBLIC OF CONGO": "COD",
        "DEMOCRATIC REPUBLIC OF THE CONGO": "COD",
        "DPRK": "PRK",
        "DR CONGO": "COD",
        "GREAT BRITAIN": "GBR",
        "IRAN ISLAMIC REPUBLIC OF": "IRN",
        "ISLAMIC REPUBLIC OF IRAN": "IRN",
        "IVORY COAST": "CIV",
        "KOREA DPR": "PRK",
        "KOREA REPUBLIC OF": "KOR",
        "LAO PDR": "LAO",
        "NORTH KOREA": "PRK",
        "PEOPLE S REPUBLIC OF CHINA": "CHN",
        "PRC": "CHN",
        "REPUBLIC OF CONGO": "COG",
        "REPUBLIC OF KOREA": "KOR",
        "RUSSIAN FEDERATION": "RUS",
        "SOUTH KOREA": "KOR",
        "SYRIAN ARAB REPUBLIC": "SYR",
        "THE NETHERLANDS": "NLD",
        "TURKIYE": "TUR",
        "U K": "GBR",
        "U S": "USA",
        "U S A": "USA",
        "UAE": "ARE",
        "UK": "GBR",
        "UNITED ARAB EMIRATES": "ARE",
        "UNITED KINGDOM OF GREAT BRITAIN AND NORTHERN IRELAND": "GBR",
        "UNITED STATES OF AMERICA": "USA",
        "US": "USA",
    }
)


def build_country_alias_index(aliases_by_iso: Dict[str, List[str]]) -> Dict[str, str]:
    """Build a reverse alias -> ISO lookup from a relevance alias table."""
    index: Dict[str, str] = {}
    for iso, aliases in aliases_by_iso.items():
        code = str(iso or "").strip().upper()
        if not code:
            continue
        index[_normalize_country_key(code)] = code
        canonical = ISO_TO_NAME.get(code)
        if canonical:
            index[_normalize_country_key(canonical)] = code
        for alias in aliases:
            norm = _normalize_country_key(alias)
            if norm:
                index[norm] = code
    return index


def _resolve_with_optional_libraries(country: str) -> str:
    """
    Best-effort external resolver.

    This keeps the runtime dependency-free but uses optional libraries if
    the environment already has them installed.
    """
    raw = str(country or "").strip()
    if not raw:
        return ""

    try:
        import pycountry  # type: ignore

        match = pycountry.countries.lookup(raw)
        alpha3 = getattr(match, "alpha_3", "")
        if isinstance(alpha3, str) and len(alpha3) == 3:
            return alpha3.upper()
    except Exception:
        pass

    try:
        import country_converter as coco  # type: ignore

        iso = str(coco.convert(names=[raw], to="ISO3")[0] or "").strip().upper()
        if iso and iso != "NOT FOUND":
            return iso
    except Exception:
        pass

    return ""


def resolve_country_iso(
    country: str,
    *,
    alias_index: Optional[Dict[str, str]] = None,
) -> str:
    """Resolve a country name, alias, or ISO code to ISO-3."""
    raw = str(country or "").strip()
    if not raw:
        return ""

    upper = raw.upper()
    if len(upper) == 3 and upper.isalpha():
        return upper

    normalized = _normalize_country_key(raw)
    if alias_index:
        iso = alias_index.get(normalized, "")
        if iso:
            return iso

    iso = NAME_TO_ISO.get(normalized, "")
    if iso:
        return iso

    return _resolve_with_optional_libraries(raw)


def resolve_country_name(
    country: str,
    *,
    alias_index: Optional[Dict[str, str]] = None,
) -> str:
    """Return a canonical display/search name when one is known."""
    raw = str(country or "").strip()
    if not raw:
        return ""

    iso = resolve_country_iso(raw, alias_index=alias_index)
    if not iso:
        return raw

    canonical = ISO_TO_NAME.get(iso, "")
    if canonical:
        return canonical

    return raw if len(raw) != 3 else iso


__all__ = [
    "ISO_TO_NAME",
    "NAME_TO_ISO",
    "build_country_alias_index",
    "resolve_country_iso",
    "resolve_country_name",
]
