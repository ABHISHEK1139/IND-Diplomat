"""Data-path hygiene: no import-time side effects, no CWD dependence."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


def test_import_creates_no_files(tmp_path, monkeypatch):
    """Importing the tracer (default-path module) must not write anything
    to the working directory."""
    code = (
        "import dip.telemetry.llm_tracer as t;"
        "import dip.pipeline.knowledge.signal_extractor;"
        "import dip.unified_pipeline;"
        "print('imports-ok')"
    )
    src_dir = str(Path(__file__).resolve().parent.parent / "src")
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": src_dir, "FORCE_MINISTER_HEURISTIC": "1"},
        timeout=120,
    )
    assert "imports-ok" in proc.stdout, proc.stderr[-2000:]
    leftovers = [p.name for p in tmp_path.iterdir()]
    assert leftovers == [], f"import created files in CWD: {leftovers}"


def test_relative_paths_resolve_under_data_dir():
    import os as _os

    from dip.core.Config.config import DATA_DIR, ROOT_DIR, resolve_data_path

    # Legacy repo-root-relative form keeps its historical meaning.
    assert Path(resolve_data_path("data/jobs.json")) == (ROOT_DIR / "jobs.json").resolve()
    assert Path(resolve_data_path("", "jobs.json")) == DATA_DIR / "jobs.json"
    assert Path(resolve_data_path("jobs.json")) == DATA_DIR / "jobs.json"
    abs_path = str(Path(_os.path.abspath(_os.sep)) / "x" / "y.json")
    assert resolve_data_path(abs_path) == abs_path
    assert resolve_data_path("file:/x/mlruns") == "file:/x/mlruns"


def test_store_default_lives_under_data_dir(tmp_path, monkeypatch):
    from dip.core.Config.config import DATA_DIR
    from dip.core.investigation_store import InvestigationStore

    monkeypatch.chdir(tmp_path)
    store = InvestigationStore()
    assert store.root.parent == DATA_DIR
    assert not (tmp_path / "investigations").exists()


def test_history_files_live_under_data_dir():
    from dip.core.Config.config import DATA_DIR
    from dip.pipeline.deliberation.reasoning import introspection
    from dip.pipeline.world_model.state import temporal_memory

    assert "src" not in str(introspection.HISTORY_FILE)
    assert "src" not in str(temporal_memory._HISTORY_FILE)
    assert str(DATA_DIR) in str(introspection.HISTORY_FILE)
    assert str(DATA_DIR) in str(temporal_memory._HISTORY_FILE)


def test_legacy_files_copied_not_moved(tmp_path, monkeypatch):
    """Legacy CWD data is copied forward once; the originals are kept."""
    from dip.pipeline.memory.core.investigation_memory import InvestigationMemory

    data_dir = tmp_path / "data"
    monkeypatch.setenv("DIP_DATA_DIR", str(data_dir))
    import importlib

    import dip.core.Config.config as cfg

    importlib.reload(cfg)
    monkeypatch.chdir(tmp_path)
    try:
        import sqlite3

        legacy_db = tmp_path / "investigations.db"
        sqlite3.connect(str(legacy_db)).close()
        mem = InvestigationMemory(
            db_path=str(data_dir / "investigations.db"),
            store_root=str(data_dir / "investigations"),
        )
        assert Path(mem.store.root) == data_dir / "investigations"
        assert legacy_db.is_file(), "legacy original must be preserved"
    finally:
        importlib.reload(cfg)
