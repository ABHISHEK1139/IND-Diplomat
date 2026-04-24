/**
 * IND-Diplomat Interactive Dashboard — app.js
 * Connects to the backend API for real-time intelligence assessments.
 */

// ── Config ─────────────────────────────────────────────────────────────
const API_BASE = '';  // same origin
const API_V3   = '/api/v3';
const POLL_MS  = 2000;

// Phase ordering for pipeline tracker
const PHASES = ['SCOPE_CHECK', 'SENSORS', 'BELIEF', 'COUNCIL', 'GATE', 'REPORT'];

// ── State ──────────────────────────────────────────────────────────────
const state = {
    jobId: null,
    pollTimer: null,
    elapsedTimer: null,
    startTime: null,
};

// ── Helpers ────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);
const $$ = sel => document.querySelectorAll(sel);

function esc(str) {
    if (!str) return '';
    return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function clamp01(v) { return Math.max(0, Math.min(1, Number(v) || 0)); }
function pct(v) { return (clamp01(v) * 100).toFixed(1) + '%'; }

function fmtElapsed(sec) {
    if (sec < 60) return sec + 's';
    return Math.floor(sec/60) + 'm ' + (sec%60) + 's';
}

// ── Init ───────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    bindEvents();
    checkHealth();
    checkModel();
    loadPastJobs();
});

function bindEvents() {
    // Query form
    $('queryForm').addEventListener('submit', handleSubmit);

    // Tab switching
    $$('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            $$('.tab-btn').forEach(b => b.classList.remove('active'));
            $$('.tab-panel').forEach(p => p.classList.remove('active'));
            btn.classList.add('active');
            const panel = $(btn.dataset.tab + '-panel');
            if (panel) panel.classList.add('active');
        });
    });

    // Past jobs toggle
    $('pastHeader').addEventListener('click', () => {
        const list = $('pastList');
        const toggle = $('pastToggle');
        const visible = list.style.display !== 'none';
        list.style.display = visible ? 'none' : 'flex';
        toggle.classList.toggle('open', !visible);
    });

    // Textarea auto-resize
    $('queryInput').addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = Math.min(this.scrollHeight, 200) + 'px';
    });

    // Enter to submit (shift+enter for newline)
    $('queryInput').addEventListener('keydown', e => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            $('queryForm').requestSubmit();
        }
    });
}

// ── Health Checks ──────────────────────────────────────────────────────
async function checkHealth() {
    try {
        const r = await fetch('/health');
        const ok = r.ok;
        $('apiChip').textContent = ok ? '● API Online' : '● API Degraded';
        $('apiChip').className = 'status-chip ' + (ok ? 'online' : 'offline');
    } catch {
        $('apiChip').textContent = '● API Offline';
        $('apiChip').className = 'status-chip offline';
    }
}

async function checkModel() {
    try {
        const r = await fetch('/api/ollama');
        if (!r.ok) throw 0;
        const d = await r.json();
        const name = d.ok ? (String(d.model || 'ready').split(',')[0]) : 'unavailable';
        $('modelChip').textContent = '● ' + name;
        $('modelChip').className = 'status-chip ' + (d.ok ? 'online' : 'offline');
    } catch {
        $('modelChip').textContent = '● Model N/A';
        $('modelChip').className = 'status-chip offline';
    }
}

// ── Submit Assessment ──────────────────────────────────────────────────
async function handleSubmit(e) {
    e.preventDefault();
    const query = $('queryInput').value.trim();
    if (!query) return;

    const btn = $('submitBtn');
    btn.disabled = true;
    btn.querySelector('.btn-text').textContent = 'Running…';
    btn.querySelector('.btn-spinner').style.display = 'inline-block';

    // Build payload
    const body = {
        query,
        country_code: ($('paramCountry').value || 'IND').toUpperCase(),
        time_horizon: $('paramHorizon').value || '30d',
        collection_depth: $('paramDepth').value || 'standard',
        use_red_team: true,
        use_mcts: false,
    };

    // Show progress
    $('progressCard').style.display = 'block';
    $('progressFill').style.width = '0%';
    $('progressDetail').textContent = 'Submitting…';
    resetPipeline();

    // Hide old results
    $('resultCard').style.display = 'none';
    $('briefingCard').style.display = 'none';
    $('sourcesCard').style.display = 'none';

    try {
        // Try v3 async first
        let jobId = null;
        try {
            const r = await fetch(API_V3 + '/assess', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });
            if (r.ok) {
                const d = await r.json();
                jobId = d.job_id;
            }
        } catch { /* v3 not available */ }

        if (jobId) {
            // Async polling mode
            state.jobId = jobId;
            startPolling(jobId);
        } else {
            // Fallback: try synchronous endpoints
            await runSyncQuery(body);
        }
    } catch (err) {
        showError(err.message);
    }
}

// ── Sync Fallback ──────────────────────────────────────────────────────
async function runSyncQuery(body) {
    $('progressDetail').textContent = 'Running synchronous query…';
    animatePipelineSync();

    // Try /api/simple/query first, then /v2/query
    let data = null;

    try {
        const r = await fetch('/api/simple/query', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query: body.query, country_code: body.country_code }),
        });
        if (r.ok) data = await r.json();
    } catch { /* fallback */ }

    if (!data) {
        const r = await fetch('/v2/query', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query: body.query, country_code: body.country_code }),
        });
        if (!r.ok) {
            let msg = `HTTP ${r.status}`;
            try { msg = (await r.json()).error || msg; } catch {}
            throw new Error(msg);
        }
        data = await r.json();
    }

    // Build a result from sync response
    const result = {
        answer: data.answer || data.summary || '',
        confidence: data.confidence || 0,
        risk_level: data.risk_level || data.outcome || 'UNKNOWN',
        outcome: data.outcome || 'UNKNOWN',
        job_id: data.trace_id || 'sync',
        sre: data.sre || null,
        gate_verdict: data.gate_verdict || null,
        evidence_chain: data.evidence_chain || data.evidence || [],
        verification_chain: data.verification_chain || null,
        council: data.council || data.ministers || null,
        sources: data.sources || [],
    };

    finishAssessment(result);
}

// ── Pipeline Animation ────────────────────────────────────────────────
function resetPipeline() {
    $$('.pipe-step').forEach(s => {
        s.classList.remove('active', 'done');
    });
}

function setPipelinePhase(phase) {
    const idx = PHASES.indexOf(phase);
    $$('.pipe-step').forEach((s, i) => {
        s.classList.remove('active', 'done');
        if (i < idx) s.classList.add('done');
        else if (i === idx) s.classList.add('active');
    });
}

function animatePipelineSync() {
    const steps = Array.from($$('.pipe-step'));
    steps.forEach((s, i) => {
        setTimeout(() => {
            steps.forEach(x => x.classList.remove('active'));
            s.classList.add('active');
            if (i > 0) steps[i-1].classList.add('done');
        }, i * 800);
    });
    setTimeout(() => {
        steps.forEach(s => { s.classList.remove('active'); s.classList.add('done'); });
    }, steps.length * 800);
}

// ── Polling ────────────────────────────────────────────────────────────
function startPolling(jobId) {
    state.startTime = Date.now();

    state.elapsedTimer = setInterval(() => {
        const sec = Math.round((Date.now() - state.startTime) / 1000);
        $('progressElapsed').textContent = fmtElapsed(sec);
    }, 1000);

    state.pollTimer = setInterval(() => pollJob(jobId), POLL_MS);
    pollJob(jobId);
}

function stopPolling() {
    clearInterval(state.pollTimer);
    clearInterval(state.elapsedTimer);
    state.pollTimer = null;
    state.elapsedTimer = null;
}

async function pollJob(jobId) {
    try {
        const r = await fetch(API_V3 + '/jobs/' + jobId);
        if (!r.ok) return;
        const s = await r.json();

        // Update progress
        $('progressFill').style.width = (s.progress_pct || 0) + '%';
        $('progressDetail').textContent = s.phase_detail || s.phase || '…';
        setPipelinePhase(s.phase);

        if (s.status === 'COMPLETED') {
            stopPolling();
            await fetchResult(jobId);
            loadPastJobs();
        } else if (s.status === 'FAILED') {
            stopPolling();
            showError(s.error || 'Assessment failed');
        }
    } catch (err) {
        console.warn('Poll error:', err);
    }
}

async function fetchResult(jobId) {
    const r = await fetch(API_V3 + '/jobs/' + jobId + '/result');
    if (!r.ok) { showError('Failed to load result'); return; }
    const result = await r.json();
    result.job_id = jobId;
    finishAssessment(result);
}

// ── Display Result ─────────────────────────────────────────────────────
function finishAssessment(result) {
    const btn = $('submitBtn');
    btn.disabled = false;
    btn.querySelector('.btn-text').textContent = 'Run Assessment';
    btn.querySelector('.btn-spinner').style.display = 'none';
    $('progressCard').style.display = 'none';

    // Pipeline all done
    $$('.pipe-step').forEach(s => { s.classList.remove('active'); s.classList.add('done'); });

    // Show tabs
    $('tabBar').style.display = 'flex';
    $$('.tab-panel').forEach(p => p.style.display = '');

    // Activate SRE tab
    $$('.tab-btn').forEach(b => b.classList.remove('active'));
    $$('.tab-panel').forEach(p => p.classList.remove('active'));
    document.querySelector('.tab-btn[data-tab="sre"]').classList.add('active');
    $('sre-panel').classList.add('active');

    // === RISK CARD ===
    const conf = clamp01(result.confidence);
    const riskText = result.risk_level || result.outcome || 'UNKNOWN';
    const riskClass = riskText.toLowerCase().replace(/[^a-z]/g,'');

    $('resultCard').style.display = 'block';
    $('riskLevel').textContent = riskText + ' — ' + pct(conf);
    $('riskLevel').className = 'risk-level ' + riskClass;
    $('confValue').textContent = pct(conf);
    $('confValue').style.color = conf > 0.6 ? 'var(--green)' : conf > 0.4 ? 'var(--yellow)' : 'var(--red)';
    $('outcomeValue').textContent = result.outcome || '—';
    $('traceValue').textContent = result.job_id ? result.job_id.substring(0, 12) : '—';
    $('elapsedValue').textContent = state.startTime ? fmtElapsed(Math.round((Date.now() - state.startTime) / 1000)) : '—';
    $('escFill').style.width = pct(conf);

    // === BRIEFING ===
    if (result.answer) {
        $('briefingCard').style.display = 'block';
        $('briefingText').innerHTML = formatAnswer(result.answer);
    }

    // === SRE ===
    renderSRE(result.sre);

    // === COUNCIL ===
    renderCouncil(result.council);

    // === GATE ===
    renderGate(result.gate_verdict);

    // === EVIDENCE ===
    renderEvidence(result.evidence_chain);

    // === REASONING ===
    renderReasoning(result.verification_chain);

    // === SOURCES ===
    renderSources(result.sources);

    checkHealth();
}

// ── Render: SRE ────────────────────────────────────────────────────────
function renderSRE(sre) {
    if (!sre) return;
    const score = clamp01(sre.escalation_score || 0);
    $('gaugeVal').textContent = pct(score);
    const rl = (sre.risk_level || 'UNKNOWN').toLowerCase();
    $('gaugeRisk').textContent = (sre.risk_level || '—').toUpperCase();
    $('gaugeRisk').className = 'gauge-risk ' + rl;

    // Conic gradient for gauge ring
    const deg = score * 360;
    const color = score > 0.6 ? 'var(--red)' : score > 0.35 ? 'var(--orange)' : 'var(--green)';
    $('gaugeRing').style.background = `conic-gradient(${color} ${deg}deg, var(--s2) ${deg}deg)`;

    setBar('sreCap', 'sreCapVal', sre.capability || 0);
    setBar('sreInt', 'sreIntVal', sre.intent || 0);
    setBar('sreStab', 'sreStabVal', sre.stability || 0);
    setBar('sreCost', 'sreCostVal', sre.cost || 0);
}

function setBar(fillId, valId, v) {
    const fill = $(fillId);
    const val = $(valId);
    if (fill) fill.style.width = pct(v);
    if (val) val.textContent = pct(v);
}

// ── Render: Council ────────────────────────────────────────────────────
function renderCouncil(council) {
    const el = $('councilList');
    if (!el) return;

    if (!council || (Array.isArray(council) && council.length === 0)) {
        el.innerHTML = '<div class="empty-hint">No council data in this assessment</div>';
        return;
    }

    const ministers = Array.isArray(council) ? council : (council.ministers || []);
    if (ministers.length === 0) {
        el.innerHTML = '<div class="empty-hint">No minister reports available</div>';
        return;
    }

    const icons = ['🛡', '🤝', '📊', '🏛', '⚡'];
    const colors = ['var(--red)', 'var(--blue)', 'var(--green)', 'var(--yellow)', 'var(--purple)'];

    el.innerHTML = ministers.map((m, i) => {
        const conf = clamp01(m.confidence || 0);
        const confColor = conf > 0.6 ? 'var(--green)' : conf > 0.35 ? 'var(--yellow)' : 'var(--red)';
        return `
        <div class="minister-row" style="border-left-color:${colors[i % colors.length]}">
            <div class="minister-icon" style="background:${colors[i % colors.length]}20">${icons[i % icons.length]}</div>
            <div class="minister-info">
                <div class="minister-name">${esc(m.minister_name || m.name || 'Minister ' + (i+1))}</div>
                <div class="minister-dim">${esc(m.hypothesis || m.dimension || '')}</div>
                <div class="minister-drivers">${esc((m.predicted_signals || m.signals || []).slice(0,4).join(', '))}</div>
            </div>
            <div class="minister-conf" style="color:${confColor}">${Math.round(conf*100)}%</div>
        </div>`;
    }).join('');
}

// ── Render: Gate ───────────────────────────────────────────────────────
function renderGate(gate) {
    const el = $('gateContent');
    if (!el) return;

    if (!gate) {
        el.innerHTML = '<div class="empty-hint">No gate verdict data</div>';
        return;
    }

    const approved = gate.approved !== false;
    const cls = approved ? 'approved' : 'withheld';
    const icon = approved ? '✅' : '🚫';
    const reasons = gate.reasons || [];
    const gaps = gate.intelligence_gaps || [];

    el.innerHTML = `
        <div class="gate-verdict-box ${cls}">
            <div class="gate-icon">${icon}</div>
            <div class="gate-decision">${esc(gate.decision || (approved ? 'APPROVED' : 'WITHHELD'))}</div>
            <div class="gate-conf">Confidence: ${pct(gate.confidence || 0)}</div>
        </div>
        ${reasons.length ? `
        <div class="gate-rules">
            ${reasons.map(r => `<div class="gate-rule"><span class="gate-rule-icon">${approved ? '✓' : '⚠'}</span>${esc(r)}</div>`).join('')}
        </div>` : ''}
        ${gaps.length ? `
        <div><strong style="font-size:12px;color:var(--dim)">Intelligence Gaps:</strong>
            <div class="gate-gaps">${gaps.map(g => `<span class="gap-badge">${esc(g)}</span>`).join('')}</div>
        </div>` : ''}
    `;
}

// ── Render: Evidence ───────────────────────────────────────────────────
function renderEvidence(evidence) {
    const el = $('evidenceContent');
    if (!el) return;

    if (!evidence || evidence.length === 0) {
        el.innerHTML = '<div class="empty-hint">No evidence atoms available</div>';
        return;
    }

    const items = Array.isArray(evidence) ? evidence : [];
    const rows = items.map(e => {
        const dim = (e.dimension || 'unknown').toLowerCase();
        return `<tr>
            <td><span class="dim-dot ${dim}"></span>${esc(e.dimension || 'UNKNOWN')}</td>
            <td><strong>${esc(e.signal_name || e.signal || '')}</strong></td>
            <td>${esc(e.source_type || e.source || '')}</td>
            <td>${Math.round(clamp01(e.confidence || 0) * 100)}%</td>
            <td title="${esc(e.raw_snippet || '')}">${esc((e.source_detail || e.detail || '').substring(0, 60))}</td>
        </tr>`;
    }).join('');

    el.innerHTML = `
        <table class="evidence-table">
            <thead><tr><th>Dimension</th><th>Signal</th><th>Source</th><th>Conf</th><th>Detail</th></tr></thead>
            <tbody>${rows}</tbody>
        </table>`;
}

// ── Render: Reasoning ──────────────────────────────────────────────────
function renderReasoning(chain) {
    const el = $('reasoningContent');
    if (!el) return;

    if (!chain || !chain.steps || chain.steps.length === 0) {
        el.innerHTML = '<div class="empty-hint">No reasoning chain recorded</div>';
        return;
    }

    el.innerHTML = chain.steps.map((step, i) => `
        <div class="reasoning-step">
            <div class="step-num">${step.step || i + 1}</div>
            <div class="step-body">
                <div class="step-title">${esc(step.title || '')}</div>
                <div class="step-desc">${esc(step.description || '')}</div>
            </div>
        </div>
    `).join('');
}

// ── Render: Sources ────────────────────────────────────────────────────
function renderSources(sources) {
    const el = $('sourcesList');
    if (!el) return;

    if (!sources || sources.length === 0) {
        $('sourcesCard').style.display = 'none';
        return;
    }

    $('sourcesCard').style.display = 'block';
    el.innerHTML = sources.map(s => {
        const name = typeof s === 'string' ? s : (s.name || s.source || '');
        const score = typeof s === 'object' ? (s.reliability || s.confidence || '') : '';
        return `<div class="source-row"><span class="source-name">${esc(name)}</span>${score ? `<span class="source-score">${pct(score)}</span>` : ''}</div>`;
    }).join('');
}

// ── Past Jobs ──────────────────────────────────────────────────────────
async function loadPastJobs() {
    try {
        const r = await fetch(API_V3 + '/jobs?limit=10');
        if (!r.ok) return;
        const jobs = await r.json();
        const el = $('pastList');
        if (!el) return;

        if (jobs.length === 0) {
            el.innerHTML = '<div class="empty-hint" style="border:none;padding:12px">No past assessments</div>';
            return;
        }

        el.innerHTML = jobs.map(j => {
            const rl = (j.risk_level || '').toLowerCase();
            const time = j.created_at ? new Date(j.created_at).toLocaleString() : '';
            return `
                <div class="past-item" onclick="loadPastJob('${esc(j.job_id)}')">
                    <span class="past-query">${esc(j.query_preview || j.job_id)}</span>
                    ${j.risk_level ? `<span class="risk-badge ${rl}">${j.risk_level}</span>` : ''}
                    <span style="font-size:10px;color:var(--dim)">${time}</span>
                </div>`;
        }).join('');
    } catch { /* silently fail */ }
}

async function loadPastJob(jobId) {
    state.startTime = Date.now();
    try {
        await fetchResult(jobId);
    } catch (err) {
        showError('Failed to load past job: ' + err.message);
    }
}

// ── Utilities ──────────────────────────────────────────────────────────
function showError(msg) {
    $('progressCard').style.display = 'none';
    $('resultCard').style.display = 'block';
    $('riskLevel').textContent = 'ERROR';
    $('riskLevel').className = 'risk-level critical';
    $('briefingCard').style.display = 'block';
    $('briefingText').innerHTML = `<span style="color:var(--red)"><strong>Error:</strong> ${esc(msg)}</span>`;

    const btn = $('submitBtn');
    btn.disabled = false;
    btn.querySelector('.btn-text').textContent = 'Run Assessment';
    btn.querySelector('.btn-spinner').style.display = 'none';

    stopPolling();
    resetPipeline();
}

function formatAnswer(text) {
    if (!text) return '';
    return String(text)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/^### (.+)$/gm, '<h3>$1</h3>')
        .replace(/^## (.+)$/gm, '<h2>$1</h2>')
        .replace(/^# (.+)$/gm, '<h1>$1</h1>')
        .replace(/\n\n/g, '</p><p>')
        .replace(/\n/g, '<br>')
        .replace(/^/, '<p>')
        .replace(/$/, '</p>');
}
