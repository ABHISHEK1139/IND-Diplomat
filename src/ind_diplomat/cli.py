from __future__ import annotations

from importlib import import_module

from ._legacy import ensure_legacy_root_on_syspath

ensure_legacy_root_on_syspath()

_legacy = import_module("run")

DiplomatResult = _legacy.DiplomatResult
diplomat_query = _legacy.diplomat_query
diplomat_query_sync = _legacy.diplomat_query_sync
main = _legacy.main


if __name__ == "__main__":
    raise SystemExit(main())
