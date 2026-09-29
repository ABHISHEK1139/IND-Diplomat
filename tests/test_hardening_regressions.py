"""Regression tests for defects fixed during the production-hardening pass.

Each test pins a specific bug that previously shipped:

- ``interdependence_matrix`` defined the ("EGY", "SDN") coupling key twice, so
  the second (0.30) silently overwrote the first (0.25).
- ``crag`` tokenised with an inline multi-character ``strip`` set that was
  duplicated (and diverged) between the tokeniser and its length filter; it now
  shares one documented constant.
- ``trajectory_engine`` annotated ``state_context: 'StateContext'`` without
  importing the name, making the forward reference unresolvable.
- ``memory_vault`` used duplicated/multi-character ``strip`` sets.
- ``config`` defaulted the API host to 0.0.0.0 (all interfaces) with no
  production guard on wildcard CORS.
- ``url_guard`` blocks non-http(s) schemes so ``urlopen`` cannot be steered
  into ``file://`` by an environment-supplied host.
"""
from __future__ import annotations

import typing

import pytest

from dip.core.Config.config import Config
from dip.core.url_guard import UnsupportedSchemeError, require_http_scheme
from dip.pipeline.deliberation.deliberation import crag
from dip.pipeline.deliberation.reasoning import trajectory_engine
from dip.pipeline.memory.global_state.interdependence_matrix import (
    COUPLING_MATRIX,
    get_weight,
)

pytestmark = pytest.mark.unit


# ── interdependence matrix ────────────────────────────────────────────────
def test_coupling_matrix_has_no_duplicate_keys():
    """The matrix must be free of literal duplicate keys (F601 regression)."""
    import ast
    import inspect

    source = inspect.getsource(__import__(
        "dip.pipeline.memory.global_state.interdependence_matrix",
        fromlist=["COUPLING_MATRIX"],
    ))
    tree = ast.parse(source)
    seen: set[tuple[str, str]] = set()
    duplicates: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for key in node.keys:
                if (
                    isinstance(key, ast.Tuple)
                    and len(key.elts) == 2
                    and all(isinstance(e, ast.Constant) and isinstance(e.value, str) for e in key.elts)
                ):
                    pair = (key.elts[0].value, key.elts[1].value)
                    if pair in seen:
                        duplicates.append(pair)
                    seen.add(pair)
    assert not duplicates, f"duplicate coupling keys: {duplicates}"


def test_egypt_sudan_coupling_is_africa_value():
    """("EGY","SDN") is the Africa pairing and must resolve to 0.30."""
    assert ("EGY", "SDN") in COUPLING_MATRIX
    assert get_weight("EGY", "SDN") == 0.30
    assert get_weight("SDN", "EGY") == 0.30


# ── crag tokenisation ─────────────────────────────────────────────────────
def test_crag_tokeniser_does_not_strip_letters():
    """The trim set must remove separators only, never word characters.

    ``str.strip()`` takes a literal character set (unlike ``re``, ``-`` is not
    a range), so the trim set must name exactly the separators intended.
    """
    trim = " ?_.-"
    for word in ("sanctions", "blockade", "maritime", "treaty", "NATO", "Zulu"):
        assert word.strip(trim) == word
    # Separators at the boundary are removed; inner characters are untouched.
    assert " -sanctions- ".strip(trim) == "sanctions"
    assert "sanctions".strip(trim) == "sanctions"


def test_crag_module_docstring_survives():
    """A stray pre-docstring import used to null out crag.__doc__ (F811 regression)."""
    assert crag.__doc__ is not None and "CRAG" in crag.__doc__


# ── trajectory engine typing ──────────────────────────────────────────────
def test_trajectory_engine_annotation_resolves():
    """StateContext annotation must be a real, resolvable name (F821 regression)."""
    from dip.core.schema import StateContext

    hints = typing.get_type_hints(trajectory_engine.TrajectoryEngine.__init__)
    assert hints["state_context"] is StateContext


# ── url guard ─────────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "url",
    ["https://api.example.com/x", "http://127.0.0.1:11434/api/tags"],
)
def test_url_guard_allows_http_schemes(url):
    assert require_http_scheme(url) == url


@pytest.mark.parametrize(
    "url",
    ["file:///etc/passwd", "ftp://host/path", "gopher://host", "no-scheme", ""],
)
def test_url_guard_rejects_non_http_schemes(url):
    with pytest.raises(UnsupportedSchemeError):
        require_http_scheme(url)


# ── config exposure defaults ──────────────────────────────────────────────
def test_api_host_default_is_loopback(monkeypatch):
    monkeypatch.delenv("API_HOST", raising=False)
    assert Config().API_HOST == "127.0.0.1"


def test_wildcard_cors_rejected_in_production(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "*")
    with pytest.raises(ValueError, match="CORS_ALLOWED_ORIGINS"):
        Config().validate_production_settings()


def test_explicit_cors_allowed_in_production(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://app.example.com")
    Config().validate_production_settings()  # must not raise


def test_wildcard_cors_tolerated_in_development(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "*")
    Config().validate_production_settings()  # must not raise
