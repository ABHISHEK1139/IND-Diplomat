"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { 
  ShieldAlert, 
  Globe, 
  TrendingUp, 
  Target, 
  Landmark, 
  Users, 
  Crosshair, 
  CheckCircle2, 
  AlertCircle, 
  ChevronDown, 
  ChevronUp,
  FileSearch,
  Sparkles
} from "lucide-react";
import { MinisterHypothesis } from "@/lib/api";

interface DebateEntry {
  expert: string;
  text: string;
  color?: string;
}

interface DebateViewProps {
  debate?: DebateEntry[];
  hypotheses?: any[];
  // Demo-only illustrative cards. Real investigations with no hypotheses
  // show an unavailable state instead of fabricated minister assessments.
  isDemo?: boolean;
}

const ministerMeta: Record<string, { icon: any; color: string; bg: string; border: string }> = {
  "Security Minister": { icon: ShieldAlert, color: "text-red-400", bg: "bg-red-500/10", border: "border-red-500/30" },
  "Diplomacy Minister": { icon: Globe, color: "text-cyan-400", bg: "bg-cyan-500/10", border: "border-cyan-500/30" },
  "Economic Minister": { icon: TrendingUp, color: "text-amber-400", bg: "bg-amber-500/10", border: "border-amber-500/30" },
  "Strategy Minister": { icon: Target, color: "text-purple-400", bg: "bg-purple-500/10", border: "border-purple-500/30" },
  "Domestic Minister": { icon: Landmark, color: "text-blue-400", bg: "bg-blue-500/10", border: "border-blue-500/30" },
  "Alliance Minister": { icon: Users, color: "text-emerald-400", bg: "bg-emerald-500/10", border: "border-emerald-500/30" },
  "Contrarian Minister": { icon: Crosshair, color: "text-orange-400", bg: "bg-orange-500/10", border: "border-orange-500/30" },
  "Red Team": { icon: Crosshair, color: "text-orange-400", bg: "bg-orange-500/10", border: "border-orange-500/30" },
};

export default function DebateView({ debate = [], hypotheses = [], isDemo }: DebateViewProps) {
  const [expandedIndex, setExpandedIndex] = useState<number | null>(0);
  const demo = isDemo === true;

  // Normalize hypotheses if present. The illustrative fallback cards below
  // are demo-preview data only — never fabricate minister assessments.
  const demoCards = [
    {
      minister: "Security Minister",
      type: "Is this a genuine military threat?",
      confidence: 0.78,
      matched_signals: ["Forward mechanized brigade positioning", "Air defense radar activation in sector"],
      missing_signals: ["Logistics fuel depot surge"],
      rationale: "Kinetic posture verified with 0.85 intensity and high source reliability. Direct readiness escalation observed.",
    },
    {
      minister: "Diplomacy Minister",
      type: "Is this diplomatic signaling / posturing?",
      confidence: 0.65,
      matched_signals: ["Formal diplomatic démarche issued", "Bilateral disengagement talks stalled"],
      missing_signals: ["Expulsion of diplomatic mission"],
      rationale: "Diplomatic channel friction elevated to 0.62 index. Bilateral protocol strain verified under UN Charter mechanisms.",
    },
    {
      minister: "Economic Minister",
      type: "What are the sanction & supply chain risks?",
      confidence: 0.60,
      matched_signals: ["Bilateral import inspection delays", "Critical mineral export restrictions"],
      missing_signals: ["Full maritime shipping embargo"],
      rationale: "Economic friction measured at 0.50 with targeted supply chain rerouting underway.",
    },
    {
      minister: "Strategy Minister",
      type: "Is this a long-term strategic doctrine shift?",
      confidence: 0.72,
      matched_signals: ["Multi-year infrastructure buildup along border", "Joint theater command reorganization"],
      missing_signals: [],
      rationale: "Structural doctrine shift indicates persistent forward presence rather than temporary exercise.",
    },
    {
      minister: "Contrarian Minister",
      type: "What are the alternative explanations & noise?",
      confidence: 0.45,
      matched_signals: ["Routine seasonal rotation schedule"],
      missing_signals: ["Unannounced rapid mobilization"],
      rationale: "Red Team analysis verified baseline noise, but core escalation indicators outweigh routine rotation hypotheses.",
    },
  ];
  const ministerCards = hypotheses.length > 0 ? hypotheses : (demo ? demoCards : []);

  if (ministerCards.length === 0) {
    return (
      <p className="text-xs text-text-muted">No minister deliberation reported for this investigation.</p>
    );
  }

  return (
    <div className="space-y-3 overflow-y-auto max-h-[540px] pr-1">
      {demo && hypotheses.length === 0 && (
        <p className="text-[10px] font-semibold text-warning uppercase tracking-wider">Demo preview — not a real deliberation</p>
      )}
      {debate.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-[11px] font-bold uppercase tracking-wider text-text-muted">Expert commentary</h4>
          {debate.map((entry, i) => (
            <blockquote key={i} className="p-2.5 rounded-lg bg-background/60 border border-border/50 space-y-1">
              <span className={`text-[11px] font-bold ${entry.color || "text-accent"}`}>{entry.expert}</span>
              <p className="text-xs text-text-muted leading-relaxed">{entry.text}</p>
            </blockquote>
          ))}
        </div>
      )}
      {/* 7-Minister Cards with Explainable Points */}
      {ministerCards.map((item: any, i: number) => {
        const ministerName = item.minister || item.expert || `Minister ${i + 1}`;
        const meta = ministerMeta[ministerName] || {
          icon: Users,
          color: "text-accent",
          bg: "bg-accent/10",
          border: "border-border",
        };
        const Icon = meta.icon;
        const conf = typeof item.confidence === "number" ? Math.round(item.confidence * 100) : null;
        const isExpanded = expandedIndex === i;

        return (
          <motion.div
            key={i}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.05 }}
            className={`rounded-xl border ${meta.border} ${meta.bg} p-3.5 transition-all shadow-sm`}
          >
            {/* Header: Minister, Title, Confidence Badge */}
            <div 
              className="flex items-start justify-between cursor-pointer"
              onClick={() => setExpandedIndex(isExpanded ? null : i)}
            >
              <div className="flex items-center gap-2.5">
                <div className={`w-8 h-8 rounded-lg ${meta.bg} flex items-center justify-center border ${meta.border}`}>
                  <Icon className={`w-4 h-4 ${meta.color}`} />
                </div>
                <div>
                  <h4 className={`text-xs font-bold ${meta.color}`}>{ministerName}</h4>
                  <p className="text-[11px] text-text-muted line-clamp-1">{item.type || item.text || "Domain Hypothesis Assessment"}</p>
                </div>
              </div>

              <div className="flex items-center gap-2">
                {item.decision_mode && (
                  <span
                    title={
                      item.llm_confidence != null
                        ? `Heuristic ${Math.round((item.heuristic_confidence ?? 0) * 100)}% vs LLM ${Math.round(item.llm_confidence * 100)}% (agreement ${item.agreement_score ?? "n/a"})`
                        : "Produced without LLM refinement"
                    }
                    className={`text-[10px] font-mono px-2 py-0.5 rounded-full border ${
                      item.decision_mode === "heuristic_only"
                        ? "bg-background text-text-muted border-border"
                        : item.decision_mode === "bounded_llm_refinement"
                          ? "bg-amber-500/10 text-amber-300 border-amber-500/30"
                          : "bg-cyan-500/10 text-cyan-300 border-cyan-500/30"
                    }`}
                  >
                    {item.decision_mode === "heuristic_only" ? "heuristic" : item.decision_mode === "bounded_llm_refinement" ? "LLM·bounded" : "LLM·refined"}
                  </span>
                )}
                <span className={`text-[11px] font-mono font-bold px-2.5 py-0.5 rounded-full border ${
                  conf == null ? "bg-background text-text-muted border-border" :
                  conf >= 70 ? "bg-red-500/20 text-red-400 border-red-500/40" :
                  conf >= 50 ? "bg-amber-500/20 text-amber-400 border-amber-500/40" :
                  "bg-emerald-500/20 text-emerald-400 border-emerald-500/40"
                }`}>
                  {conf == null ? "n/a" : `${conf}% Conf`}
                </span>
                {isExpanded ? (
                  <ChevronUp className="w-4 h-4 text-text-muted" />
                ) : (
                  <ChevronDown className="w-4 h-4 text-text-muted" />
                )}
              </div>
            </div>

            {/* Expanded Explainability Details */}
            <AnimatePresence>
              {isExpanded && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  className="mt-3 pt-3 border-t border-border/50 space-y-3"
                >
                  {/* Why this point was given (Rationale) */}
                  <div>
                    <div className="flex items-center gap-1.5 text-[11px] font-semibold text-text-primary mb-1">
                      <Sparkles className="w-3.5 h-3.5 text-accent" />
                      <span>Why This Score Was Assigned:</span>
                    </div>
                    <p className="text-xs text-text-muted bg-background/60 p-2.5 rounded-lg border border-border/40 leading-relaxed">
                      {item.rationale || item.text || "Confidence score calibrated from corroborated intelligence signals and multi-source credibility weighting."}
                    </p>
                  </div>

                  {/* Signals & Intelligence Accessed */}
                  {item.matched_signals && item.matched_signals.length > 0 && (
                    <div>
                      <div className="flex items-center gap-1.5 text-[11px] font-semibold text-emerald-400 mb-1.5">
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        <span>Signals & Evidence Accessed ({item.matched_signals.length}):</span>
                      </div>
                      <div className="space-y-1">
                        {item.matched_signals.map((sig: string, sIdx: number) => (
                          <div 
                            key={sIdx} 
                            className="flex items-center gap-2 text-[11px] text-text-primary bg-emerald-500/10 border border-emerald-500/20 px-2.5 py-1 rounded-md"
                          >
                            <FileSearch className="w-3 h-3 text-emerald-400 shrink-0" />
                            <span className="truncate">{sig}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Missing Signals & Gaps */}
                  {item.missing_signals && item.missing_signals.length > 0 && (
                    <div>
                      <div className="flex items-center gap-1.5 text-[11px] font-semibold text-amber-400 mb-1">
                        <AlertCircle className="w-3.5 h-3.5" />
                        <span>Unobserved Indicators / Gaps:</span>
                      </div>
                      <div className="flex flex-wrap gap-1.5">
                        {item.missing_signals.map((gap: string, gIdx: number) => (
                          <span 
                            key={gIdx} 
                            className="text-[10px] text-amber-300 bg-amber-500/10 border border-amber-500/20 px-2 py-0.5 rounded"
                          >
                            {gap}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        );
      })}
    </div>
  );
}

