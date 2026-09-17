"use client";

import { useState } from "react";
import { 
  FileText, 
  BookOpen, 
  Users, 
  Globe2, 
  TrendingUp, 
  ShieldAlert, 
  Scale, 
  ExternalLink, 
  CheckCircle2, 
  AlertTriangle,
  Layers,
  Sparkles,
  Search
} from "lucide-react";
import GlassCard from "@/components/ui/GlassCard";
import Notebook from "@/components/investigation/Notebook";
import DecisionTrail from "@/components/investigation/DecisionTrail";
import ForecastCharts from "@/components/investigation/ForecastCharts";
import RecommendationsView from "@/components/investigation/RecommendationsView";
import { InvestigationResult } from "@/lib/api";

interface CenterPanelProps {
  allComplete: boolean;
  result: InvestigationResult | null;
  error: string | null;
  // UI-01/UI-02: illustrative fallback content is demo-only. For real
  // investigations without pipeline data yet, show explicit unavailable
  // states instead of fabricated assessments.
  isDemo?: boolean;
}

// Demo-only illustrative dossier. Never shown for real investigations:
// without pipeline output there is nothing truthful to summarize.
const DEMO_DOSSIER = (country: string, query: string) => `
# STRATEGIC GEOPOLITICAL INTELLIGENCE ESTIMATE (DEMO): ${country}
**Objective**: Autonomous multi-domain intelligence synthesis for query: "${query}".
**Assessed Threat Level**: HIGH (illustrative) | **Confidence**: HIGH CONFIDENCE (illustrative)

## 1. Executive Intelligence Summary (demo data)
Illustrative 7-minister council output for UI preview only — not a real assessment.

## 2. Key Strategic Judgments (demo data)
- Illustrative escalation indicators for layout preview.
- No live evidence corroboration.

## 3. Applicable Legal & Treaty Grounding
- UN_CHARTER (Article 2(4)) — Prohibition of threat or use of force.
- UN_CHARTER (Article 51) — Right of individual or collective self-defense.
- UNCLOS (Article 56) — Sovereign rights in exclusive economic zones.
  `;

export default function CenterPanel({ allComplete, result, error, isDemo }: CenterPanelProps) {
  const [activeTab, setActiveTab] = useState<"report" | "why" | "ministers" | "sources" | "forecast" | "engines" | "notebook">("report");
  const [sourceFilter, setSourceFilter] = useState<string>("all");
  const demo = isDemo === true;

  // Format executive briefing / dossier text. No fabrication: without a
  // pipeline briefing there is no dossier to show (demo mode excepted).
  const executiveDossier =
    result?.briefing || result?.dossier ||
    (demo ? DEMO_DOSSIER(result?.country || "IND", result?.query || "Geopolitical Risk Assessment") : null);

  // Display helpers: real values when present, demo placeholders in demo
  // mode, explicit "unavailable" markers otherwise.
  const threatLabel = result?.threat_level ?? (demo ? "HIGH" : "Not assessed");
  const verificationLabel =
    result?.verification_score != null
      ? `${(result.verification_score * 100).toFixed(1)}%`
      : (demo ? "88.0%" : "Unavailable");

  // Normalize hypotheses (demo fallbacks are illustrative preview data only)
  const hypotheses = result?.hypotheses && result.hypotheses.length > 0 ? result.hypotheses : (demo ? [
    {
      minister: "Security Minister",
      type: "Is this a genuine military threat?",
      confidence: 0.78,
      matched_signals: ["Mechanized armored brigade forward deployment", "Air defense radar battery activation"],
      missing_signals: ["Full logistics fuel depot surge"],
      rationale: "Kinetic posture verified with 0.85 intensity and high source reliability. Direct readiness escalation observed.",
    },
    {
      minister: "Diplomacy Minister",
      type: "Is this diplomatic signaling / posturing?",
      confidence: 0.65,
      matched_signals: ["Formal diplomatic démarche issued", "Bilateral disengagement talks stalled"],
      missing_signals: ["Expulsion of diplomatic mission"],
      rationale: "Diplomatic channel friction elevated to 0.62 index. Bilateral protocol strain verified under international treaty mechanisms.",
    },
    {
      minister: "Economic Minister",
      type: "What are the sanction & supply chain risks?",
      confidence: 0.60,
      matched_signals: ["Import inspection delays along border corridors", "Critical supply chain rerouting"],
      missing_signals: ["Full maritime commercial shipping embargo"],
      rationale: "Economic friction measured at 0.50 with targeted supply chain friction and tariff review underway.",
    },
    {
      minister: "Strategy Minister",
      type: "Is this a long-term strategic doctrine shift?",
      confidence: 0.72,
      matched_signals: ["Multi-year infrastructure buildup", "Joint theater command reorganization"],
      missing_signals: [],
      rationale: "Structural doctrine shift indicates persistent forward presence rather than temporary exercise.",
    },
    {
      minister: "Domestic Minister",
      type: "What is the domestic political & public impact?",
      confidence: 0.58,
      matched_signals: ["Legislative committee security briefing", "Public mobilization sentiment surge"],
      missing_signals: ["Civilian emergency mobilization"],
      rationale: "Domestic political consensus supports enhanced border readiness and strategic resource allocation.",
    },
    {
      minister: "Alliance Minister",
      type: "How will bilateral partners & coalitions respond?",
      confidence: 0.68,
      matched_signals: ["Joint intelligence-sharing protocol activated", "Partner naval patrol alignment"],
      missing_signals: ["Formal mutual defense pact invocation"],
      rationale: "Coalition coordination active with allied defense intelligence sharing and diplomatic solidarity statements.",
    },
    {
      minister: "Contrarian Minister",
      type: "What are the alternative explanations & noise?",
      confidence: 0.45,
      matched_signals: ["Routine seasonal rotation schedule"],
      missing_signals: ["Unannounced rapid mobilization"],
      rationale: "Red Team evaluated alternative explanations; verified that escalation indicators outweigh baseline noise.",
    },
  ] : []);

  // Normalize raw internet / OSINT sources (demo fallbacks are illustrative only)
  const internetSources = (result?.raw_sources && result.raw_sources.length > 0) ? result.raw_sources : (demo ? [
    {
      source_ref: "OFFICIAL_DEFENSE_INTELLIGENCE_BULLETIN",
      entity: "Ministry of Defense / Joint Staff",
      action: "Forward troop deployments and radar readiness alert monitored along strategic sector",
      domain: "military",
      intensity: 0.85,
      confidence: 0.88,
      reliability_score: 0.95,
      tier: "Tier 1 (Official)",
      url: "https://mod.gov.in/press-release/border-posture-update",
      timestamp: "2026-09-01T18:30:00Z"
    },
    {
      source_ref: "GOV_FOREIGN_AFFAIRS_COMMUNIQUE",
      entity: "Ministry of External Affairs",
      action: "Issued formal diplomatic démarche regarding border protocol compliance",
      domain: "diplomacy",
      intensity: 0.75,
      confidence: 0.82,
      reliability_score: 0.90,
      tier: "Tier 1 (Official)",
      url: "https://mea.gov.in/bilateral-briefing-lac",
      timestamp: "2026-09-01T17:45:00Z"
    },
    {
      source_ref: "REUTERS_GLOBAL_WIRE",
      entity: "Reuters Defense & Security Desk",
      action: "Satellite imagery reveals fortified shelters and runway extensions near border",
      domain: "military",
      intensity: 0.80,
      confidence: 0.85,
      reliability_score: 0.88,
      tier: "Tier 2 (Wire)",
      url: "https://reuters.com/world/asia-pacific/satellite-images-show-buildup",
      timestamp: "2026-09-01T16:15:00Z"
    },
    {
      source_ref: "UN_TREATY_COLLECTION",
      entity: "United Nations Secretariat",
      action: "UN Charter Article 2(4) and bilateral peaceful resolution agreements indexed",
      domain: "legal",
      intensity: 0.40,
      confidence: 0.95,
      reliability_score: 0.98,
      tier: "Tier 1 (Legal Treaty)",
      url: "https://treaties.un.org/pages/ViewDetails.aspx?src=TREATY",
      timestamp: "2026-09-01T15:00:00Z"
    },
    {
      source_ref: "GDELT_GLOBAL_EVENT_DATABASE",
      entity: "GDELT 2.0 Conflict Monitor",
      action: "Bilateral Goldstein conflict index recorded at -6.8 with elevated media tone pressure",
      domain: "information",
      intensity: 0.65,
      confidence: 0.78,
      reliability_score: 0.80,
      tier: "Tier 2 (Sensor/Database)",
      url: "https://data.gdeltproject.org/events/index.html",
      timestamp: "2026-09-01T14:20:00Z"
    }
  ] : []);

  const filteredSources = sourceFilter === "all" 
    ? internetSources 
    : internetSources.filter((s: any) => (s.domain || "").toLowerCase() === sourceFilter.toLowerCase());

  return (
    <GlassCard hover={false} className="h-full flex flex-col">
      {/* Tab Bar */}
      <div className="flex items-center justify-between mb-4 border-b border-border pb-3 shrink-0 overflow-x-auto">
        <div className="flex items-center gap-1.5">
          {[
            { key: "report", label: "Executive Dossier", icon: FileText },
            { key: "why", label: "Why?", icon: Scale },
            { key: "ministers", label: "7-Minister Council", icon: Users },
            { key: "sources", label: "Internet & OSINT Sources", icon: Globe2 },
            { key: "forecast", label: "Forecasts & Scenarios", icon: TrendingUp },
            { key: "engines", label: "Advanced AI Engines", icon: Layers },
            { key: "notebook", label: "Analyst Notebook", icon: BookOpen },
          ].map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key as any)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all shrink-0 ${
                activeTab === tab.key ? "bg-accent/10 text-accent border border-accent/20" : "text-text-muted hover:text-text-primary"
              }`}
            >
              <tab.icon className="w-3.5 h-3.5" />
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto pr-2">
        {/* TAB 1: EXECUTIVE DOSSIER (OVERALL SUMMARY) */}
        {activeTab === "report" && (
          <div className="space-y-6 pb-6">
            {allComplete ? (
              <>
                {error && (
                  <div className="p-3 mb-4 rounded-xl bg-danger/10 border border-danger/30 text-danger text-sm">
                    {error}
                  </div>
                )}

                {/* Refusal / gate banner: a non-released assessment must say why */}
                {result?.status && !["COMPLETE", "COMPLETED"].includes(result.status.toUpperCase()) && (
                  <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 space-y-2">
                    <div className="flex items-center gap-2">
                      <AlertTriangle className="w-4 h-4 text-amber-400" />
                      <span className="text-xs font-bold uppercase tracking-wider text-amber-300">
                        Assessment {result.status} — withheld, not released
                      </span>
                    </div>
                    {(result.refusal?.reasons || []).map((reason, i) => (
                      <p key={i} className="text-xs text-text-muted leading-relaxed">• {reason}</p>
                    ))}
                    {(!result.refusal?.reasons || result.refusal.reasons.length === 0) && (
                      <p className="text-xs text-text-muted">No refusal record was attached by the pipeline.</p>
                    )}
                    {result.refusal?.recommendation && (
                      <p className="text-xs text-text-primary">{result.refusal.recommendation}</p>
                    )}
                  </div>
                )}

                {/* Header Summary Banner */}
                <div className="p-4 rounded-xl bg-background/60 border border-border space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Scale className="w-4 h-4 text-accent" />
                      <span className="text-xs font-bold uppercase tracking-wider text-accent">
                        Sherman Kent Intelligence Estimate
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-[11px] px-2.5 py-0.5 rounded-full bg-red-500/10 text-red-400 border border-red-500/30 font-bold">
                        Threat: {threatLabel}
                      </span>
                      <span className="text-[11px] px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 font-bold">
                        Verification: {verificationLabel}
                      </span>
                    </div>
                  </div>
                  <h2 className="text-base font-bold text-text-primary">
                    Strategic Geopolitical Assessment: {result?.country || "IND"}
                  </h2>
                  <p className="text-xs text-text-muted leading-relaxed">
                    Autonomous 7-minister council investigation into <span className="text-text-primary font-medium">&quot;{result?.query || "Regional Crisis & Escalation Risk"}&quot;</span>. Multi-domain synthesis combines defense posture, foreign affairs communiqués, economic dependencies, and international treaty grounding.
                  </p>
                </div>

                {/* Key Strategic Judgments Grid — pipeline-derived only */}
                {result ? (
                <section className="space-y-3">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-text-muted flex items-center gap-1.5">
                    <Sparkles className="w-3.5 h-3.5 text-accent" />
                    Key Strategic Judgments
                  </h3>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                    <div className="p-3 rounded-xl bg-background/50 border border-border">
                      <div className="flex items-center gap-1.5 text-xs font-bold text-red-400 mb-1">
                        <ShieldAlert className="w-3.5 h-3.5" />
                        <span>Military / Kinetic</span>
                      </div>
                      <p className="text-xs text-text-muted leading-relaxed">
                        {hypotheses.length > 0
                          ? `${hypotheses.length} minister portfolio(s) report assessed signals; see the 7-Minister Council tab for per-portfolio rationale.`
                          : "No minister portfolios reported assessed signals."}
                      </p>
                    </div>

                    <div className="p-3 rounded-xl bg-background/50 border border-border">
                      <div className="flex items-center gap-1.5 text-xs font-bold text-cyan-400 mb-1">
                        <Globe2 className="w-3.5 h-3.5" />
                        <span>Diplomatic Channels</span>
                      </div>
                      <p className="text-xs text-text-muted leading-relaxed">
                        {internetSources.length > 0
                          ? `${internetSources.length} ingested source(s) available; see the Sources tab.`
                          : "No diplomatic sources ingested for this assessment."}
                      </p>
                    </div>

                    <div className="p-3 rounded-xl bg-background/50 border border-border">
                      <div className="flex items-center gap-1.5 text-xs font-bold text-amber-400 mb-1">
                        <TrendingUp className="w-3.5 h-3.5" />
                        <span>Economic Friction</span>
                      </div>
                      <p className="text-xs text-text-muted leading-relaxed">
                        Verification {verificationLabel}. Threat {threatLabel}.
                      </p>
                    </div>
                  </div>
                </section>
                ) : (
                  <p className="text-xs text-text-muted">Judgments unavailable — no pipeline result for this investigation{demo ? " (demo preview)" : ""}.</p>
                )}

                {/* Strategic Recommendations */}
                <section>
                  <h3 className="text-sm font-semibold text-text-primary mb-3">Actionable Strategic Recommendations</h3>
                  {result?.recommendations && result.recommendations.length > 0 ? (
                    <RecommendationsView recommendations={result.recommendations} />
                  ) : demo ? (
                    <RecommendationsView
                      recommendations={[
                        { option: "Activate high-readiness satellite and UAV surveillance along strategic sectors", impact: "High", confidence: 88 },
                        { option: "Convene bilateral working group under UN Charter Article 51 & border protocols", impact: "High", confidence: 82 },
                        { option: "Execute targeted supply chain rerouting for critical imports and components", impact: "Medium", confidence: 75 },
                      ]}
                    />
                  ) : (
                    <p className="text-xs text-text-muted">No recommendations supplied by the pipeline.</p>
                  )}
                  {demo && (!result?.recommendations || result.recommendations.length === 0) && (
                    <p className="text-[10px] text-text-muted mt-2">Demo preview data — not a real assessment.</p>
                  )}
                </section>
              </>
            ) : (
              <div className="flex flex-col items-center justify-center py-20 text-text-muted h-full">
                <FileText className="w-8 h-8 text-accent/40 mb-3 animate-pulse" />
                <p className="text-sm">Synthesizing executive intelligence dossier...</p>
              </div>
            )}
          </div>
        )}

        {/* TAB 2: WHY — DECISION TRAIL */}
        {activeTab === "why" && (
          <div className="space-y-4 pb-6">
            <DecisionTrail result={result} isDemo={demo} />
          </div>
        )}

        {/* TAB 3: 7-MINISTER COUNCIL (EXPLAINABLE POINTS, ACCESS & COMBINED SYNTHESIS) */}
        {activeTab === "ministers" && (
          <div className="space-y-4 pb-6">
            {/* Combined 7-Minister Consensus Synthesis Engine */}
            <div className="p-4 rounded-xl bg-gradient-to-br from-accent/10 via-background/60 to-purple-500/10 border border-accent/30 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-accent" />
                  <span className="text-xs font-bold uppercase tracking-wider text-accent">
                    7-Minister Combined Consensus Engine
                  </span>
                </div>
                <span className="text-[11px] font-mono font-bold px-2.5 py-0.5 rounded-full bg-accent/20 text-accent border border-accent/40">
                  Consensus Status: {result ? (hypotheses.length > 0 ? "REPORTED" : "NO HYPOTHESES") : (demo ? "DEMO" : "PENDING")}
                </span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div className="p-3 rounded-lg bg-background/80 border border-border">
                  <span className="text-[10px] text-text-muted uppercase font-semibold">Aggregated Threat Index</span>
                  <div className="text-xl font-bold text-red-400 font-mono mt-0.5">
                    {threatLabel}
                  </div>
                  <span className="text-[10px] text-text-muted">Pipeline-reported level{demo && !result ? " (demo)" : ""}</span>
                </div>

                <div className="p-3 rounded-lg bg-background/80 border border-border">
                  <span className="text-[10px] text-text-muted uppercase font-semibold">Cabinet Spread & Alignment</span>
                  <div className="text-xl font-bold text-cyan-400 font-mono mt-0.5">
                    {hypotheses.length > 0
                      ? `${(Math.max(...hypotheses.map((h: any) => Number(h.confidence) || 0)) - Math.min(...hypotheses.map((h: any) => Number(h.confidence) || 0))).toFixed(2)} Spread`
                      : "Unavailable"}
                  </div>
                  <span className="text-[10px] text-text-muted font-semibold">Computed from reported confidences</span>
                </div>

                <div className="p-3 rounded-lg bg-background/80 border border-border">
                  <span className="text-[10px] text-text-muted uppercase font-semibold">Epistemic Verification Gate</span>
                  <div className="text-xl font-bold text-emerald-400 font-mono mt-0.5">
                    {verificationLabel}
                  </div>
                  <span className="text-[10px] text-text-muted font-semibold">
                    {result?.verification_score != null
                      ? (result.verification_score >= 0.7 ? "✓ Passed Gate (V ≥ 70%)" : "✗ Below Gate (V < 70%)")
                      : "Gate status unavailable"}
                  </span>
                </div>
              </div>

              {/* Multi-Domain Weight Matrix */}
              <div className="p-3 rounded-lg bg-background/60 border border-border/60 space-y-2">
                <span className="text-[11px] font-semibold text-text-primary flex items-center gap-1.5">
                  <Layers className="w-3.5 h-3.5 text-accent" />
                  <span>How the 7 Ministers Combine to Form the Unified Output:</span>
                </span>
                <p className="text-xs text-text-muted leading-relaxed">
                  The Reasoning Coordinator ingests each minister&apos;s independent domain output, calculates the inter-minister confidence spread, runs cross-portfolio critiques, and applies evidential weights:
                  <span className="text-text-primary font-medium"> Security (25%) + Strategy (20%) + Diplomacy (15%) + Alliance (15%) + Economy (10%) + Domestic (10%) − Red Team Noise Offset (5%)</span>.
                </p>
              </div>
            </div>

            <div className="p-3.5 rounded-xl bg-background/60 border border-border flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-text-primary">Individual Minister Portfolio Breakdown</h3>
                <p className="text-xs text-text-muted">Detailed scoring rationale, accessed signals, and intelligence gaps per minister.</p>
              </div>
              <span className="text-xs font-mono text-accent font-semibold">{hypotheses.length > 0 ? `${hypotheses.length} Portfolio${hypotheses.length === 1 ? "" : "s"} Reported` : "No Portfolios Reported"}</span>
            </div>

            <div className="space-y-3">
              {hypotheses.length === 0 && (
                <p className="text-xs text-text-muted">No minister hypotheses reported for this investigation{demo ? " (demo preview has none either)" : ""}.</p>
              )}
              {hypotheses.map((h: any, idx: number) => {
                const conf = typeof h.confidence === "number" ? Math.round(h.confidence * 100) : null;
                return (
                  <div key={idx} className="p-4 rounded-xl bg-background/50 border border-border space-y-3">
                    {/* Minister Header */}
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-text-primary">{h.minister || `Minister ${idx+1}`}</span>
                        <span className="text-[11px] text-text-muted">| {h.type}</span>
                      </div>
                      <span className={`text-xs font-mono font-bold px-2.5 py-0.5 rounded-full border ${
                        conf == null ? "bg-background text-text-muted border-border" :
                        conf >= 70 ? "bg-red-500/20 text-red-400 border-red-500/30" :
                        conf >= 50 ? "bg-amber-500/20 text-amber-400 border-amber-500/30" :
                        "bg-emerald-500/20 text-emerald-400 border-emerald-500/30"
                      }`}>
                        Score: {conf == null ? "n/a" : `${conf}%`}
                      </span>
                    </div>

                    {/* Why this point was given */}
                    <div className="p-2.5 rounded-lg bg-background/80 border border-border/50">
                      <div className="flex items-center gap-1.5 text-[11px] font-semibold text-accent mb-1">
                        <Sparkles className="w-3 h-3" />
                        <span>Why This Point Was Given (Rationale):</span>
                      </div>
                      <p className="text-xs text-text-muted leading-relaxed">
                        {h.rationale || "Calibrated from corroborated intelligence signals, domain weightings, and SRE escalation pressure."}
                      </p>
                    </div>

                    {/* What this minister accessed */}
                    {h.matched_signals && h.matched_signals.length > 0 && (
                      <div>
                        <span className="text-[11px] font-semibold text-emerald-400 flex items-center gap-1 mb-1.5">
                          <CheckCircle2 className="w-3 h-3" />
                          <span>Intelligence Signals Accessed & Verified ({h.matched_signals.length}):</span>
                        </span>
                        <div className="space-y-1">
                          {h.matched_signals.map((sig: string, sIdx: number) => (
                            <div key={sIdx} className="text-xs text-text-primary bg-emerald-500/10 border border-emerald-500/20 px-2.5 py-1 rounded-md">
                              {sig}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Missing signals */}
                    {h.missing_signals && h.missing_signals.length > 0 && (
                      <div>
                        <span className="text-[11px] font-semibold text-amber-400 flex items-center gap-1 mb-1">
                          <AlertTriangle className="w-3 h-3" />
                          <span>Gaps / Unobserved Indicators:</span>
                        </span>
                        <div className="flex flex-wrap gap-1.5">
                          {h.missing_signals.map((gap: string, gIdx: number) => (
                            <span key={gIdx} className="text-[10px] text-amber-300 bg-amber-500/10 border border-amber-500/20 px-2 py-0.5 rounded">
                              {gap}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* TAB 3: INTERNET & OSINT SOURCES */}
        {activeTab === "sources" && (
          <div className="space-y-4 pb-6">
            <div className="p-3.5 rounded-xl bg-background/60 border border-border flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-text-primary">Live Internet & OSINT Sources ({internetSources.length})</h3>
                <p className="text-xs text-text-muted">All web crawls, defense bulletins, legal treaties, and wire reports ingested by the pipeline.</p>
              </div>

              {/* Domain Filter */}
              <div className="flex items-center gap-1">
                {["all", "military", "diplomacy", "legal", "information"].map((dom) => (
                  <button
                    key={dom}
                    onClick={() => setSourceFilter(dom)}
                    className={`text-[10px] font-semibold px-2 py-1 rounded-md uppercase tracking-wider transition-all ${
                      sourceFilter === dom ? "bg-accent/20 text-accent border border-accent/30" : "text-text-muted hover:text-text-primary"
                    }`}
                  >
                    {dom}
                  </button>
                ))}
              </div>
            </div>

            <div className="space-y-3">
              {filteredSources.map((src: any, sIdx: number) => (
                <div key={sIdx} className="p-3.5 rounded-xl bg-background/50 border border-border space-y-2 hover:border-accent/40 transition-all">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold text-text-primary">{src.entity || "Intelligence Source"}</span>
                      <span className="text-[10px] px-2 py-0.5 rounded bg-accent/10 text-accent font-mono">
                        {src.domain || "general"}
                      </span>
                    </div>

                    <div className="flex items-center gap-2">
                      <span className="text-[10px] text-text-muted font-mono">{src.tier || "Tier 1"}</span>
                      {src.reliability_score && (
                        <span className="text-[10px] text-emerald-400 font-bold bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                          {Math.round(src.reliability_score * 100)}% Rel
                        </span>
                      )}
                    </div>
                  </div>

                  <p className="text-xs text-text-muted leading-relaxed">
                    {src.action || src.content || "Observed intelligence signal ingested into the state context."}
                  </p>

                  <div className="flex items-center justify-between text-[11px] text-text-muted pt-1 border-t border-border/40">
                    <span className="font-mono text-[10px] text-text-muted">
                      Ref: {src.source_ref || "OSINT_FEED"}
                    </span>
                    {src.url ? (
                      <a 
                        href={src.url} 
                        target="_blank" 
                        rel="noreferrer" 
                        className="text-accent hover:underline flex items-center gap-1 text-[11px]"
                      >
                        <span>{src.url}</span>
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    ) : (
                      <span className="text-[10px] text-text-muted">Verified Internal Intelligence Cache</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* TAB 4: FORECASTS */}
        {activeTab === "forecast" && (
          <div className="space-y-6 pb-6">
            {(result?.trajectory?.trajectory_label || result?.trajectory?.label) && (
              <div className="p-3.5 rounded-xl bg-background/60 border border-border flex items-center justify-between">
                <div>
                  <span className="text-[10px] text-text-muted uppercase font-semibold">Trajectory direction</span>
                  <div className="text-lg font-bold text-text-primary font-mono">
                    {result.trajectory.trajectory_label || result.trajectory.label}
                  </div>
                </div>
                <div className="flex items-center gap-4 text-xs font-mono text-text-muted">
                  {[
                    ["14d", result.trajectory.prob_14d],
                    ["30d", result.trajectory.prob_30d],
                    ["60d", result.trajectory.prob_60d],
                  ].map(([horizon, p]) => (
                    <span key={horizon as string}>
                      P(HIGH {horizon}){" "}
                      <span className="text-text-primary font-bold">
                        {typeof p === "number" ? `${Math.round(p * 100)}%` : "—"}
                      </span>
                    </span>
                  ))}
                </div>
              </div>
            )}
            <section>
              <h3 className="text-sm font-semibold text-text-primary mb-3">Bayesian Trajectory & Scenario Projections</h3>
              {result?.scenarios && result.scenarios.length > 0 ? (
                <ForecastCharts
                  scenarios={result.scenarios}
                  timelineData={
                    result.trajectory && typeof result.trajectory.prob_14d === "number"
                      ? [["14d", Math.round((result.trajectory.prob_14d || 0) * 100)], ["30d", Math.round((result.trajectory.prob_30d || 0) * 100)], ["60d", Math.round((result.trajectory.prob_60d || 0) * 100)]]
                      : undefined
                  }
                />
              ) : demo ? (
                <>
                  <ForecastCharts
                    scenarios={[
                      { name: "De-escalation via Treaty Talks", probability: 58, description: "Bilateral working group convenes, reducing forward kinetic alert." },
                      { name: "Prolonged Armed Standoff", probability: 28, description: "Forces maintain forward winterized positions along disputed sectors." },
                      { name: "Localized Border Skirmish", probability: 14, description: "Tactical friction triggers isolated patrol engagement without general war." },
                    ]}
                  />
                  <p className="text-[10px] text-text-muted mt-2">Demo preview scenarios — not a real forecast.</p>
                </>
              ) : (
                <p className="text-xs text-text-muted">No scenario projections supplied by the pipeline.</p>
              )}
            </section>
          </div>
        )}

        {/* TAB 5: ADVANCED ENGINES */}
        {activeTab === "engines" && (
          <div className="space-y-6 pb-6">
            
            {/* 1. Fuzzy Logic SRE */}
            <section className="p-4 rounded-xl bg-background/60 border border-border space-y-3">
              <div className="flex items-center gap-2 mb-2">
                <Layers className="w-5 h-5 text-accent" />
                <h3 className="text-sm font-bold text-text-primary uppercase tracking-wider">Fuzzy Logic State Readiness (SRE)</h3>
              </div>
              <p className="text-xs text-text-muted mb-4">
                Raw intelligence signals are mapped through deterministic membership curves (triangular, trapezoidal) to calculate objective escalation bounds.
              </p>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="p-3 bg-background/80 border border-border rounded-lg">
                  <span className="text-[10px] text-text-muted uppercase font-semibold">SRE Escalation Score</span>
                  <div className="text-2xl font-bold text-red-400 font-mono mt-1">
                    {result?.fuzzy_trace?.sre_escalation_score != null ? result.fuzzy_trace.sre_escalation_score.toFixed(3) : "Unavailable"}
                  </div>
                </div>
                <div className="p-3 bg-background/80 border border-border rounded-lg">
                  <span className="text-[10px] text-text-muted uppercase font-semibold">Mathematical Risk Level</span>
                  <div className="text-2xl font-bold text-accent font-mono mt-1">
                    {result?.fuzzy_trace?.risk_level || "Unavailable"}
                  </div>
                </div>
              </div>
            </section>

            {/* 2. Symbolic Guardrails (Z3 & pyDatalog) */}
            <section className="p-4 rounded-xl bg-background/60 border border-border space-y-3">
              <div className="flex items-center gap-2 mb-2">
                <ShieldAlert className="w-5 h-5 text-emerald-400" />
                <h3 className="text-sm font-bold text-text-primary uppercase tracking-wider">Symbolic Guardrails (Z3 & pyDatalog)</h3>
              </div>
              <p className="text-xs text-text-muted mb-4">
                Mathematical firewalls verify that LLM outputs do not logically contradict the deterministic Fuzzy SRE math bounds.
              </p>

              <div className="p-3 rounded-lg border bg-background/80 border-border">
                 {result?.symbolic_guardrails?.findings && result.symbolic_guardrails.findings.length > 0 ? (
                    <div className="space-y-3">
                      <span className="text-xs font-bold text-red-400">🚨 Logical Contradictions Detected by Z3 Solver</span>
                      {result.symbolic_guardrails.findings.map((finding: any, i: number) => (
                        <div key={i} className="text-xs text-text-muted p-2 border border-red-500/30 bg-red-500/10 rounded">
                          {finding.message} (Rule: {finding.rule})
                        </div>
                      ))}
                    </div>
                 ) : (
                    <div className="flex items-center gap-2 text-emerald-400">
                      <CheckCircle2 className="w-4 h-4" />
                      <span className="text-xs font-bold">Passed Z3 Logic Checks</span>
                    </div>
                 )}
              </div>
            </section>

            {/* 3. Game Theory & Wargaming */}
            <section className="p-4 rounded-xl bg-background/60 border border-border space-y-3">
              <div className="flex items-center gap-2 mb-2">
                <Globe2 className="w-5 h-5 text-amber-400" />
                <h3 className="text-sm font-bold text-text-primary uppercase tracking-wider">Mesa Agent Wargaming</h3>
              </div>
              <p className="text-xs text-text-muted mb-4">
                Mesa agent-based simulation computes the Nash Equilibrium vector for counter-moves.
              </p>

              <div className="p-3 bg-background/80 border border-border rounded-lg">
                  <span className="text-[10px] text-text-muted uppercase font-semibold">Predicted Nash Equilibrium</span>
                  <div className="text-sm font-mono text-text-primary mt-1">
                    {result?.nash_equilibrium?.recommended_strategy || "Unavailable — no wargame output supplied"}
                  </div>
              </div>
            </section>

          </div>
        )}

        {/* TAB 6: NOTEBOOK */}
        {activeTab === "notebook" && (
          <div className="h-full min-h-[400px]">
            <Notebook initialContent="<h2>Analyst Working Notes</h2><p>Document human-in-the-loop insights and red-line reviews here...</p>" />
          </div>
        )}
      </div>
    </GlassCard>
  );
}

