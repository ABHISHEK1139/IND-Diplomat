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
    const ws = connectPipelineWS(
      (data: any) => {
        if (data.type === "pipeline_update" && data.job_id === idStr) {
          setStatuses((prev) => ({
            ...prev,
            [data.phase]: data.status,
          }));
        } else if (data.type === "pipeline_complete" && data.job_id === idStr) {
          // Fetch final results
          getJobResult(idStr)
            .then(res => setResult(res))
            .catch(err => setError(err.message));
        }
      },
      (err) => {
        console.error("WS error:", err);
        setError("Lost connection to live pipeline");
      }
    );

    return () => ws.close();
  }, [params?.id]);

  const phaseDetails: Record<string, { sources?: number; credibility?: number; entities?: string[] }> = {
    planning: { entities: ["Technology", "Economy", "India", "2035"] },
    collection: { sources: 287, credibility: 91 },
    worldmodel: { entities: ["TSMC", "NVIDIA", "Modi", "Taiwan"] },
    reasoning: { entities: ["Economist", "Military", "Technology", "Climate"] },
  };

  const allComplete = phaseOrder.every((p) => statuses[p] === "complete");
  const hasProgress = Object.values(statuses).some((s) => s === "complete");

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
              entities={result?.entities || mockEntities} 
              relationships={result?.relationships || mockRelationships} 
              selectedNode={selectedNode}
              setSelectedNode={setSelectedNode}
            />
          </div>

          {/* CENTER: Report / Ministers / Sources / Notebook */}
          <div className="col-span-6">
            <CenterPanel 
              allComplete={allComplete}
              result={result}
              error={error}
            />
          </div>

          {/* RIGHT: Experts, Timeline, Evidence, Confidence */}
          <div className="col-span-3">
            <RightPanel 
              mockDebate={mockDebate} 
              mockEvidence={mockEvidence}
              hypotheses={result?.hypotheses}
            />
          </div>
        </motion.div>
      )}
    </div>
  );
}
