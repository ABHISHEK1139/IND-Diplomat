"""
Layer5_Trajectory — GKG Ingestion (Live Pull)
==============================================

Fetches the latest GDELT GKG (Global Knowledge Graph) 15-minute file,
filters for target actors/themes, and produces an aggregate narrative
metrics object.  No raw articles stored — only aggregate counts.

Phase 5 ONLY.  Never touches SRE core.

Pipeline:
    1. Fetch lastupdate.txt → find GKG CSV URL
    2. Stream + parse GKG CSV (tab-delimited)
    3. Filter by actor (FIPS country codes) and themes
    4. Compute aggregate metrics → return NarrativeMetrics
"""

from __future__ import annotations

import csv
import io
import logging
import re
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

logger = logging.getLogger("Layer5_Trajectory.gkg_ingest")

# ── GKG column indices (V2 format) ───────────────────────────────────
_COL_DATE       = 0
_COL_THEMES     = 7   # semicolon-separated theme list
_COL_LOCATIONS  = 9   # semicolon-separated location entries
_COL_PERSONS    = 10
_COL_ORGS       = 11
_COL_TONE       = 15  # comma-separated: tone, pos, neg, polarity, ...
_COL_GCAM       = 16  # General Content Analysis Measures
_COL_COUNTS     = 5   # semicolon-separated count entries
_COL_SOURCEURL  = 4

# ── Target actor FIPS codes (Persian Gulf cluster) ───────────────────
TARGET_ACTORS: Set[str] = {
    "IRN", "USA", "ISR", "SAU", "ARE", "QAT",
    "IRQ", "KWT", "BHR", "OMN", "YEM",
}

# ── Theme keywords for filtering ─────────────────────────────────────
THEME_KEYWORDS: Set[str] = {
    "NUCLEAR", "SANCTIONS", "MILITARY", "EXERCISE",
    "ALLIANCE", "CYBER", "STRAIT_OF_HORMUZ", "BLOCKADE",
    "ENRICHMENT", "MISSILE", "NAVY", "IAEA",
    "WMD", "DRONE", "EMBARGO", "WEAPONRY",
    "MOBILIZATION", "CONFLICT", "TERROR", "IRAN",
}

# ── GDELT endpoints ──────────────────────────────────────────────────
GDELT_LAST_UPDATE_URL = "http://data.gdeltproject.org/gdeltv2/lastupdate.txt"

# Minimum rows before NDI is considered valid
MIN_ROWS_FOR_NDI = 50


@dataclass
class NarrativeMetrics:
    """Aggregate narrative metrics from a GKG pull."""
    total_articles: int = 0
    theme_counts: Dict[str, int] = field(default_factory=dict)
    avg_tone: float = 0.0
    negative_tone_ratio: float = 0.0
    actor_cooccurrence: Dict[str, int] = field(default_factory=dict)
    event_codes: List[str] = field(default_factory=list)
    goldstein_scores: List[float] = field(default_factory=list)
    source_count: int = 0
    valid: bool = False

    def to_dict(self) -> dict:
        return {
            "total_articles": self.total_articles,
            "theme_counts": dict(self.theme_counts),
            "avg_tone": round(self.avg_tone, 3),
            "negative_tone_ratio": round(self.negative_tone_ratio, 3),
            "actor_cooccurrence": dict(self.actor_cooccurrence),
            "source_count": self.source_count,
            "valid": self.valid,
        }


def _extract_tone(tone_field: str) -> tuple:
    """Parse GKG tone field → (avg_tone, positive, negative)."""
    parts = tone_field.split(",")
    try:
        avg = float(parts[0]) if len(parts) > 0 else 0.0
        pos = float(parts[1]) if len(parts) > 1 else 0.0
        neg = float(parts[2]) if len(parts) > 2 else 0.0
        return avg, pos, neg
    except (ValueError, IndexError):
        return 0.0, 0.0, 0.0


def _matches_target_location(locations_field: str) -> bool:
    """Check if any location entry contains a target FIPS code."""
    if not locations_field:
        return False
    for entry in locations_field.split(";"):
        parts = entry.split("#")
        # Location entries have FIPS country code in various positions
        for part in parts:
            token = part.strip().upper()
            if token in TARGET_ACTORS:
                return True
    return False


def _extract_matching_themes(themes_field: str) -> List[str]:
    """Extract themes that match our target keywords."""
    if not themes_field:
        return []
    matched = []
    for theme in themes_field.split(";"):
        theme_upper = theme.strip().upper()
        for kw in THEME_KEYWORDS:
            if kw in theme_upper:
                matched.append(theme.strip())
                break
    return matched


def fetch_latest_gkg_url() -> Optional[str]:
    """Fetch the latest GKG file URL from GDELT's lastupdate endpoint."""
    try:
        import urllib.request
        req = urllib.request.Request(
            GDELT_LAST_UPDATE_URL,
            headers={"User-Agent": "DIP5-Phase5/1.0"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            lines = resp.read().decode("utf-8", errors="replace").strip().split("\n")
        # lastupdate.txt has 3 lines: events, mentions, gkg
        # GKG line contains .gkg.csv.zip
        for line in lines:
            if ".gkg.csv" in line.lower():
                parts = line.strip().split()
                if len(parts) >= 3:
                    return parts[2]  # URL is the third field
        logger.warning("[GKG] No GKG URL found in lastupdate.txt")
        return None
    except Exception as exc:
        logger.warning("[GKG] Failed to fetch lastupdate.txt: %s", exc)
        return None


def fetch_and_parse_gkg(url: Optional[str] = None) -> NarrativeMetrics:
    """
    Fetch latest GKG file, filter for target actors/themes, return metrics.

    If URL is None, fetches the latest from GDELT.
    Returns NarrativeMetrics with valid=False if fetch fails or
    too few rows match.
    """
    metrics = NarrativeMetrics()

    if url is None:
        url = fetch_latest_gkg_url()
    if url is None:
        logger.info("[GKG] No URL available — returning empty metrics")
        return metrics

    logger.info("[GKG] Fetching: %s", url)

    try:
        import urllib.request
        req = urllib.request.Request(url, headers={"User-Agent": "DIP5-Phase5/1.0"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw_data = resp.read()
    except Exception as exc:
        logger.warning("[GKG] Download failed: %s", exc)
        return metrics

    # Decompress if zipped
    csv_text = ""
    try:
        if url.endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(raw_data)) as zf:
                for name in zf.namelist():
                    if name.endswith(".csv"):
                        csv_text = zf.read(name).decode("utf-8", errors="replace")
                        break
        else:
            csv_text = raw_data.decode("utf-8", errors="replace")
    except Exception as exc:
        logger.warning("[GKG] Decompression failed: %s", exc)
        return metrics

    if not csv_text.strip():
        logger.info("[GKG] Empty GKG file")
        return metrics

    # Parse tab-delimited GKG
    theme_counter: Counter = Counter()
    actor_counter: Counter = Counter()
    tones: List[float] = []
    neg_count = 0
    total_rows = 0

    for line in csv_text.strip().split("\n"):
        cols = line.split("\t")
        if len(cols) < 17:
            continue

        # Filter: must have target location OR target actor in themes
        locations = cols[_COL_LOCATIONS] if len(cols) > _COL_LOCATIONS else ""
        themes = cols[_COL_THEMES] if len(cols) > _COL_THEMES else ""

        has_location = _matches_target_location(locations)
        matched_themes = _extract_matching_themes(themes)

        if not has_location and not matched_themes:
            continue

        total_rows += 1

        # Aggregate themes
        for t in matched_themes:
            theme_counter[t] += 1

        # Aggregate tone
        tone_field = cols[_COL_TONE] if len(cols) > _COL_TONE else ""
        avg_tone, _, neg = _extract_tone(tone_field)
        tones.append(avg_tone)
        if avg_tone < -1.0:
            neg_count += 1

        # Actor co-occurrence
        if has_location:
            for entry in locations.split(";"):
                parts = entry.split("#")
                for part in parts:
                    token = part.strip().upper()
                    if token in TARGET_ACTORS:
                        actor_counter[token] += 1

    # Build metrics
    metrics.total_articles = total_rows
    metrics.theme_counts = dict(theme_counter.most_common(30))
    metrics.avg_tone = sum(tones) / len(tones) if tones else 0.0
    metrics.negative_tone_ratio = neg_count / len(tones) if tones else 0.0
    metrics.actor_cooccurrence = dict(actor_counter.most_common(20))
    metrics.source_count = total_rows
    metrics.valid = total_rows >= MIN_ROWS_FOR_NDI

    logger.info(
        "[GKG] Parsed %d matching rows (valid=%s, avg_tone=%.2f, neg_ratio=%.2f, themes=%d)",
        total_rows, metrics.valid, metrics.avg_tone,
        metrics.negative_tone_ratio, len(metrics.theme_counts),
    )

    return metrics
