# Configure And Run

This runbook is for new users, reviewers, and deployers who need a reliable setup path.

## 1) Prerequisites

- Python 3.11+ (3.12 recommended)
- Git
- Ollama (for local model runtime) or OpenRouter API key
- Windows PowerShell, bash, or zsh

## 2) Clone

```bash
git clone https://github.com/ABHISHEK1139/IND-Diplomat.git
cd IND-Diplomat
```

## 3) Bootstrap (Recommended)

```powershell
powershell -ExecutionPolicy Bypass -File .\Scripts\configure_first_run.ps1 -InstallDependencies
```

Bootstrap actions:

- Creates `.env` from `.env.example` if missing
- Detects and writes dataset paths into `.env`
- Creates `.venv` if needed
- Installs dependencies

## 4) Manual Setup (Alternative)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

## 5) Environment Configuration

At minimum, verify these in `.env`:

- `LLM_PROVIDER` (`ollama` or `openrouter`)
- `LLM_MODEL` and `LAYER4_MODEL`
- `GLOBAL_RISK_DIR`
- `LEGAL_MEMORY_DIR`
- `JWT_SECRET_KEY`
- `IND_DIPLOMAT_API_KEY` (or `API_KEY`)

For local Ollama:

```env
LLM_PROVIDER=ollama
LLM_MODEL=deepseek-r1:8b
LAYER4_MODEL=deepseek-r1:8b
OLLAMA_BASE_URL=http://localhost:11434
```

For OpenRouter:

```env
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=<your_key>
OPENROUTER_MODEL=qwen/qwen3.6-plus-preview:free
```

## 6) Start Model Runtime

### Ollama mode

Terminal A:

```powershell
ollama serve
```

Terminal B (first time):

```powershell
ollama pull deepseek-r1:8b
```

### OpenRouter mode

- Ensure `OPENROUTER_API_KEY` is set
- No local model process required

## 7) Start Services

### Unified server (recommended)

```powershell
python app_server.py --port 8000
```

### API-only

```powershell
python API/main.py
```

### Analyst async API

```powershell
python analyst_api/main.py
```

## 8) Verify Health

```powershell
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/docs
curl http://127.0.0.1:8100/api/v3/health
```

Simple request:

```powershell
curl -Method POST "http://127.0.0.1:8000/api/simple/query" `
  -Headers @{"Content-Type"="application/json"} `
  -Body '{"query":"Assess India-Pakistan escalation risk in 30 days","country_code":"IND"}'
```

## 9) Optional Test Check

```powershell
python -m pytest test/test_imports.py -q
```

## 10) Production Notes

- Set strong values for auth secrets (`JWT_SECRET_KEY`, API keys)
- Keep `.env` private
- Keep generated runtime artifacts out of git
- Use `AUTH_MODE=production` for stricter auth behavior
