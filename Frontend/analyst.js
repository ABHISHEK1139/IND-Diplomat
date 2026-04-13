/**
 * IND-Diplomat Analyst Workstation — analyst.js
 * ==============================================
 * Extends the base app.js with:
 *   - Async job submission + polling
 *   - Parameter controls
 *   - SRE decomposition visualization
 *   - Gate verdict display
 *   - Evidence provenance table
 *   - Trend chart (Chart.js)
 *   - Formatted report display
 *   - Past assessments sidebar
 *   - Verification/reasoning chain
 *
 * Does NOT modify any base app.js functions — only extends.
 */

// ── Config ───────────────────────────────────────────────────────────

const ANALYST_API = '/api/v3';   // proxied via server.py → localhost:8100
const POLL_INTERVAL = 2000;      // ms

// ── State ────────────────────────────────────────────────────────────

let analystState = {
    currentJobId: null,
    pollTimer: null,
    pollStartTime: null,
    elapsedTimer: null,
    trendsChart: null,
    currentResult: null,
};

// ── Phase ordering (for progress tracker) ────────────────────────────
const PHASE_ORDER = ['SCOPE_CHECK', 'SENSORS', 'COUNCIL', 'GATE', 'REPORT'];

// ── DOM elements ─────────────────────────────────────────────────────

const $  = id => document.getElementById(id);
const $$ = sel => document.querySelectorAll(sel);

// ── Init (runs after base app.js DOMContentLoaded) ─────────────────

document.addEventListener('DOMContentLoaded', () => {
    initAnalystWorkstation();
});

function initAnalystWorkstation() {
    // Past jobs toggle
    const toggle = $('pastJobsToggle');
    const header = document.querySelector('.past-jobs-header');
    if (toggle && header) {
        header.addEventListener('click', () => {
            const list = $('pastJobsList');
            const open = list.style.display !== 'none';
            list.style.display = open ? 'none' : 'block';
            toggle.classList.toggle('open', !open);
        });
    }

    // Evidence filter
    const evidenceFilter = $('evidenceFilter');
    if (evidenceFilter) {
        evidenceFilter.addEventListener('change', () => {
            if (analystState.currentResult) {
                renderEvidenceTable(analystState.currentResult.evidence_chain, evidenceFilter.value);
            }
        });
    }

    // Load past jobs on init
    loadPastJobs();
}

// ── Submit Assessment ────────────────────────────────────────────────

async function handleAnalystSubmit() {
    const query = $('queryInput').value.trim();
    if (!query) return;

    const btn = $('submitBtn');
    btn.classList.add('loading');

    // Read parameters
    const body = {
        query: query,
        country_code: ($('paramCountry')?.value || 'IRN').toUpperCase(),
        time_horizon: $('paramHorizon')?.value || '30d',
        evidence_strictness: $('paramStrictness')?.value || 'balanced',
        source_mode: $('paramSources')?.value || 'hybrid',
        gate_threshold: $('paramGate')?.value || 'default',
        collection_depth: $('paramDepth')?.value || 'standard',
        use_red_team: true,
        use_mcts: false,
    };

    // Read feature toggle overrides
    document.querySelectorAll('.toggle-chip').forEach(chip => {
        const flag = chip.dataset.flag;
        const checked = chip.querySelector('input')?.checked;
        if (flag === 'enable_red_team') body.use_red_team = checked;
        if (flag === 'enable_mcts') body.use_mcts = checked;
    });

    try {
        const resp = await fetch(`${ANALYST_API}/assess`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });

        if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            throw new Error(err.detail || resp.statusText);
        }

        const data = await resp.json();
        analystState.currentJobId = data.job_id;

        // Show progress tracker
        showProgressSection(true);
        resetProgressPhases();
        startPolling(data.job_id);

    } catch (err) {
        console.error('Assessment submit failed:', err);
        showError(`Failed to start assessment: ${err.message}`);
        btn.classList.remove('loading');
    }
}

// ── Polling ──────────────────────────────────────────────────────────

function startPolling(jobId) {
    analystState.pollStartTime = Date.now();

    // Elapsed timer
    analystState.elapsedTimer = setInterval(() => {
        const elapsed = Math.round((Date.now() - analystState.pollStartTime) / 1000);
        const el = $('progressElapsed');
        if (el) el.textContent = formatElapsed(elapsed);
    }, 1000);

    // Poll job status
    analystState.pollTimer = setInterval(() => pollJobStatus(jobId), POLL_INTERVAL);

    // Immediate first poll
    pollJobStatus(jobId);
}

function stopPolling() {
    if (analystState.pollTimer) {
        clearInterval(analystState.pollTimer);
        analystState.pollTimer = null;
    }
    if (analystState.elapsedTimer) {
        clearInterval(analystState.elapsedTimer);
        analystState.elapsedTimer = null;
    }
}

async function pollJobStatus(jobId) {
    try {
        const resp = await fetch(`${ANALYST_API}/jobs/${jobId}`);
        if (!resp.ok) return;

        const status = await resp.json();
        updateProgressUI(status);

        if (status.status === 'COMPLETED') {
            stopPolling();
            await loadResult(jobId);
            loadPastJobs();
        } else if (status.status === 'FAILED') {
            stopPolling();
            showError(`Assessment failed: ${status.error || 'Unknown error'}`);
            $('submitBtn')?.classList.remove('loading');
        }
    } catch (err) {
        console.warn('Poll error:', err);
    }
}

// ── Progress UI ──────────────────────────────────────────────────────

function showProgressSection(show) {
    const el = $('progressSection');
    if (el) el.style.display = show ? 'block' : 'none';
}

function resetProgressPhases() {
    $$('.phase-step').forEach(step => {
        step.classList.remove('active', 'completed');
    });
    $$('.phase-connector').forEach(c => c.classList.remove('done'));
    const fill = $('progressBarFill');
    if (fill) fill.style.width = '0%';
    const detail = $('progressDetail');
    if (detail) detail.textContent = 'Queued…';
}

function updateProgressUI(status) {
    const currentPhase = status.phase;
    const currentIdx = PHASE_ORDER.indexOf(currentPhase);

    // Update phase dots in progress section
    const steps = Array.from($$('.phase-step'));
    const connectors = Array.from($$('.phase-connector'));

    steps.forEach((step, i) => {
        step.classList.remove('active', 'completed');
        if (i < currentIdx) {
            step.classList.add('completed');
        } else if (i === currentIdx) {
            step.classList.add('active');
        }
    });

    connectors.forEach((c, i) => {
        c.classList.toggle('done', i < currentIdx);
    });

    // Update main pipeline flow UI from app.js to reflect Analyst Phases
    const pipelineStages = Array.from(document.querySelectorAll('.pipeline-stage'));
    if (pipelineStages.length > 0) {
        // Map Analyst phases to app.js's 17 pipeline stages broadly
        const mapping = {
            'SCOPE_CHECK': 2,
            'SENSORS': 6,
            'COUNCIL': 11,
            'GATE': 14,
            'REPORT': 17
        };
        const maxStage = mapping[currentPhase] || 0;
        
        pipelineStages.forEach((stageEl, i) => {
            stageEl.classList.remove('running', 'success', 'skipped', 'pending');
            if (i < maxStage - 1) {
                stageEl.classList.add('success');
            } else if (i === maxStage - 1) {
                stageEl.classList.add('running');
            } else {
                stageEl.classList.add('pending');
            }
        });
    }

    // Progress bar
    const fill = $('progressBarFill');
    if (fill) fill.style.width = `${status.progress_pct}%`;

    // Detail text
    const detail = $('progressDetail');
    if (detail) detail.textContent = status.phase_detail || status.phase;
}

// ── Load Result ──────────────────────────────────────────────────────

async function loadResult(jobId) {
    try {
        const resp = await fetch(`${ANALYST_API}/jobs/${jobId}/result`);
        if (!resp.ok) {
            if (resp.status === 202) {
                // Still running
                return;
            }
            throw new Error(await resp.text());
        }

        const result = await resp.json();
        analystState.currentResult = result;

        // Hide progress, show results
        showProgressSection(false);
        $('submitBtn')?.classList.remove('loading');

        // Update all panels
        displayFullResult(result);

    } catch (err) {
        console.error('Load result failed:', err);
        showError(`Failed to load result: ${err.message}`);
        $('submitBtn')?.classList.remove('loading');
    }
}

function displayFullResult(result) {
    // Answer section
    const answerEl = $('answerContent');
    if (answerEl) {
        answerEl.innerHTML = formatAnswer(result.answer || '');
    }

    // Confidence bar
    const confPct = Math.round((result.confidence || 0) * 100);
    const confFill = $('confidenceFill');
    if (confFill) confFill.style.width = `${confPct}%`;
    const confVal = $('confidenceValue');
    if (confVal) confVal.textContent = `${confPct}%`;

    // Trace info
    const traceEl = $('traceId');
    if (traceEl) traceEl.textContent = result.job_id || '—';

    // Update new tabs
    updateSRETab(result.sre);
    updateGateTab(result.gate_verdict);
    
    const evContainer = evidenceTable; 
    if (evContainer && result.evidence_chain) { 
        evContainer.innerHTML = result.evidence_chain.map(e => <tr><td></td><td><strong></strong></td><td></td><td>%</td></tr>).join('');
    }

    updateReportTab(result.formatted_report);
    updateVerificationReasoningTab(result.verification_chain);

    // Update existing tabs from base app
    if (typeof updateSourcesTab === 'function') updateSourcesTab(result.sources || []);
    if (typeof updateDossierTab === 'function') updateDossierTab(result.dossier_hits || []);
    if (typeof updateReliabilityTab === 'function') updateReliabilityTab(result.confidence_ledger || []);
    if (typeof updatePlaybookTab === 'function') updatePlaybookTab(result.scenario_playbook);

    // Load trends chart
    const cc = result.request?.country_code || 'IRN';
    loadTrendsChart(cc);

    // Switch to evidence tab by default
    activateTab('evidence');

    // Show results container
    const rc = $('resultsContainer');
    if (rc) rc.style.display = 'grid';
}

// ── SRE Tab ──────────────────────────────────────────────────────────

function updateSRETab(sre) {
    if (!sre) return;

    // Gauge
    const scoreStr = ((sre.escalation_score || 0) * 100).toFixed(1);
    const gaugeVal = $('sreGaugeValue');
    if (gaugeVal) gaugeVal.textContent = `${scoreStr}%`;

    const gaugeRisk = $('sreGaugeRisk');
    if (gaugeRisk) {
        const rl = sre.risk_level || 'UNKNOWN';
        gaugeRisk.textContent = rl;
        gaugeRisk.className = `gauge-risk ${rl.toLowerCase()}`;
    }

    // Domain bars
    setDomainBar('sreCap', 'sreCapVal', sre.capability || 0);
    setDomainBar('sreInt', 'sreIntVal', sre.intent || 0);
    setDomainBar('sreStab', 'sreStabVal', sre.stability || 0);
    setDomainBar('sreCost', 'sreCostVal', sre.cost || 0);

    // Trend bonus
    const tb = $('sreTrendBonus');
    if (tb) tb.textContent = `trend_bonus: +${((sre.trend_bonus || 0) * 100).toFixed(1)}%`;
}

function setDomainBar(fillId, valId, value) {
    const fill = $(fillId);
    const val = $(valId);
    if (fill) fill.style.width = `${(value * 100).toFixed(0)}%`;
    if (val) val.textContent = `${(value * 100).toFixed(1)}%`;
}

// ── Gate Tab ─────────────────────────────────────────────────────────

function updateGateTab(gate) {
    if (!gate) return;

    const card = $('gateVerdictCard');
    if (card) {
        card.classList.remove('approved', 'withheld');
        card.classList.add(gate.approved ? 'approved' : 'withheld');
    }

    const icon = $('gateIcon');
    if (icon) icon.textContent = gate.approved ? '✅' : '🚫';

    const decision = $('gateDecision');
    if (decision) decision.textContent = gate.decision;

    const conf = $('gateConfidence');
    if (conf) conf.textContent = `Confidence: ${(gate.confidence * 100).toFixed(1)}%`;

    // Reasons
    const reasonsEl = $('gateReasons');
    if (reasonsEl) {
        if (!gate.reasons || gate.reasons.length === 0) {
            reasonsEl.innerHTML = '<li>Assessment approved — no blocking conditions</li>';
        } else {
            reasonsEl.innerHTML = gate.reasons.map(r => `<li>${escHtml(r)}</li>`).join('');
        }
    }

    // Gaps
    const gapsEl = $('gateGaps');
    if (gapsEl) {
        if (!gate.intelligence_gaps || gate.intelligence_gaps.length === 0) {
            gapsEl.innerHTML = '<span style="color: var(--success);">No gaps</span>';
        } else {
            gapsEl.innerHTML = gate.intelligence_gaps
                .map(g => `<span class="gap-badge">${escHtml(g)}</span>`)
                .join('');
        }
    }

    // Collection tasks
    const tasksEl = $('gateTasks');
    if (tasksEl) {
        if (!gate.collection_tasks || gate.collection_tasks.length === 0) {
            tasksEl.innerHTML = '<span style="color: var(--text-muted);">No pending tasks</span>';
        } else {
            tasksEl.innerHTML = gate.collection_tasks.map(t => `
                <div class="task-card">
                    <div class="task-signal">${escHtml(t.signal || t.name || '')}</div>
                    <div class="task-reason">${escHtml(t.reason || t.detail || '')}</div>
                </div>
            `).join('');
        }
    }
}

// ── Evidence Table ───────────────────────────────────────────────────

function renderEvidenceTable(evidence, filter) {
    const container = $('evidenceTable');
    if (!container) return;

    if (!evidence || evidence.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <span class="empty-icon">🔍</span>
                <p>No evidence atoms available</p>
            </div>`;
        return;
    }

    let filtered = evidence;
    if (filter && filter !== 'all') {
        filtered = evidence.filter(e => e.dimension === filter);
    }

    const rows = filtered.map(e => {
        const dimClass = (e.dimension || 'unknown').toLowerCase();
        const confPct = (e.confidence * 100).toFixed(0);
        return `<tr>
            <td><span class="dim-dot ${dimClass}"></span>${escHtml(e.dimension || 'UNKNOWN')}</td>
            <td><strong>${escHtml(e.signal_name)}</strong></td>
            <td>${escHtml(e.source_type)}</td>
            <td>${confPct}%</td>
            <td title="${escHtml(e.raw_snippet || '')}">${escHtml((e.source_detail || '').substring(0, 60))}</td>
        </tr>`;
    }).join('');

    container.innerHTML = `
        <table class="evidence-table">
            <thead><tr>
                <th>Dimension</th>
                <th>Signal</th>
                <th>Source</th>
                <th>Confidence</th>
                <th>Detail</th>
            </tr></thead>
            <tbody>${rows}</tbody>
        </table>`;
}

// ── Trends Chart ─────────────────────────────────────────────────────

async function loadTrendsChart(countryCode) {
    const emptyEl = $('trendsEmpty');
    const canvas = $('trendsChart');
    if (!canvas) return;

    try {
        const resp = await fetch(`${ANALYST_API}/trends/${countryCode}?hours=72`);
        if (!resp.ok) throw new Error('No trend data');

        const points = await resp.json();
        if (!points || points.length === 0) {
            if (emptyEl) emptyEl.style.display = 'flex';
            return;
        }

        if (emptyEl) emptyEl.style.display = 'none';

        // Destroy old chart
        if (analystState.trendsChart) {
            analystState.trendsChart.destroy();
        }

        const labels = points.map(p => {
            try { return new Date(p.timestamp).toLocaleTimeString(); }
            catch { return p.timestamp; }
        });

        const ctx = canvas.getContext('2d');
        analystState.trendsChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Escalation',
                        data: points.map(p => (p.escalation_score * 100).toFixed(1)),
                        borderColor: '#ef4444',
                        backgroundColor: 'rgba(239, 68, 68, 0.1)',
                        fill: true,
                        tension: 0.3,
                        borderWidth: 2,
                    },
                    {
                        label: 'Capability',
                        data: points.map(p => ((p.domains?.capability || 0) * 100).toFixed(1)),
                        borderColor: '#f59e0b',
                        borderWidth: 1.5,
                        tension: 0.3,
                        borderDash: [4, 2],
                    },
                    {
                        label: 'Intent',
                        data: points.map(p => ((p.domains?.intent || 0) * 100).toFixed(1)),
                        borderColor: '#3b82f6',
                        borderWidth: 1.5,
                        tension: 0.3,
                        borderDash: [4, 2],
                    },
                    {
                        label: 'Stability',
                        data: points.map(p => ((p.domains?.stability || 0) * 100).toFixed(1)),
                        borderColor: '#06b6d4',
                        borderWidth: 1.5,
                        tension: 0.3,
                        borderDash: [4, 2],
                    },
                    {
                        label: 'Cost',
                        data: points.map(p => ((p.domains?.cost || 0) * 100).toFixed(1)),
                        borderColor: '#8b5cf6',
                        borderWidth: 1.5,
                        tension: 0.3,
                        borderDash: [4, 2],
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        labels: { color: '#9ca3af', font: { size: 11 } },
                    },
                },
                scales: {
                    x: {
                        ticks: { color: '#6b7280', font: { size: 10 } },
                        grid: { color: 'rgba(55, 65, 81, 0.3)' },
                    },
                    y: {
                        min: 0,
                        max: 100,
                        ticks: {
                            color: '#6b7280',
                            font: { size: 10 },
                            callback: v => v + '%',
                        },
                        grid: { color: 'rgba(55, 65, 81, 0.3)' },
                    },
                },
            },
        });

    } catch (err) {
        console.warn('Trends chart:', err);
        if (emptyEl) emptyEl.style.display = 'flex';
    }
}

// ── Report Tab ───────────────────────────────────────────────────────

function updateReportTab(reportText) {
    const container = $('reportContainer');
    if (!container) return;

    if (!reportText) {
        container.innerHTML = `
            <div class="empty-state">
                <span class="empty-icon">📋</span>
                <p>No formatted report available</p>
            </div>`;
        return;
    }

    container.innerHTML = `<div class="report-text">${escHtml(reportText)}</div>`;
}

// ── Verification / Reasoning Chain ───────────────────────────────────

function _OLD_updateVerificationReasoningTab(chain) {
    const reasoningEl = $('reasoningChain');
    if (!reasoningEl) return;

    if (!chain || !chain.steps || chain.steps.length === 0) {
        reasoningEl.innerHTML = `
            <div class="empty-state">
                <span class="empty-icon">🧠</span>
                <p>No reasoning chain available</p>
            </div>`;
        return;
    }

    reasoningEl.innerHTML = chain.steps.map(step => `
        <div class="reasoning-step">
            <span class="step-number">${step.step}</span>
            <div class="step-content">
                <h4>${escHtml(step.title)}</h4>
                <p>${escHtml(step.description)}</p>
            </div>
        </div>
    `).join('');
}

// ── Past Jobs ────────────────────────────────────────────────────────

async function loadPastJobs() {
    try {
        const resp = await fetch(`${ANALYST_API}/jobs?limit=10`);
        if (!resp.ok) return;

        const jobs = await resp.json();
        const list = $('pastJobsList');
        if (!list) return;

        if (jobs.length === 0) {
            list.innerHTML = '<div class="past-job-item"><span class="past-job-query" style="color:var(--text-muted)">No past assessments</span></div>';
            return;
        }

        list.innerHTML = jobs.map(job => {
            const riskClass = (job.risk_level || '').toLowerCase();
            const timeStr = job.created_at ? new Date(job.created_at).toLocaleString() : '';
            return `
                <div class="past-job-item" data-job-id="${job.job_id}" onclick="loadPastJob('${job.job_id}')">
                    <span class="past-job-query">${escHtml(job.query_preview || job.job_id)}</span>
                    <div class="past-job-meta">
                        ${job.risk_level ? `<span class="risk-badge ${riskClass}">${job.risk_level}</span>` : ''}
                        <span style="font-size:0.7rem;color:var(--text-muted)">${timeStr}</span>
                        <span style="font-size:0.7rem;color:var(--text-muted)">${job.status}</span>
                    </div>
                </div>
            `;
        }).join('');

    } catch (err) {
        console.warn('Load past jobs:', err);
    }
}

async function loadPastJob(jobId) {
    analystState.currentJobId = jobId;
    await loadResult(jobId);
}

// ── Tab switching helper ─────────────────────────────────────────────

function activateTab(tabName) {
    $$('.tab-btn').forEach(b => b.classList.remove('active'));
    $$('.tab-panel').forEach(p => p.classList.remove('active'));

    const btn = document.querySelector(`.tab-btn[data-tab="${tabName}"]`);
    const panel = $(`${tabName}-panel`);
    if (btn) btn.classList.add('active');
    if (panel) panel.classList.add('active');
}

// ── Utilities ────────────────────────────────────────────────────────

function formatElapsed(sec) {
    if (sec < 60) return `${sec}s`;
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return `${m}m ${s}s`;
}

function escHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

function showError(msg) {
    const answerEl = $('answerContent');
    if (answerEl) {
        answerEl.innerHTML = `<div style="color: var(--error);"><strong>Error:</strong> ${escHtml(msg)}</div>`;
    }
    showProgressSection(false);
}

// formatAnswer is defined in base app.js, but provide fallback
if (typeof formatAnswer === 'undefined') {
    function formatAnswer(text) {
        if (!text) return '';
        return text
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/\n\n/g, '</p><p>')
            .replace(/\n/g, '<br>')
            .replace(/^/, '<p>')
            .replace(/$/, '</p>');
    }
}

function _OLD_updateVerificationReasoningTab(chain) {
    const reasoningEl = reasoningChain;
    if (!reasoningEl) return;
    
    if (!chain || !chain.steps || chain.steps.length === 0) {
        reasoningEl.innerHTML = <div class="empty-state">No AI debate recorded.</div>;
        return;
    }
    
    // Attempt to map steps into conversations
    reasoningEl.innerHTML = chain.steps.map(step => {
        let name = step.title;
        
        

        let text = String(step.description);
        
        return <div class="expert-bubble">
            <div class="expert-name">
                <span class="expert-title"></span>
            </div>
            <div class="expert-desc"></div>
        </div>;
    }).join('');
}

function updateVerificationReasoningTab(chain) {
    const reasoningEl = reasoningChain;
    if (!reasoningEl) return;
    
    if (!chain || !chain.steps || chain.steps.length === 0) {
        reasoningEl.innerHTML = <div class="empty-state">No AI debate recorded.</div>;
        return;
    }
    
    // Attempt to map steps into conversations
    reasoningEl.innerHTML = chain.steps.map(step => {
        let name = step.title;
        
        

        let text = String(step.description);
        
        return <div class="expert-bubble">
            <div class="expert-name">
                <span class="expert-title"></span>
            </div>
            <div class="expert-desc"></div>
        </div>;
    }).join('');
}
