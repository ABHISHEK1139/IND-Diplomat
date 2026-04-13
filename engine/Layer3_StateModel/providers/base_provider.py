"""
Abstract Base Class for Layer 3 Data Providers.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List
from Config.runtime_clock import RuntimeClock


class BaseProvider(ABC):
    """
    Interface for a data provider that loads raw signals for a specific domain.
    """

    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self._cache: Dict[str, Any] = {}
        self._index: Dict[str, Any] = {}
        self._loaded = False
        self._status: Dict[str, Any] = {}
        self._reset_status()

    @abstractmethod
    def load_index(self):
        """
        Load the raw data index into memory.
        Should be uniform/idempotent (safe to call multiple times).
        """
        pass

    @abstractmethod
    def get_signal(self, country_code: str, date: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve the signal for a specific country and date.
        Returns None if no data exists.
        """
        pass
    
    def _normalize_country_key(self, country: str) -> str:
        """Helper to normalize country codes."""
        return country.strip().upper()

    def _target_year(self, date_str: str) -> int:
        """Extract year from YYYY-MM-DD date string."""
        try:
            return int(date_str.split("-")[0])
        except (ValueError, IndexError):
            return int(RuntimeClock.today().year)

    # Minimal COW numeric mapping for countries currently tracked by the registry.
    COW_TO_ISO = {
        2: "USA",
        20: "CAN",
        140: "BRA",
        200: "GBR",
        220: "FRA",
        255: "DEU",
        290: "POL",
        365: "RUS",
        369: "UKR",
        560: "ZAF",
        630: "IRN",
        640: "TUR",
        666: "ISR",
        670: "SAU",
        700: "AFG",
        710: "CHN",
        713: "TWN",
        731: "PRK",
        732: "KOR",
        740: "JPN",
        750: "IND",
        770: "PAK",
        771: "BGD",
        780: "LKA",
        790: "NPL",
        900: "AUS",
    }

    def _clamp(self, val: Any) -> float:
        """Clamp value between 0.0 and 1.0."""
        try:
            return max(0.0, min(1.0, float(val)))
        except (ValueError, TypeError):
            return 0.0

    def _reset_status(self) -> None:
        self._status = {
            "loaded": False,
            "dataset_path": "",
            "rows_read": 0,
            "rows_kept": 0,
            "coverage_count": 0,
            "warnings": [],
            "error": None,
        }

    def _warn(self, message: str) -> None:
        warning = str(message or "").strip()
        if not warning:
            return
        warnings = self._status.setdefault("warnings", [])
        if warning not in warnings:
            warnings.append(warning)

    def _set_error(self, message: Any) -> None:
        self._status["error"] = str(message) if message is not None else None
        if message:
            self._loaded = False

    def _set_dataset_path(self, path: Any) -> None:
        if path is None:
            return
        self._status["dataset_path"] = str(path)

    def _set_status_counts(
        self,
        *,
        rows_read: Optional[int] = None,
        rows_kept: Optional[int] = None,
        coverage_count: Optional[int] = None,
    ) -> None:
        if rows_read is not None:
            self._status["rows_read"] = max(0, int(rows_read))
        if rows_kept is not None:
            self._status["rows_kept"] = max(0, int(rows_kept))
        if coverage_count is not None:
            self._status["coverage_count"] = max(0, int(coverage_count))

    def _infer_coverage_count(self) -> int:
        index = getattr(self, "_index", None)
        if isinstance(index, dict):
            return len(index)
        if isinstance(index, list):
            return len(index)
        return 0

    def _finalize_status(self, *, loaded: bool) -> None:
        self._loaded = bool(loaded)
        self._status["loaded"] = bool(loaded)
        if not self._status.get("coverage_count", 0):
            self._status["coverage_count"] = self._infer_coverage_count()

    def get_status(self) -> Dict[str, Any]:
        status = dict(self._status)
        status["loaded"] = bool(self._loaded)
        if not status.get("coverage_count", 0):
            status["coverage_count"] = self._infer_coverage_count()
        status["dataset_path"] = str(status.get("dataset_path", "") or "")
        status["rows_read"] = int(status.get("rows_read", 0) or 0)
        status["rows_kept"] = int(status.get("rows_kept", 0) or 0)
        status["warnings"] = list(status.get("warnings", []) or [])
        return status

