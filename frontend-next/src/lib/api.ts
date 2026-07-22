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

export interface InvestigationResult {
  query?: string;
  country?: string;
  threat_level?: string;
  dossier?: string;
  signals?: Array<{ title: string; source: string; category: string }>;
  hypotheses?: Array<{ text: string; probability: number }>;
  scenarios?: Array<{ name: string; probability: number; description: string }>;
  recommendations?: Array<{ option: string; impact: string; confidence: number }>;
  evidence_log?: Array<{ claim: string; sources: string[]; contradictions?: number }>;
  verification_score?: number;
  confidence_scores?: {
    evidence?: number;
    sources?: number;
    expert_agreement?: number;
    forecast_reliability?: number;
  };
  expert_reports?: Array<{ expert: string; analysis: string; status: string }>;
  entities?: Array<{ id: string; label: string; type: string }>;
  relationships?: Array<{ source: string; target: string; label: string }>;
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

// Get job result
export async function getJobResult(jobId: string): Promise<InvestigationResult> {
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
  onError?: (err: Event) => void
): WebSocket {
  const wsBase = API_BASE.replace("http", "ws");
  const ws = new WebSocket(`${wsBase}/ws/assessments`);

  ws.onopen = () => {
    ws.send(JSON.stringify({ action: "ping" }));
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
