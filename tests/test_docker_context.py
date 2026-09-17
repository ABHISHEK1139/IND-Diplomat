"""Deploy static validation: Dockerfiles must match the real repo layout.

Catches DEP-02/DEP-03 class regressions (stale COPY paths, wrong ASGI
targets) without needing a Docker daemon. Real image builds remain the
gold standard and are attempted in CI with a daemon; this test is the
always-on guard.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parent.parent
DOCKER = ROOT / "docker"


def _dockerfiles():
    return sorted(DOCKER.glob("Dockerfile*"))


def _copy_sources(text: str) -> list[str]:
    sources = []
    for line in text.splitlines():
        m = re.match(r"\s*COPY\s+(--\S+\s+)*(\S+)\s+(\S+)", line)
        if m:
            sources.append(m.group(2))
    return sources


def test_dockerfiles_exist():
    assert DOCKER.is_dir()
    names = {p.name for p in _dockerfiles()}
    assert {"Dockerfile", "Dockerfile.web", "Dockerfile.worker", "Dockerfile.scheduler", "Dockerfile.guardian"} <= names


def test_copy_sources_exist_in_build_context():
    """Every COPY source must exist relative to the documented build context
    (repo root for all images; see header comments)."""
    missing = []
    for df in _dockerfiles():
        if df.name == "Dockerfile.war_room":
            continue  # static-export precondition documented in-file
        text = df.read_text(encoding="utf-8")
        assert "repo root" in text.lower() or "repository root" in text.lower(), f"{df.name} must document its build context"
        for src in _copy_sources(text):
            if src.startswith("--"):
                continue
            if (ROOT / src).exists():
                continue
            missing.append(f"{df.name}: COPY {src} (missing under repo root)")
    assert not missing, "stale COPY paths:\n" + "\n".join(missing)


def test_asgi_targets_are_importable():
    """CMD uvicorn targets must resolve to a real app object."""
    import importlib

    targets = set()
    for df in _dockerfiles():
        for m in re.finditer(r"uvicorn\"\s*,\s*\"([\w.]+):(\w+)\"", df.read_text(encoding="utf-8")):
            targets.add((m.group(1), m.group(2)))
    assert targets, "no uvicorn ASGI target found in Dockerfiles"
    for module, attr in targets:
        mod = importlib.import_module(module)
        assert getattr(mod, attr, None) is not None, f"{module}:{attr} missing"


def test_single_worker_for_json_stores():
    """JSON job stores support one API process; images must not scale
    uvicorn workers (see BUG_AUDIT CFG/JOB notes)."""
    offenders = []
    for df in ("Dockerfile", "Dockerfile.web"):
        text = (DOCKER / df).read_text(encoding="utf-8")
        m = re.search(r"--workers\s+(\d+)", text)
        if m and int(m.group(1)) != 1:
            offenders.append(f"{df}: --workers {m.group(1)}")
    assert not offenders, "multi-worker uvicorn with JSON stores:\n" + "\n".join(offenders)


def test_compose_paths_resolve():
    """docker/docker-compose.yml host-relative paths must exist or be
    documented mounts; build contexts + dockerfiles must exist."""
    compose = yaml.safe_load((DOCKER / "docker-compose.yml").read_text(encoding="utf-8"))
    problems = []
    for name, svc in compose.get("services", {}).items():
        build = svc.get("build")
        if isinstance(build, dict):
            ctx = (DOCKER / build["context"]).resolve()
            df = ctx / build["dockerfile"] if not Path(build["dockerfile"]).is_absolute() else Path(build["dockerfile"])
            # dockerfile is relative to context
            df = (ctx / build["dockerfile"]).resolve()
            if not ctx.is_dir():
                problems.append(f"{name}: context {build['context']} missing")
            if not df.is_file():
                problems.append(f"{name}: dockerfile {build['dockerfile']} missing")
    assert not problems, "compose build refs broken:\n" + "\n".join(problems)
