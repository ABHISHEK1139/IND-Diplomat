"""Guardrail for sandbox-only fault-injection tests."""

from __future__ import annotations

import os


def test_mode_enabled() -> bool:
    token = str(os.environ.get("TEST_MODE", "")).strip().lower()
    return token in {"1", "true", "yes", "on"}


def ensure_test_mode() -> None:
    if not test_mode_enabled():
        raise RuntimeError(
            "You are attempting to run fault-injection tests without TEST_MODE=1."
        )


if __name__ == "__main__":
    ensure_test_mode()
    print("TEST_MODE is enabled.")

