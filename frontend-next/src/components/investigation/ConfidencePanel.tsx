"use client";

import { motion } from "framer-motion";
import AnimatedCounter from "@/components/ui/AnimatedCounter";

interface ConfidenceMetrics {
  evidence: number;
  sources: number;
  expertAgreement: number;
  forecastReliability: number;
}

export default function ConfidencePanel({ metrics }: { metrics: ConfidenceMetrics }) {
  const bars = [
    { label: "Evidence", value: metrics.evidence, color: "bg-accent" },
    { label: "Sources", value: metrics.sources, color: "bg-success" },
    { label: "Expert Agreement", value: metrics.expertAgreement, color: "bg-warning" },
    { label: "Forecast Reliability", value: metrics.forecastReliability, color: "bg-accent/70" },
  ];

  return (
    <div className="space-y-4">
      {bars.map((bar, i) => (
        <div key={bar.label}>
          <div className="flex justify-between text-xs mb-1 font-semibold">
            <span className="text-text-muted">{bar.label}</span>
            <span className="text-text-primary font-mono"><AnimatedCounter value={bar.value} />%</span>
          </div>
          <div className="h-1.5 w-full bg-background rounded-full overflow-hidden">
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${bar.value}%` }}
              transition={{ duration: 1, delay: i * 0.1 }}
              className={`h-full ${bar.color}`}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
