"use client";

import { motion } from "framer-motion";
import AnimatedCounter from "@/components/ui/AnimatedCounter";

interface ConfidenceMetrics {
  evidence: number | null;
  sources: number | null;
  expertAgreement: number | null;
  forecastReliability: number | null;
}

export default function ConfidencePanel({ metrics }: { metrics: ConfidenceMetrics }) {
  // Backend reports 0-1 fractions; demo data uses 0-100. Normalize honestly.
  const normalize = (v: number | null) => (typeof v === "number" ? (v <= 1 ? v * 100 : v) : null);
  const bars = [
    { label: "Evidence", value: normalize(metrics.evidence), color: "bg-accent" },
    { label: "Sources", value: normalize(metrics.sources), color: "bg-success" },
    { label: "Expert Agreement", value: normalize(metrics.expertAgreement), color: "bg-warning" },
    { label: "Forecast Reliability", value: normalize(metrics.forecastReliability), color: "bg-accent/70" },
  ];

  return (
    <div className="space-y-4">
      {bars.map((bar, i) => (
        <div key={bar.label}>
          <div className="flex justify-between text-xs mb-1 font-semibold">
            <span className="text-text-muted">{bar.label}</span>
            <span className="text-text-primary font-mono">
              {bar.value == null ? "n/a" : <><AnimatedCounter value={Math.round(bar.value)} />%</>}
            </span>
          </div>
          <div className="h-1.5 w-full bg-background rounded-full overflow-hidden">
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${bar.value ?? 0}%` }}
              transition={{ duration: 1, delay: i * 0.1 }}
              className={`h-full ${bar.color}`}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
