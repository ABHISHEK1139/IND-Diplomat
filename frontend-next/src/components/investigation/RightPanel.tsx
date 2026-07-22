"use client";

import { useState } from "react";
import { MessageSquare, ShieldCheck, Clock, BarChart3, ShieldAlert } from "lucide-react";
import GlassCard from "@/components/ui/GlassCard";
import DebateView from "@/components/investigation/DebateView";
import EvidenceExplorer from "@/components/investigation/EvidenceExplorer";
import TimelineView from "@/components/investigation/TimelineView";
import ConfidencePanel from "@/components/investigation/ConfidencePanel";

interface DebateEntry {
  expert: string;
  text: string;
  color: string;
}

interface EvidenceEntry {
  claim: string;
  sources: string[];
  contradictions: number;
}

interface RightPanelProps {
  mockDebate: DebateEntry[];
  mockEvidence: EvidenceEntry[];
}

type TabType = "experts" | "timeline" | "evidence" | "confidence";

export default function RightPanel({ mockDebate, mockEvidence }: RightPanelProps) {
  const [activeTab, setActiveTab] = useState<TabType>("experts");

  const mockTimeline = [
    {
      date: "2024 Q3",
      title: "Policy Shift",
      cardTitle: "India Semiconductor Mission Expanded",
      cardDetailedText: "Govt announces $10B additional subsidies for trailing-edge fabs.",
    },
    {
      date: "2026 Q1",
      title: "Industry Move",
      cardTitle: "Tata-PSMC Fab Operational",
      cardDetailedText: "First major 28nm fab begins commercial production in Gujarat.",
    },
    {
      date: "2029 Q2",
      title: "AI Pivot",
      cardTitle: "Nvidia-India Strategic Compute Pact",
      cardDetailedText: "India secures sovereign supply of Blackwell GPUs in exchange for data localization waivers.",
    },
    {
      date: "2032 Q4",
      title: "Geopolitical Event",
      cardTitle: "US Export Control Tightening",
      cardDetailedText: "US restricts advanced node design tools; India relies on open-source RISC-V architectures.",
    }
  ];

  return (
    <GlassCard hover={false} className="h-full flex flex-col">
      {/* Tab Bar */}
      <div className="flex items-center justify-between mb-4 border-b border-border pb-3 shrink-0">
        {[
          { key: "experts", icon: MessageSquare, label: "Experts" },
          { key: "timeline", icon: Clock, label: "Timeline" },
          { key: "evidence", icon: ShieldCheck, label: "Evidence" },
          { key: "confidence", icon: BarChart3, label: "Metrics" },
        ].map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key as TabType)}
            className={`flex flex-col items-center gap-1 p-2 rounded-lg text-[10px] font-semibold transition-all ${
              activeTab === tab.key ? "bg-accent/10 text-accent" : "text-text-muted hover:text-text-primary"
            }`}
          >
            <tab.icon className="w-4 h-4" />
            {tab.label}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto pr-1">
        {activeTab === "experts" && (
          <div className="space-y-4">
            <h3 className="text-sm font-semibold text-text-primary">Live Debate</h3>
            <DebateView debate={mockDebate} />
          </div>
        )}

        {activeTab === "evidence" && (
          <div className="space-y-4">
            <h3 className="text-sm font-semibold text-text-primary flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 text-warning" />
              Verified Claims
            </h3>
            <EvidenceExplorer evidence={mockEvidence} />
          </div>
        )}

        {activeTab === "timeline" && (
          <div className="space-y-4">
            <h3 className="text-sm font-semibold text-text-primary">Predicted Timeline</h3>
            <TimelineView events={mockTimeline} />
          </div>
        )}

        {activeTab === "confidence" && (
          <div className="space-y-4">
            <h3 className="text-sm font-semibold text-text-primary">System Confidence</h3>
            <ConfidencePanel 
              metrics={{
                evidence: 92,
                sources: 87,
                expertAgreement: 81,
                forecastReliability: 74,
              }} 
            />
          </div>
        )}
      </div>
    </GlassCard>
  );
}
