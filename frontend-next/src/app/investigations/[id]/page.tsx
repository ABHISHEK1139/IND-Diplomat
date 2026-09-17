"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import { motion } from "framer-motion";
import PipelineTracker from "@/components/investigation/PipelineTracker";
import { connectPipelineWS, getJobResult, InvestigationResult } from "@/lib/api";
import LeftPanel from "@/components/investigation/LeftPanel";
import CenterPanel from "@/components/investigation/CenterPanel";
import RightPanel from "@/components/investigation/RightPanel";

type PhaseStatus = "waiting" | "running" | "complete" | "error";

const phaseOrder = ["planning", "collection", "worldmodel", "reasoning", "forecasting", "workspace", "learning"];

// Backend pipeline phases -> tracker display phases. Without this map the
// tracker steps sit in "waiting" mid-run because the backend emits its own
// stage names (council, cove_verification, briefing, ...).
const PHASE_MAP: Record<string, string> = {
  planning: "planning",
  collection: "collection",
  sre: "worldmodel",
  council: "reasoning",
  red_team: "reasoning",
  investigation: "reasoning",
  threat_synthesis: "reasoning",
  cove_verification: "reasoning",
  assessment_gate: "forecasting",
  briefing: "workspace",
  presentation: "workspace",
  report: "workspace",
};

// Mock data for the knowledge graph
const mockEntities = [
  { id: "india", label: "India", type: "country" },
  { id: "semiconductor", label: "Semiconductor", type: "sector" },
  { id: "tsmc", label: "TSMC", type: "organization" },
  { id: "taiwan", label: "Taiwan", type: "country" },
  { id: "usa", label: "USA", type: "country" },
  { id: "nvidia", label: "NVIDIA", type: "organization" },
  { id: "modi", label: "PM Modi", type: "person" },
  { id: "ism", label: "India Semiconductor Mission", type: "event" },
  { id: "chips_act", label: "CHIPS Act", type: "event" },
  { id: "ai_compute", label: "AI Compute", type: "technology" },
];

const mockRelationships = [
  { source: "india", target: "semiconductor", label: "INVESTS_IN" },
  { source: "india", target: "ism", label: "LAUNCHED" },
  { source: "ism", target: "semiconductor", label: "TARGETS" },
  { source: "semiconductor", target: "tsmc", label: "DOMINATED_BY" },
  { source: "tsmc", target: "taiwan", label: "HEADQUARTERED_IN" },
  { source: "usa", target: "chips_act", label: "ENACTED" },
  { source: "chips_act", target: "semiconductor", label: "SUBSIDIZES" },
  { source: "nvidia", target: "ai_compute", label: "LEADS" },
  { source: "ai_compute", target: "semiconductor", label: "REQUIRES" },
  { source: "usa", target: "nvidia", label: "HOME_OF" },
  { source: "modi", target: "india", label: "LEADS" },
  { source: "india", target: "nvidia", label: "IMPORTS_FROM" },
];

const mockEvidence = [
  { claim: "India imports 100% of advanced GPUs", sources: ["Reuters", "Govt. Report", "NVIDIA"], contradictions: 0 },
  { claim: "ISM has committed $10B to fab investment", sources: ["MeitY", "Economic Times", "Bloomberg"], contradictions: 1 },
  { claim: "India AI talent growing 20% YoY", sources: ["NASSCOM", "LinkedIn", "Stanford HAI"], contradictions: 0 },
  { claim: "TSMC considers India fab by 2028", sources: ["Nikkei Asia", "TSMC Annual Report"], contradictions: 2 },
];

const mockDebate = [
  { expert: "Economist", text: "India lacks fabrication infrastructure. The $10B ISM commitment is a fraction of what TSMC spends annually ($36B). Without foundry-grade fabs, India remains a design-only hub.", color: "text-warning" },
  { expert: "Technology Expert", text: "India's AI talent pipeline is the world's second largest. Coupled with the NVIDIA DGX Cloud partnership, India can lead in AI software and model training without domestic fabs.", color: "text-success" },
  { expert: "Devil's Advocate", text: "This analysis ignores US export controls on China. If controls expand to India-allied nations, GPU supply chains become vulnerable. No export control risk matrix has been presented.", color: "text-danger" },
  { expert: "Evidence Judge", text: "The claim about 20% talent growth needs primary citation from NASSCOM's 2024 report, not secondary media sources. Marking as NEEDS_CITATION.", color: "text-accent" },
];

export default function InvestigationWorkspacePage() {
  const params = useParams();
  const [statuses, setStatuses] = useState<Record<string, PhaseStatus>>({});
  const [expandedPhase, setExpandedPhase] = useState<string | null>(null);
  const [result, setResult] = useState<InvestigationResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);

  // Connect to live pipeline updates
  useEffect(() => {
    const idStr = Array.isArray(params?.id) ? params?.id[0] : params?.id;
    if (!idStr) return;

    // If it's the demo investigation, just use the mock simulation
    if (idStr.toString().startsWith("demo-")) {
      let i = 0;
      const interval = setInterval(() => {
        if (i >= phaseOrder.length) {
          clearInterval(interval);
          return;
        }
        setStatuses((prev) => {
          const next = { ...prev };
          if (i > 0) next[phaseOrder[i - 1]] = "complete";
          next[phaseOrder[i]] = "running";
          return next;
        });
        i++;
      }, 2200);
      setTimeout(() => {
        setStatuses({ planning: "running" });
      }, 0);
      return () => clearInterval(interval);
    }

    // Real API connection
    setTimeout(() => {
      setStatuses({ planning: "running" }); // Optimistic start
    }, 0);

    let isCompleted = false;
    let pollAttempts = 0;
    const MAX_POLL_ATTEMPTS = 150; // ~10 min backstop; terminal states stop earlier

    const markFailed = (message: string) => {
      if (isCompleted) return;
      isCompleted = true;
      clearInterval(pollInterval);
      setError(message);
      setStatuses((prev) => {
        const next = { ...prev };
        phaseOrder.forEach((p) => { next[p] = next[p] === "complete" ? "complete" : "error"; });
        return next;
      });
    };

    // Polling fallback to ensure results are fetched even if WebSocket disconnects or drops packet
    const pollInterval = setInterval(async () => {
      if (isCompleted) return;
      pollAttempts += 1;
      try {
        const res = await getJobResult(idStr);
        if (res && res.threat_level) {
          isCompleted = true;
          setResult(res);
          setStatuses((prev) => {
            const next = { ...prev };
            phaseOrder.forEach((p) => { next[p] = "complete"; });
            return next;
          });
          clearInterval(pollInterval);
          return;
        }
        // Terminal job envelope without a result: stop instead of polling forever.
        const jobStatus = String(res?.status || "").toUpperCase();
        if (jobStatus === "FAILED" || jobStatus === "ERROR") {
          markFailed(res?.error || `Job ${jobStatus.toLowerCase()}: no assessment was produced.`);
          return;
        }
      } catch {
        // Transient fetch failure — keep polling until the backstop.
      }
      if (pollAttempts >= MAX_POLL_ATTEMPTS) {
        markFailed("Timed out waiting for the assessment result.");
      }
    }, 4000);

    const ws = connectPipelineWS(
      (data: any) => {
        const eventType = String(data.type || data.event || "").toLowerCase();
        const jobId = data.job_id || idStr;

        if (jobId === idStr) {
          if (eventType.includes("update") || eventType.startsWith("phase.")) {
            const phase = typeof data.phase === "string" ? (PHASE_MAP[data.phase] || data.phase) : undefined;
            const rawStatus = data.status || (eventType.endsWith("completed") ? "complete" : "running");
            const status = rawStatus === "COMPLETED" ? "complete" : rawStatus === "FAILED" ? "error" : rawStatus;
            if (phase && phaseOrder.includes(phase)) {
              setStatuses((prev) => ({
                ...prev,
                [phase]: status,
              }));
            }
          } else if (
            eventType === "job_failed" ||
            eventType === "job.failed"
          ) {
            markFailed(data.error || "The assessment job failed with no result.");
          } else if (
            eventType === "pipeline_complete" ||
            eventType === "job_completed" ||
            eventType === "job.completed" ||
            eventType === "pipeline.completed"
          ) {
            isCompleted = true;
            clearInterval(pollInterval);
            getJobResult(idStr)
              .then((res) => {
                setResult(res);
                setStatuses((prev) => {
                  const next = { ...prev };
                  phaseOrder.forEach((p) => { next[p] = "complete"; });
                  return next;
                });
              })
              .catch((err) => setError(err.message));
          }
        }
      },
      (err) => {
        console.warn("WS disconnected, relying on polling fallback:", err);
      },
      idStr
    );

    return () => {
      clearInterval(pollInterval);
      ws.close();
    };
  }, [params?.id]);

  // Phase details come from the reported result — never hardcoded counts.
  const signalCount = result?.raw_sources?.length;
  const phaseDetails: Record<string, { sources?: number; credibility?: number; entities?: string[] }> = {
    ...(signalCount != null ? { collection: { sources: signalCount } } : {}),
    ...(result?.hypotheses && result.hypotheses.length > 0
      ? { reasoning: { entities: result.hypotheses.map((h: any) => h.minister || h.expert || "Minister").slice(0, 8) } }
      : {}),
  };

  // UI-02: mock workspace data is demo-only. Real investigations surface
  // pipeline data or explicit unavailable states — never fake jobs.
  const idStr = Array.isArray(params?.id) ? params?.id[0] : params?.id;
  const isDemo = typeof idStr === "string" && idStr.startsWith("demo-");

  // Confidence metrics pass through when the pipeline reported them;
  // individual nulls render as "n/a" bars instead of invented numbers.
  const cs = result?.confidence_scores;
  const metrics = cs && typeof cs.evidence === "number"
    ? {
        evidence: cs.evidence,
        sources: typeof cs.sources === "number" ? cs.sources : null,
        expertAgreement: typeof cs.expert_agreement === "number" ? cs.expert_agreement : null,
        forecastReliability: typeof cs.forecast_reliability === "number" ? cs.forecast_reliability : null,
      }
    : undefined;

  // Timeline projection points derived from the reported trajectory —
  // labeled as projections, never as historical events.
  const trajectory = result?.trajectory;
  const timeline = result?.timeline || (
    trajectory && (typeof trajectory.prob_14d === "number" || typeof trajectory.prob_30d === "number" || typeof trajectory.prob_60d === "number")
      ? ([
          ["T+14d", trajectory.prob_14d],
          ["T+30d", trajectory.prob_30d],
          ["T+60d", trajectory.prob_60d],
        ] as Array<[string, number | undefined]>)
          .filter(([, p]) => typeof p === "number")
          .map(([horizon, p]) => ({
            date: horizon as string,
            title: "Projection point",
            cardTitle: `${trajectory.trajectory_label || trajectory.label || "Trajectory"} — P(HIGH ${horizon}) ${Math.round((p as number) * 100)}%`,
            cardDetailedText: `Model-projected probability of HIGH threat at ${horizon}. Projection, not observation.`,
          }))
      : undefined
  );

  const allComplete = phaseOrder.every((p) => statuses[p] === "complete");
  const hasProgress = Object.values(statuses).some((s) => s === "complete");

  // Explainability wiring: derive the knowledge graph from reported signals
  // (entity -> action -> target) and surface the verbatim evidence log.
  // Nothing is invented: empty pipeline data renders empty with a notice.
  const graphNodes = (() => {
    const nodes = new Map<string, { id: string; label: string; type: string }>();
    const edges: Array<{ source: string; target: string; label: string }> = [];
    for (const s of result?.raw_sources || []) {
      const entity = String(s?.entity || "").trim();
      const target = String(s?.target || "").trim();
      const action = String(s?.action || "linked").trim();
      if (entity && !nodes.has(entity) && nodes.size < 30) {
        nodes.set(entity, { id: entity, label: entity, type: String(s?.domain || "actor") });
      }
      if (entity && target) {
        if (!nodes.has(target) && nodes.size < 30) {
          nodes.set(target, { id: target, label: target, type: "actor" });
        }
        if (edges.length < 40 && nodes.has(entity) && nodes.has(target)) {
          edges.push({ source: entity, target, label: action.slice(0, 40) });
        }
      }
      if (nodes.size >= 30 && edges.length >= 40) break;
    }
    return { entities: [...nodes.values()], relationships: edges };
  })();

  const evidenceEntries = (result?.evidence_log || []).map((e: any) =>
    typeof e === "string"
      ? { claim: e.slice(0, 240), sources: [] as string[], contradictions: 0 }
      : { claim: String(e?.claim || e?.text || JSON.stringify(e)).slice(0, 240), sources: e?.sources || [], contradictions: e?.contradictions || 0 }
  );

  return (
    <div className="space-y-4">
      {/* Question Header */}
      <div className="glass p-5">
        <p className="text-[11px] text-text-muted uppercase tracking-widest mb-1">Investigation</p>
        <h1 className="text-xl font-bold text-text-primary">
          {result?.query || "Strategic Geopolitical Risk Assessment"}
        </h1>
        <p className="text-xs text-text-muted mt-1 font-mono">
          ID: {Array.isArray(params?.id) ? params?.id[0] : params?.id} | Country: {result?.country || "IND"}
        </p>
      </div>

      {/* Pipeline Tracker */}
      <PipelineTracker
        statuses={statuses}
        expandedPhase={expandedPhase}
        onPhaseClick={(p) => setExpandedPhase(expandedPhase === p ? null : p)}
        phaseDetails={phaseDetails}
      />

      {/* Three-Pane Layout */}
      {hasProgress && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="grid grid-cols-12 gap-4"
          style={{ minHeight: "560px" }}
        >
          {/* LEFT: Knowledge Graph */}
          <div className="col-span-3">
            <LeftPanel
              entities={result?.entities || (graphNodes.entities.length > 0 ? graphNodes.entities : (isDemo ? mockEntities : []))}
              relationships={result?.relationships || (graphNodes.relationships.length > 0 ? graphNodes.relationships : (isDemo ? mockRelationships : []))}
              selectedNode={selectedNode}
              setSelectedNode={setSelectedNode}
              isDemo={isDemo && !result?.entities && graphNodes.entities.length === 0}
            />
          </div>

          {/* CENTER: Report / Ministers / Sources / Notebook */}
          <div className="col-span-6">
            <CenterPanel
              allComplete={allComplete}
              result={result}
              error={error}
              isDemo={isDemo}
            />
          </div>

          {/* RIGHT: Experts, Timeline, Evidence, Confidence */}
          <div className="col-span-3">
            <RightPanel
              mockDebate={isDemo ? mockDebate : []}
              mockEvidence={evidenceEntries.length > 0 ? evidenceEntries : (isDemo ? mockEvidence : [])}
              hypotheses={result?.hypotheses}
              redTeam={result?.red_team_report}
              timeline={timeline}
              metrics={metrics}
              isDemo={isDemo}
            />
          </div>
        </motion.div>
      )}
    </div>
  );
}
