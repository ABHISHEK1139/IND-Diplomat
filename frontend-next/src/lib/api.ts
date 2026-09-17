const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface InvestigationJob {
  job_id: string;
  status: string;
  query?: string;
  country?: string;
  created_at?: string;
  updated_at?: string;
  error?: string;
  trace_id?: string;
}

export interface MinisterHypothesis {
  minister: string;
  type: string;
  decision_mode?: string | null;
  heuristic_confidence?: number | null;
  llm_confidence?: number | null;
  agreement_score?: number | null;
  confidence: number;
  matched_signals: string[];
  missing_signals: string[];
  rationale?: string;
  critical_signal_refs?: string[];
  disagreement_notes?: string[];
  recalibrated_confidence?: number;
}

export interface InvestigationResult {
  query?: string;
  country?: string;
  status?: string;
  error?: string;
  trace_id?: string;
  elapsed_seconds?: number;
  threat_level?: string;
  briefing?: string;
  dossier?: string;
  signals?: Array<{ title?: string; entity?: string; action?: string; source?: string; source_ref?: string; intensity?: number; confidence?: number; category?: string }>;
  hypotheses?: Array<MinisterHypothesis | { text?: string; probability?: number; minister?: string; confidence?: number; matched_signals?: string[]; missing_signals?: string[]; rationale?: string }>;
  scenarios?: Array<{ name: string; probability: number; description: string }>;
  recommendations?: Array<{ option: string; impact: string; confidence: number | null }>;
  confidence_scores?: {
    evidence?: number | null;
    sources?: number | null;
    expert_agreement?: number | null;
    forecast_reliability?: number | null;
  };
  evidence_log?: Array<string | { claim: string; sources: string[]; contradictions?: number }>;
  verification_score?: number;
  expert_reports?: Array<{ expert: string; analysis: string; status: string }>;
  entities?: Array<{ id: string; label: string; type: string }>;
  relationships?: Array<{ source: string; target: string; label: string }>;
  timeline?: Array<{ date: string; title: string; cardTitle: string; cardDetailedText: string }>;
  red_team_report?: string[];
  raw_sources?: any[];
  xai_sources?: string[];
  refusal?: { status?: string; verification_score?: number; reasons?: string[]; recommendation?: string } | null;
  gate_verdict?: { approved?: boolean; decision?: string; reasons?: string[] };
  trajectory?: { prob_14d?: number; prob_30d?: number; prob_60d?: number; velocity?: number; trajectory_label?: string; label?: string };
  nextgen_sre?: { sre_escalation_score?: number; risk_level?: string };
  strategic_narrative?: any;
  black_swan?: { triggered?: boolean; reasons?: string[] } | null;
  fuzzy_trace?: { sre_escalation_score?: number; risk_level?: string };
  symbolic_guardrails?: { findings?: Array<{ message: string; rule: string }> };
  nash_equilibrium?: { recommended_strategy?: string };
}

// Create a new investigation
export async function createInvestigation(query: string, country: string = "IND"): Promise<InvestigationJob> {
  const res = await fetch(`${API_BASE}/api/v3/assess`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, country }),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

// Get job status
export async function getJobStatus(jobId: string): Promise<InvestigationJob> {
  const res = await fetch(`${API_BASE}/api/v3/jobs/${jobId}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

// Get job result. Returns either the assessment payload or a job envelope
// ({ status, result, error }) while the job is incomplete or failed.
export async function getJobResult(jobId: string): Promise<InvestigationResult & { result?: InvestigationResult | null }> {
  const res = await fetch(`${API_BASE}/api/v3/jobs/${jobId}/result`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

// Get evidence log
export async function getJobEvidence(jobId: string) {
  const res = await fetch(`${API_BASE}/api/v3/jobs/${jobId}/evidence`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

// List all jobs
export async function listJobs(): Promise<InvestigationJob[]> {
  const res = await fetch(`${API_BASE}/api/v3/jobs`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

// WebSocket connection for live pipeline updates
export function connectPipelineWS(
  onMessage: (data: Record<string, unknown>) => void,
  onError?: (err: Event) => void,
  jobId?: string
): WebSocket {
  const wsBase = API_BASE.replace("http", "ws");
  const ws = new WebSocket(`${wsBase}/ws/assessments`);

  ws.onopen = () => {
    ws.send(JSON.stringify({ action: "ping" }));
    if (jobId) {
      ws.send(JSON.stringify({ action: "subscribe", topic: `job:${jobId}` }));
    }
  };

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      onMessage(data);
    } catch {
      // ignore non-JSON messages
    }
  };

  ws.onerror = (err) => {
    onError?.(err);
  };

  return ws;
}
