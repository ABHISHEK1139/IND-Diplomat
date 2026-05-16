from __future__ import annotations

from importlib import import_module

from ._legacy import ensure_legacy_root_on_syspath

ensure_legacy_root_on_syspath()

_legacy = import_module("app_server")

app = _legacy.app
main = _legacy.main


if __name__ == "__main__":
    raise SystemExit(main())
