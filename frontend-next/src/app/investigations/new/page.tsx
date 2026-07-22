"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import {
  Search,
  TrendingUp,
  BookOpen,
  GitCompare,
  Clock,
  ShieldAlert,
  FileText,
  BarChart3,
  Network,
  FileDown,
  Presentation,
  ArrowRight,
  ArrowLeft,
  Rocket,
} from "lucide-react";
import { createInvestigation } from "@/lib/api";

const investigationTypes = [
  { key: "intelligence", label: "Intelligence", icon: Search, desc: "Full-spectrum analysis" },
  { key: "forecast",     label: "Forecast",     icon: TrendingUp, desc: "Future projections" },
  { key: "research",     label: "Research",      icon: BookOpen, desc: "Deep literature review" },
  { key: "compare",      label: "Compare",       icon: GitCompare, desc: "Side-by-side analysis" },
  { key: "timeline",     label: "Timeline",      icon: Clock, desc: "Chronological mapping" },
  { key: "risk",         label: "Risk Assessment",icon: ShieldAlert, desc: "Threat evaluation" },
];

const depths = [
  { key: "quick",    label: "Quick",                   time: "~1 min",  cost: "$0.02" },
  { key: "standard", label: "Standard",                time: "~3 min",  cost: "$0.06" },
  { key: "deep",     label: "Deep Investigation",      time: "~8 min",  cost: "$0.15" },
  { key: "full",     label: "Full Intelligence Dossier",time: "~20 min", cost: "$0.40" },
];

const outputs = [
  { key: "report",   label: "Report",          icon: FileText },
  { key: "dashboard",label: "Dashboard",       icon: BarChart3 },
  { key: "timeline", label: "Timeline",        icon: Clock },
  { key: "graph",    label: "Knowledge Graph", icon: Network },
  { key: "pdf",      label: "PDF",             icon: FileDown },
  { key: "slides",   label: "Slides",          icon: Presentation },
];

export default function NewInvestigationPage() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [query, setQuery] = useState("");
  const [type, setType] = useState("intelligence");
  const [depth, setDepth] = useState("standard");
  const [selectedOutputs, setSelectedOutputs] = useState<string[]>(["report", "dashboard"]);

  const toggleOutput = (key: string) => {
    setSelectedOutputs((prev) =>
      prev.includes(key) ? prev.filter((o) => o !== key) : [...prev, key]
    );
  };

  const selectedDepth = depths.find((d) => d.key === depth)!;

  const handleLaunch = async () => {
    try {
      const job = await createInvestigation(query || "General assessment");
      router.push(`/investigations/${job.job_id}`);
    } catch (err) {
      console.error("Failed to launch investigation:", err);
      // Fallback for demo purposes if backend isn't running
      const jobId = "demo-" + Date.now();
      router.push(`/investigations/${jobId}`);
    }
  };

  const steps = [
    // Step 0: Query
    <div key="query" className="space-y-4">
      <h2 className="text-2xl font-bold text-text-primary">What would you like to investigate?</h2>
      <p className="text-text-muted text-sm">Ask a strategic question. Be specific for deeper analysis.</p>
      <textarea
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="e.g. Can India become an AI semiconductor leader by 2035?"
        rows={4}
        className="w-full bg-background border border-border rounded-xl px-4 py-3 text-text-primary placeholder:text-text-muted/50 text-sm focus:outline-none focus:ring-2 focus:ring-accent/50 resize-none"
      />
    </div>,

    // Step 1: Type
    <div key="type" className="space-y-4">
      <h2 className="text-2xl font-bold text-text-primary">Investigation Type</h2>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        {investigationTypes.map((t) => (
          <motion.button
            key={t.key}
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            onClick={() => setType(t.key)}
            className={`flex flex-col items-center gap-2 p-4 rounded-xl border text-center transition-all ${
              type === t.key
                ? "border-accent bg-accent/10 text-accent"
                : "border-border bg-surface/50 text-text-muted hover:border-accent/30"
            }`}
          >
            <t.icon className="w-6 h-6" />
            <span className="text-sm font-semibold">{t.label}</span>
            <span className="text-[11px] opacity-70">{t.desc}</span>
          </motion.button>
        ))}
      </div>
    </div>,

    // Step 2: Depth
    <div key="depth" className="space-y-4">
      <h2 className="text-2xl font-bold text-text-primary">Analysis Depth</h2>
      <div className="space-y-2">
        {depths.map((d) => (
          <motion.button
            key={d.key}
            whileHover={{ x: 4 }}
            onClick={() => setDepth(d.key)}
            className={`w-full flex items-center justify-between p-4 rounded-xl border transition-all ${
              depth === d.key
                ? "border-accent bg-accent/10"
                : "border-border bg-surface/50 hover:border-accent/30"
            }`}
          >
            <div className="flex items-center gap-3">
              <div className={`w-3 h-3 rounded-full border-2 ${depth === d.key ? "border-accent bg-accent" : "border-text-muted"}`} />
              <span className={`text-sm font-semibold ${depth === d.key ? "text-accent" : "text-text-muted"}`}>{d.label}</span>
            </div>
            <div className="flex items-center gap-4 text-xs text-text-muted">
              <span>{d.time}</span>
              <span className="font-mono">{d.cost}</span>
            </div>
          </motion.button>
        ))}
      </div>
    </div>,

    // Step 3: Outputs
    <div key="outputs" className="space-y-4">
      <h2 className="text-2xl font-bold text-text-primary">Output Formats</h2>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        {outputs.map((o) => (
          <motion.button
            key={o.key}
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            onClick={() => toggleOutput(o.key)}
            className={`flex items-center gap-3 p-4 rounded-xl border transition-all ${
              selectedOutputs.includes(o.key)
                ? "border-accent bg-accent/10 text-accent"
                : "border-border bg-surface/50 text-text-muted hover:border-accent/30"
            }`}
          >
            <o.icon className="w-5 h-5" />
            <span className="text-sm font-semibold">{o.label}</span>
          </motion.button>
        ))}
      </div>
    </div>,

    // Step 4: Launch
    <div key="launch" className="space-y-6 text-center">
      <h2 className="text-2xl font-bold text-text-primary">Ready to Launch</h2>
      <div className="glass p-6 inline-block mx-auto text-left space-y-3">
        <div className="text-sm"><span className="text-text-muted">Query:</span> <span className="text-text-primary font-medium">{query || "—"}</span></div>
        <div className="text-sm"><span className="text-text-muted">Type:</span> <span className="text-accent font-semibold capitalize">{type}</span></div>
        <div className="text-sm"><span className="text-text-muted">Depth:</span> <span className="text-text-primary font-semibold">{selectedDepth.label}</span></div>
        <div className="text-sm"><span className="text-text-muted">Outputs:</span> <span className="text-text-primary">{selectedOutputs.join(", ")}</span></div>
        <div className="flex gap-6 pt-2 border-t border-border">
          <div>
            <p className="text-[11px] text-text-muted uppercase tracking-wider">Expected Time</p>
            <p className="text-lg font-bold text-accent">{selectedDepth.time}</p>
          </div>
          <div>
            <p className="text-[11px] text-text-muted uppercase tracking-wider">Estimated Cost</p>
            <p className="text-lg font-bold text-success">{selectedDepth.cost}</p>
          </div>
        </div>
      </div>
      <motion.button
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
        onClick={handleLaunch}
        className="inline-flex items-center gap-2 px-8 py-3 rounded-xl bg-accent text-white font-bold text-sm hover:shadow-[0_0_30px_rgba(59,130,246,0.4)] transition-all"
      >
        <Rocket className="w-5 h-5" />
        Launch Investigation
      </motion.button>
    </div>,
  ];

  return (
    <div className="max-w-2xl mx-auto py-12 px-4">
      {/* Step Indicator */}
      <div className="flex items-center justify-center gap-2 mb-10">
        {["Query", "Type", "Depth", "Output", "Launch"].map((label, i) => (
          <div key={label} className="flex items-center gap-2">
            <button
              onClick={() => setStep(i)}
              className={`w-8 h-8 rounded-full text-xs font-bold flex items-center justify-center transition-all ${
                i === step ? "bg-accent text-white" : i < step ? "bg-success/20 text-success" : "bg-surface text-text-muted"
              }`}
            >
              {i < step ? "✓" : i + 1}
            </button>
            {i < 4 && <div className={`w-8 h-[2px] ${i < step ? "bg-success/40" : "bg-border"}`} />}
          </div>
        ))}
      </div>

      {/* Step Content */}
      <AnimatePresence mode="wait">
        <motion.div
          key={step}
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -20 }}
          transition={{ duration: 0.2 }}
        >
          {steps[step]}
        </motion.div>
      </AnimatePresence>

      {/* Navigation */}
      <div className="flex justify-between mt-8">
        <button
          onClick={() => setStep(Math.max(0, step - 1))}
          disabled={step === 0}
          className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm text-text-muted hover:text-text-primary disabled:opacity-30 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" /> Back
        </button>
        {step < 4 && (
          <button
            onClick={() => setStep(step + 1)}
            disabled={step === 0 && !query.trim()}
            className="flex items-center gap-2 px-6 py-2 rounded-xl text-sm font-semibold bg-accent/10 text-accent hover:bg-accent/20 disabled:opacity-30 transition-all"
          >
            Next <ArrowRight className="w-4 h-4" />
          </button>
        )}
      </div>
    </div>
  );
}
