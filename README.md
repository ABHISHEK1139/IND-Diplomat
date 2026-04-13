# IND-Diplomat

IND-Diplomat is a layered geopolitical intelligence system that combines structured data ingestion, Bayesian state modeling, deliberative analysis, deterministic assessment gating, and evidence-backed reporting.

All layer packages are grouped under `engine/` for a clean and modern project layout.

## What This Repository Contains

- End-to-end pipeline implementation (Layer 1 to Layer 7)
- Unified web server and API surfaces
- Analyst async assessment API
- Backtesting and learning components
- Frontend dashboard assets
- Setup/run documentation and examples

## Architecture At A Glance

- `engine/Layer1_Collection` and `engine/Layer1_Sensors`: collection and sensor adapters
- `engine/Layer2_Knowledge`: retrieval, indexing, extraction, normalization
- `engine/Layer3_StateModel`: state construction and Bayesian modeling
- `engine/Layer4_Analysis`: council reasoning, verification, safety
- `engine/Layer5_Judgment` and `engine/Layer5_Reporting`: deterministic gate + reporting
- `engine/Layer5_Trajectory`, `engine/Layer6_*`: trajectory, presentation, backtesting, learning
- `engine/Layer7_GlobalModel`: cross-theater contagion and global view

## Quick Start (Recommended)

1. Clone repository and enter project root.
2. Run first-time bootstrap:

```powershell
powershell -ExecutionPolicy Bypass -File .\Scripts\configure_first_run.ps1 -InstallDependencies
```

3. Activate the environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

4. Start the unified server:

```powershell
python app_server.py --port 8000
```

5. Open:

- App: `http://127.0.0.1:8000`
- Health: `http://127.0.0.1:8000/health`
- API docs: `http://127.0.0.1:8000/docs`

## Run Modes

- Unified web + API server: `python app_server.py --port 8000`
- API v4 service only: `python API/main.py`
- Analyst async API only: `python analyst_api/main.py`
- CLI mode: `python run.py --help`

## Dependencies

- Main dependency entrypoint: `requirements.txt`
- Full stack dependency list: `Config/requirements.txt`
- Includes runtime plus optional production/dev tooling (Neo4j, Redis, quality tools, tests)

Install manually (if not using bootstrap):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Configuration

- Copy `.env.example` to `.env`
- Default setup is local Ollama (`LLM_PROVIDER=ollama`)
- Set your own auth secrets before production use (`API_KEY`, `IND_DIPLOMAT_API_KEY`, `JWT_SECRET_KEY`)

## Validate Installation

```powershell
python project_root.py
python -m pytest test/test_imports.py -q
```

## Documentation

- `QUICK_START.md` for the fastest path
- `CONFIGURE_AND_RUN.md` for detailed runbook
- `docs/architecture.md` for pipeline architecture
- `docs/repo-map.md` for module map
- `docs/ROOT_STRUCTURE.md` for folder-level orientation

## Notes

- This is a research-oriented system with production-hardening improvements.
- Data paths are environment driven (`GLOBAL_RISK_DIR`, `LEGAL_MEMORY_DIR`).
- Generated runtime artifacts are intentionally excluded from git.
