docker run -d -p 7687:7687 neo4j  # Graph database
# IND-Diplomat Quick Start

Use this guide if you want the fastest path from clone to a running system.

## 1) Clone and Enter Project

```powershell
git clone https://github.com/ABHISHEK1139/IND-Diplomat.git
cd IND-Diplomat
```

## 2) Run First-Time Bootstrap

```powershell
powershell -ExecutionPolicy Bypass -File .\Scripts\configure_first_run.ps1 -InstallDependencies
```

This script:

- Creates `.env` from `.env.example` if missing
- Resolves dataset paths (`GLOBAL_RISK_DIR`, `LEGAL_MEMORY_DIR`)
- Creates `.venv` (if missing)
- Installs dependencies

## 3) Start LLM Service (Ollama)

In terminal A:

```powershell
ollama serve
```

In terminal B (first run only):

```powershell
ollama pull deepseek-r1:8b
```

## 4) Start IND-Diplomat

```powershell
.\.venv\Scripts\Activate.ps1
python app_server.py --port 8000
```

## 5) Verify

- Web app: `http://127.0.0.1:8000`
- Health: `http://127.0.0.1:8000/health`
- API docs: `http://127.0.0.1:8000/docs`

Quick query test:

```powershell
curl -Method POST "http://127.0.0.1:8000/api/simple/query" `
	-Headers @{"Content-Type"="application/json"} `
	-Body '{"query":"Assess India-Pakistan escalation risk in 30 days","country_code":"IND"}'
```

## Alternate Services

- API-only mode: `python API/main.py`
- Analyst async API: `python analyst_api/main.py`

## If Something Fails

- Missing package: `pip install -r requirements.txt`
- Model not found: `ollama pull deepseek-r1:8b`
- Env not configured: re-run bootstrap script
- Data path issues: `python project_root.py`
