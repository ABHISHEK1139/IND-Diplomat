# IND-Diplomat Analyst Workstation

White-box intelligence interface that wraps the frozen engine (Layers 1–5) in an async job system with full evidence provenance, SRE decomposition, and reasoning chain visibility.

**Stability Lock**: This module does NOT modify any Layer 1–5 code. The engine is a black-box computation service.

## Quick Start

```bash
# From project root (DIP_3_0/)
python -m analyst_api.launch
```

Opens two servers:
| Service | Port | URL |
|---------|------|-----|
| Dashboard | 3000 | http://localhost:3000 |
| Analyst API | 8100 | http://localhost:8100/docs |

The dashboard proxies all `/api/v3/*` requests to the Analyst API automatically.

## Architecture

```
┌──────────────────────────────────────────────────┐
│  Browser (localhost:3000)                         │
│  ┌───────────────────────────────────────────┐   │
│  │  index.html + styles.css + app.js         │   │
│  │  + analyst.js  (new workstation logic)    │   │
│  │  + Chart.js CDN (trend visualization)     │   │
│  └───────────────────┬───────────────────────┘   │
│                      │ /api/v3/*                  │
├──────────────────────┼───────────────────────────┤
│  Frontend/server.py  │  (proxy)                   │
│                      ▼                            │
│  analyst_api/main.py (FastAPI, port 8100)        │
│  ┌─────────────────────────────────────────┐     │
│  │  /assess  → async job + engine bridge   │     │
│  │  /jobs/*  → status, result, evidence    │     │
│  │  /trends  → monitor_log.jsonl reader    │     │
│  │  /health  → system guardian checks      │     │
│  └──────────┬──────────────────────────────┘     │
│             │                                     │
│  ┌──────────▼──────────────────────────────┐     │
│  │  engine_bridge.py                        │     │
│  │  Calls diplomat_query() as black box     │     │
│  │  Extracts: SRE, gate, evidence, chain   │     │
│  └──────────┬──────────────────────────────┘     │
│             │                                     │
│  ┌──────────▼──────────────────────────────┐     │
│  │  Frozen Engine (Layers 1–5)             │     │
│  │  DO NOT MODIFY                          │     │
│  └─────────────────────────────────────────┘     │
└──────────────────────────────────────────────────┘
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v3/assess` | Start async assessment (returns job_id immediately) |
| GET | `/api/v3/jobs/{id}` | Poll job status + phase progress |
| GET | `/api/v3/jobs/{id}/result` | Full structured result (SRE, gate, evidence, report) |
| GET | `/api/v3/jobs/{id}/evidence` | Evidence provenance chain |
| GET | `/api/v3/jobs/{id}/verify` | White-box reasoning chain (7 steps) |
| GET | `/api/v3/jobs` | List past jobs (newest first) |
| GET | `/api/v3/trends/{cc}` | Temporal trend data (from monitor_log.jsonl) |
| GET | `/api/v3/alerts/{cc}` | Latest alert for country |
| GET | `/api/v3/health` | System health + guardian checks |

## Parameters

When submitting via POST `/api/v3/assess`:

```json
{
  "query": "Assess Iran-Israel escalation risk...",
  "country_code": "IRN",
  "time_horizon": "30d",         // 7d | 30d | 90d
  "evidence_strictness": "balanced", // cautious | balanced | aggressive
  "source_mode": "hybrid",       // dataset | osint | hybrid
  "gate_threshold": "default",   // default | strict | experimental
  "collection_depth": "standard", // fast (1 loop) | standard (2) | deep (3)
  "use_red_team": true,
  "use_mcts": false
}
```

## Dashboard Features

1. **Parameter Control Panel** — Country, time horizon, evidence strictness, source mode, gate threshold, collection depth
2. **Async Progress Tracker** — 5-phase stepper (Scope → Sensors → Council → Gate → Report) with elapsed timer
3. **SRE Decomposition** — Domain bars (capability/intent/stability/cost) + escalation gauge
4. **Gate Verdict** — Approved/Withheld card with reasons, intelligence gaps, collection tasks
5. **Evidence Provenance** — Filterable table: signal → source → dimension → confidence
6. **Trend Charts** — Chart.js temporal lines: escalation + 4 domain scores over time
7. **Intelligence Report** — Formatted briefing from report_formatter.py
8. **Verification Chain** — 7-step reasoning: Sensors → Beliefs → Ministers → SRE → Temporal → Gate → Verdict
9. **Past Assessments** — Collapsible sidebar, click to reload any previous result

## Data Persistence

- Jobs stored in SQLite: `runtime/analyst_jobs.db`
- Trends read from: `runtime/monitor_log.jsonl`
- Alerts read from: `runtime/alerts/*.json`

## Files Created

```
analyst_api/
  __init__.py       — package init
  models.py         — Pydantic v2 models (request, result, evidence, SRE, gate)
  job_store.py      — SQLite job persistence
  engine_bridge.py  — wraps diplomat_query(), extracts structured data
  trend_store.py    — reads monitor_log.jsonl for trend charts
  main.py           — FastAPI app (port 8100)
  launch.py         — combined launcher (API + Frontend)
  README.md         — this file

Frontend/ (EXTENDED, not replaced)
  index.html        — added: parameter panel, progress tracker, past jobs bar, 5 new tabs
  styles.css        — added: 300+ lines for new components
  analyst.js        — NEW: async job system, SRE/gate/evidence/trends/report rendering
  server.py         — added: /api/v3/* proxy route to port 8100
```
