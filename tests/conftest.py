"""Shared fixtures. DIP_OFFLINE=1 runs the suite with zero network/LLM.

Cassettes replace collection sensors with deterministic fixtures and force
heuristic mode, so every pipeline stage still executes against realistic
content. Default runs (without the switch) are completely unaffected.
"""
from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def _offline_cassettes(monkeypatch):
    if os.getenv("DIP_OFFLINE") != "1":
        return
    monkeypatch.setenv("FORCE_MINISTER_HEURISTIC", "1")
    from tests.cassette import install_cassettes

    install_cassettes(monkeypatch)
