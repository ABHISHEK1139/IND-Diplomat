"use client";

import { motion } from "framer-motion";
import {
  CheckCircle2,
  Loader2,
  Clock,
  Search,
  Brain,
  Globe,
  MessageSquare,
  TrendingUp,
  FileText,
  GraduationCap,
} from "lucide-react";

const phases = [
  { key: "planning",   label: "Planner",     icon: Search },
  { key: "collection", label: "Collection",  icon: Globe },
  { key: "worldmodel", label: "World Model", icon: Brain },
  { key: "reasoning",  label: "Reasoning",   icon: MessageSquare },
  { key: "forecasting",label: "Forecast",    icon: TrendingUp },
  { key: "workspace",  label: "Report",      icon: FileText },
  { key: "learning",   label: "Learning",    icon: GraduationCap },
];

type PhaseStatus = "waiting" | "running" | "complete" | "error";

interface PipelineTrackerProps {
  statuses: Record<string, PhaseStatus>;
  expandedPhase?: string | null;
  onPhaseClick?: (phase: string) => void;
  phaseDetails?: Record<string, { sources?: number; credibility?: number; entities?: string[] }>;
}

export default function PipelineTracker({ statuses, expandedPhase, onPhaseClick, phaseDetails }: PipelineTrackerProps) {
  return (
    <div className="glass p-4">
      <div className="flex items-center gap-1 overflow-x-auto">
        {phases.map((phase, i) => {
          const status = statuses[phase.key] || "waiting";
          const Icon = phase.icon;

          return (
            <div key={phase.key} className="flex items-center">
              {/* Phase Step */}
              <motion.button
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                onClick={() => onPhaseClick?.(phase.key)}
                className={`flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-semibold transition-all ${
                  status === "complete"
                    ? "bg-success/10 text-success"
                    : status === "running"
                    ? "bg-accent/10 text-accent animate-pulse-glow"
                    : status === "error"
                    ? "bg-danger/10 text-danger"
                    : "bg-surface text-text-muted"
                }`}
              >
                {status === "complete" ? (
                  <CheckCircle2 className="w-4 h-4" />
                ) : status === "running" ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Clock className="w-4 h-4 opacity-40" />
                )}
                <Icon className="w-3.5 h-3.5" />
                <span>{phase.label}</span>
              </motion.button>

              {/* Connector Line */}
              {i < phases.length - 1 && (
                <div className={`w-6 h-[2px] mx-1 rounded-full transition-colors ${
                  status === "complete" ? "bg-success/40" : "bg-border"
                }`} />
              )}
            </div>
          );
        })}
      </div>

      {/* Expanded Phase Detail */}
      {expandedPhase && phaseDetails?.[expandedPhase] && (
        <motion.div
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: "auto", opacity: 1 }}
          exit={{ height: 0, opacity: 0 }}
          className="mt-3 pt-3 border-t border-border"
        >
          <div className="flex flex-wrap gap-4 text-sm">
            {phaseDetails[expandedPhase].sources !== undefined && (
              <div>
                <span className="text-text-muted">Sources: </span>
                <span className="font-bold text-accent">{phaseDetails[expandedPhase].sources}</span>
              </div>
            )}
            {phaseDetails[expandedPhase].credibility !== undefined && (
              <div>
                <span className="text-text-muted">Credibility: </span>
                <span className="font-bold text-success">{phaseDetails[expandedPhase].credibility}%</span>
              </div>
            )}
            {phaseDetails[expandedPhase].entities && (
              <div className="flex items-center gap-2">
                <span className="text-text-muted">Detected: </span>
                {phaseDetails[expandedPhase].entities!.map((e) => (
                  <span key={e} className="px-2 py-0.5 rounded-full bg-accent/10 text-accent text-xs font-medium">{e}</span>
                ))}
              </div>
            )}
          </div>
        </motion.div>
      )}
    </div>
  );
}
