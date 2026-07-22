"use client";

import { useState } from "react";
import { FileText, BookOpen } from "lucide-react";
import GlassCard from "@/components/ui/GlassCard";
import Notebook from "@/components/investigation/Notebook";
import ForecastCharts from "@/components/investigation/ForecastCharts";
import RecommendationsView from "@/components/investigation/RecommendationsView";
import { InvestigationResult } from "@/lib/api";

interface CenterPanelProps {
  allComplete: boolean;
  result: InvestigationResult | null;
  error: string | null;
}

export default function CenterPanel({ allComplete, result, error }: CenterPanelProps) {
  const [activeTab, setActiveTab] = useState<"report" | "notebook">("report");

  return (
    <GlassCard hover={false} className="h-full flex flex-col">
      {/* Tab Bar */}
      <div className="flex items-center gap-1 mb-4 border-b border-border pb-3 shrink-0">
        {[
          { key: "report", label: "Dossier", icon: FileText },
          { key: "notebook", label: "Notebook", icon: BookOpen },
        ].map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key as "report" | "notebook")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              activeTab === tab.key ? "bg-accent/10 text-accent" : "text-text-muted hover:text-text-primary"
            }`}
          >
            <tab.icon className="w-3.5 h-3.5" />
            {tab.label}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto pr-2">
        {activeTab === "report" && (
          <div className="space-y-6 pb-6">
            {allComplete ? (
              <>
                {error && (
                  <div className="p-3 mb-4 rounded-xl bg-danger/10 border border-danger/30 text-danger text-sm">
                    {error}
                  </div>
                )}
                
                {/* Overview */}
                <section>
                  <h2 className="text-base font-bold text-text-primary mb-2">Executive Overview</h2>
                  <p className="text-text-muted text-sm leading-relaxed">
                    {result?.dossier || "India's semiconductor ambitions face significant structural challenges, particularly in fabrication capacity. However, the nation's rapidly growing AI talent pool, government incentives under the India Semiconductor Mission, and strategic partnerships with global foundries present viable pathways to partial leadership by 2035."}
                  </p>
                </section>

                {/* Forecast Sub-section */}
                <section>
                  <h3 className="text-sm font-semibold text-text-primary mb-3">Forecast Analysis</h3>
                  <ForecastCharts
                    scenarios={
                      result?.scenarios || [
                        { name: "Most Likely", probability: 62 },
                        { name: "Best Case", probability: 21 },
                        { name: "Worst Case", probability: 17 },
                      ]
                    }
                  />
                </section>

                {/* Recommendations Sub-section */}
                <section>
                  <h3 className="text-sm font-semibold text-text-primary mb-3">Strategic Recommendations</h3>
                  <RecommendationsView 
                    recommendations={result?.recommendations || [
                      { option: "Increase Domestic Fab Investment", impact: "High", confidence: 81 },
                      { option: "Expand GPU Import Agreements", impact: "Medium", confidence: 73 },
                      { option: "AI Talent Export Controls", impact: "Low", confidence: 68 },
                    ]} 
                  />
                </section>
              </>
            ) : (
              <div className="flex flex-col items-center justify-center py-20 text-text-muted h-full">
                <FileText className="w-8 h-8 text-accent/40 mb-3 animate-pulse" />
                <p className="text-sm">Compiling dossier...</p>
              </div>
            )}
          </div>
        )}

        {activeTab === "notebook" && (
          <div className="h-full min-h-[400px]">
            <Notebook initialContent="<h2>Investigation Notes</h2><p>Start your analysis here...</p>" />
          </div>
        )}
      </div>
    </GlassCard>
  );
}
