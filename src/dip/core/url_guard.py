"""URL scheme guard for outbound fetches.

`urllib.request.urlopen` honours every registered scheme, so an environment-
or config-supplied URL such as ``file:///etc/passwd`` or ``ftp://`` would turn a
plain "probe the local Ollama server" into a local-file read. Feed adapters
should route URL construction through :func:`require_http_scheme` so that only
``http``/``https`` ever reach the network stack.
"""

from __future__ import annotations

from urllib.parse import urlparse

ALLOWED_SCHEMES = ("http", "https")


class UnsupportedSchemeError(ValueError):
    """Raised when a URL uses a scheme that outbound fetchers must not follow."""


def require_http_scheme(url: str) -> str:
    """Return ``url`` unchanged, or raise if its scheme is not http/https.

    Args:
        url: The absolute URL about to be opened.

    Returns:
        The original URL, so the call can wrap the fetch inline.

    Raises:
        UnsupportedSchemeError: If the scheme is missing or not http/https.
    """
    scheme = (urlparse(url).scheme or "").lower()
    if scheme not in ALLOWED_SCHEMES:
        raise UnsupportedSchemeError(
            f"Refusing to open non-http(s) URL (scheme={scheme or 'none'!r}); "
            "only http and https are permitted for outbound fetches"
        )
    return url
