"""
Lowy Institute Global Diplomacy Index Provider.
"""

import xml.etree.ElementTree as ET
from zipfile import ZipFile
from typing import Any, Dict, List, Optional

from engine.Layer3_StateModel.providers.base_provider import BaseProvider
from engine.Layer3_StateModel.providers.country_resolver import resolve_country_to_iso3
from engine.Layer3_StateModel.providers.dataset_catalog import resolve_dataset_path

class LowyProvider(BaseProvider):
    def __init__(self, data_dir: str):
        super().__init__(data_dir)
        self._index: Dict[str, Dict[str, Any]] = {}

    def load_index(self):
        if self._loaded:
            return

        self._reset_status()
        path = resolve_dataset_path("lowy_diplomacy_index", self.data_dir)
        if path is None:
            self._set_error("Lowy diplomacy workbook not found")
            self._warn("lowy_missing")
            self._finalize_status(loaded=False)
            return
        self._set_dataset_path(path)

        rows_read = 0
        rows_kept = 0
        ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        rel_ns = {"r": "http://schemas.openxmlformats.org/package/2006/relationships"}
        tmp: Dict[str, Dict[str, Any]] = {}
        
        try:
            with ZipFile(path) as workbook:
                shared_strings: List[str] = []
                if "xl/sharedStrings.xml" in workbook.namelist():
                    root = ET.fromstring(workbook.read("xl/sharedStrings.xml"))
                    for si in root.findall("x:si", ns):
                        text = "".join((t.text or "") for t in si.findall(".//x:t", ns))
                        shared_strings.append(text)

                workbook_root = ET.fromstring(workbook.read("xl/workbook.xml"))
                rels_root = ET.fromstring(workbook.read("xl/_rels/workbook.xml.rels"))
                rel_map = {
                    rel.attrib.get("Id", ""): rel.attrib.get("Target", "")
                    for rel in rels_root.findall("r:Relationship", rel_ns)
                }

                sheets = workbook_root.findall("x:sheets/x:sheet", ns)
                if not sheets: return

                selected_sheet = sheets[0]
                selected_year = -1
                for sheet in sheets:
                    name = sheet.attrib.get("name", "")
                    try:
                        year = int(float(name))
                    except ValueError:
                        year = None
                    if year is not None and year > selected_year:
                        selected_year = year
                        selected_sheet = sheet

                rel_id = selected_sheet.attrib.get(
                    "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id", ""
                )
                target = rel_map.get(rel_id, "")
                if not target:
                    self._warn("lowy_sheet_target_missing")
                    self._finalize_status(loaded=False)
                    return
                
                sheet_path = f"xl/{target.lstrip('/')}"
                sheet_root = ET.fromstring(workbook.read(sheet_path))

                for row in sheet_root.findall(".//x:sheetData/x:row", ns):
                    rows_read += 1
                    try:
                        row_idx = int(row.attrib.get("r", "0"))
                    except: row_idx = 0
                    if row_idx <= 1: continue

                    cells = {}
                    for cell in row.findall("x:c", ns):
                        ref = cell.attrib.get("r", "")
                        column = "".join(ch for ch in ref if ch.isalpha())
                        if not column: continue
                        value_node = cell.find("x:v", ns)
                        text = value_node.text if value_node is not None else ""
                        if cell.attrib.get("t") == "s" and text and text.isdigit():
                            idx = int(text)
                            text = shared_strings[idx] if idx < len(shared_strings) else ""
                        cells[column] = text

                    country_name = (cells.get("A") or "").strip()
                    if not country_name: continue
                    iso = resolve_country_to_iso3(country_name)
                    if not iso: continue

                    bucket = tmp.setdefault(
                        iso,
                        {"post_count": 0, "hosts": set(), "embassy_count": 0, "rank": None},
                    )
                    bucket["post_count"] += 1
                    host_country = (cells.get("I") or "").strip()
                    if host_country: bucket["hosts"].add(host_country.lower())
                    
                    post_type = f"{cells.get('J', '')} {cells.get('K', '')}".lower()
                    if "embassy" in post_type: bucket["embassy_count"] += 1
                    rows_kept += 1
                    
                    try:
                        rank = int(float(cells.get("G", "0")))
                        if bucket.get("rank") is None or rank < bucket["rank"]:
                            bucket["rank"] = rank
                    except: pass

            for iso, bucket in tmp.items():
                post_count = max(int(bucket["post_count"]), 1)
                host_count = len(bucket["hosts"])
                reach_index = self._clamp(host_count / 180.0)
                rank = bucket["rank"]
                rank_score = self._clamp(1.0 - ((float(rank or 120) - 1.0) / 120.0))
                embassy_share = self._clamp(float(bucket["embassy_count"]) / float(post_count))
                representation_index = self._clamp((reach_index * 0.6) + (embassy_share * 0.2) + (rank_score * 0.2))
                
                self._index[iso] = {
                    "post_count": post_count,
                    "host_country_count": host_count,
                    "reach_index": reach_index,
                    "rank_score": rank_score,
                    "representation_index": representation_index,
                }
            self._set_status_counts(
                rows_read=rows_read,
                rows_kept=rows_kept,
                coverage_count=len(self._index),
            )
            self._finalize_status(loaded=len(self._index) > 0)
            if selected_year > 0:
                self._status["selected_year"] = int(selected_year)
        except Exception as exc:
            self._index = {}
            self._set_error(exc)
            self._set_status_counts(rows_read=rows_read, rows_kept=rows_kept, coverage_count=0)
            self._finalize_status(loaded=False)

    def get_signal(self, country_code: str, date: str) -> Optional[Dict[str, Any]]:
        self.load_index()
        iso3 = resolve_country_to_iso3(country_code) or country_code.upper()
        record = self._index.get(iso3)
        if not record:
            return None
        return {
            "post_count": int(record.get("post_count", 0)),
            "host_country_count": int(record.get("host_country_count", 0)),
            "reach_index": round(float(record.get("reach_index", 0.0)), 4),
            "rank_score": round(float(record.get("rank_score", 0.0)), 4),
            "representation_index": round(float(record.get("representation_index", 0.0)), 4),
            "date": "2023-12-31",
        }
