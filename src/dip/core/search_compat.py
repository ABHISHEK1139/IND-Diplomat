"""DuckDuckGo search backend compatibility shim.

The upstream ``duckduckgo_search`` distribution was renamed to ``ddgs`` and now
emits a ``RuntimeWarning`` on import. Both expose a compatible ``DDGS`` class
with a ``.text()`` method; only the exception type name differs
(``DDGSException`` vs the legacy ``DuckDuckGoSearchException``).

Import from this module instead of the distribution so the rename is handled in
exactly one place and the deprecation warning never reaches callers. ``ddgs`` is
preferred; ``duckduckgo_search`` remains a fallback for older environments.
"""

from __future__ import annotations

import warnings

DDGS: type | None
DDGSException: type[Exception]

try:  # Preferred: current distribution.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        from ddgs import DDGS  # type: ignore[attr-defined]
        from ddgs.exceptions import DDGSException  # type: ignore[attr-defined]
except ImportError:
    try:  # Fallback: legacy distribution.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            from duckduckgo_search import DDGS  # type: ignore[no-redef,attr-defined]
        from duckduckgo_search.exceptions import (  # type: ignore[import-not-found,no-redef]
            DuckDuckGoSearchException as DDGSException,
        )
    except ImportError:  # Neither installed.
        DDGS = None  # type: ignore[assignment]

        class DDGSException(Exception):  # type: ignore[no-redef]
            """Placeholder when no DuckDuckGo backend is installed."""


SEARCH_AVAILABLE = DDGS is not None

__all__ = ["DDGS", "DDGSException", "SEARCH_AVAILABLE"]
