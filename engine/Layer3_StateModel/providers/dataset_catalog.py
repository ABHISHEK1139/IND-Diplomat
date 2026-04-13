"""
Global-risk dataset catalog and path resolver.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional


@dataclass(frozen=True)
class DatasetSpec:
    key: str
    patterns: List[str]
    parser_mode: str
    required_columns: List[str] = field(default_factory=list)
    signatures: List[str] = field(default_factory=list)


DATASET_CATALOG: Dict[str, DatasetSpec] = {
    "sipri_import": DatasetSpec(
        key="sipri_import",
        patterns=[
            "SIPRI/*impoted*country*.csv",
            "SIPRI/*import*country*.csv",
            "SIPRI/*Recipient*.csv",
        ],
        parser_mode="csv",
        required_columns=["Recipient"],
    ),
    "sipri_export": DatasetSpec(
        key="sipri_export",
        patterns=[
            "SIPRI/*eported*county*.csv",
            "SIPRI/*export*country*.csv",
            "SIPRI/*Supplier*.csv",
        ],
        parser_mode="csv",
        required_columns=["Exports by"],
    ),
    "sanctions_gsdb": DatasetSpec(
        key="sanctions_gsdb",
        patterns=[
            "global Sanction db_v4/GSDB*.csv",
            "global Sanction db_v4/*.csv",
        ],
        parser_mode="csv",
        required_columns=["sanctioned_state", "sanctioning_state", "begin", "end"],
    ),
    "ofac_sdn": DatasetSpec(
        key="ofac_sdn",
        patterns=[
            "OFAC_Sanctions.csv",
            "sdn.csv",
            "OFAC*.csv",
        ],
        parser_mode="csv",
        signatures=["CUBA", "DPRK", "RUSSIA"],
    ),
    "lowy_diplomacy_index": DatasetSpec(
        key="lowy_diplomacy_index",
        patterns=["Lowy Institute Global Diplomacy Index*.xlsx"],
        parser_mode="xlsx",
    ),
    "leaders_archigos": DatasetSpec(
        key="leaders_archigos",
        patterns=["Archigos_Leaders.csv", "Archigos*.csv"],
        parser_mode="csv",
    ),
    "ucdp_ged": DatasetSpec(
        key="ucdp_ged",
        patterns=["ged251-csv/GEDEvent*.csv", "ged251-csv/*.csv"],
        parser_mode="csv",
        required_columns=["year", "country", "country_id"],
    ),
    "atop": DatasetSpec(
        key="atop",
        patterns=["ATOP 5.1 (.csv)/atop*.csv", "ATOP 5.1 (.csv)/*.csv"],
        parser_mode="csv",
        required_columns=["stateA", "stateB", "year"],
    ),
    "world_bank": DatasetSpec(
        key="world_bank",
        patterns=["WorldBank_Economy_Data.csv"],
        parser_mode="csv",
    ),
    "vdem": DatasetSpec(
        key="vdem",
        patterns=["V-Dem-CY-FullOthers-v15_csv/V-Dem-CY-Full+Others-v15.csv"],
        parser_mode="csv",
    ),
    "eez": DatasetSpec(
        key="eez",
        patterns=["World_EEZ_v12_20231025_LR/eez_v12_lowres.gpkg"],
        parser_mode="sqlite",
    ),
    "ports": DatasetSpec(
        key="ports",
        patterns=["UpdatedPub150.csv"],
        parser_mode="csv",
    ),
    "comtrade_snapshots": DatasetSpec(
        key="comtrade_snapshots",
        patterns=["comtrade_snapshots", "data/comtrade", "UN_Comtrade"],
        parser_mode="json_dir",
    ),
}


def _dedupe_paths(paths: Iterable[Path]) -> List[Path]:
    seen = set()
    ordered: List[Path] = []
    for path in paths:
        norm = str(path.resolve()) if path.exists() else str(path)
        if norm in seen:
            continue
        seen.add(norm)
        ordered.append(path)
    return ordered


def resolve_dataset_paths(key: str, data_root: str | Path) -> List[Path]:
    """
    Resolve catalog key to one or more local dataset paths.
    """
    spec = DATASET_CATALOG.get(key)
    if spec is None:
        return []

    root = Path(data_root)
    candidates: List[Path] = []
    for pattern in spec.patterns:
        matches = sorted(root.glob(pattern))
        if matches:
            candidates.extend(matches)
            continue
        # fallback to recursive search for brittle datasets
        basename = Path(pattern).name
        recursive = sorted(root.rglob(basename))
        candidates.extend(recursive)
    existing = [path for path in _dedupe_paths(candidates) if path.exists()]
    return existing


def resolve_dataset_path(key: str, data_root: str | Path) -> Optional[Path]:
    paths = resolve_dataset_paths(key, data_root)
    if not paths:
        return None
    spec = DATASET_CATALOG.get(key)
    if spec and spec.parser_mode == "csv" and spec.required_columns:
        required = {col.strip().lower() for col in spec.required_columns if col}
        for path in paths:
            if _csv_has_required_columns(path, required):
                return path
    return paths[0]


def _csv_has_required_columns(path: Path, required_columns: set[str]) -> bool:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore", newline="") as handle:
            reader = csv.reader(handle)
            for _ in range(20):
                row = next(reader, None)
                if row is None:
                    break
                header = {str(col or "").strip().lower() for col in row}
                if required_columns.issubset(header):
                    return True
    except Exception:
        return False
    return False


def catalog_entry(key: str) -> Optional[DatasetSpec]:
    return DATASET_CATALOG.get(key)


def list_catalog_keys() -> List[str]:
    return sorted(DATASET_CATALOG.keys())
