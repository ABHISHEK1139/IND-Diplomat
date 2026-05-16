from __future__ import annotations

import sys

from ind_diplomat._legacy import bind_legacy_package

bind_legacy_package(sys.modules[__name__], "analyst_api")
