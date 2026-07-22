"use client";

import { motion } from "framer-motion";
import { ExternalLink } from "lucide-react";

interface EvidenceEntry {
  claim: string;
  sources: string[];
  contradictions: number;
}

interface EvidenceExplorerProps {
  evidence: EvidenceEntry[];
}

export default function EvidenceExplorer({ evidence }: EvidenceExplorerProps) {
  return (
    <div className="space-y-3 overflow-y-auto max-h-[460px] pr-2">
      {evidence.map((ev, i) => (
        <motion.div
          key={i}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: i * 0.08 }}
          className="p-3 rounded-xl bg-background/50 border border-border"
        >
          <p className="text-sm font-medium text-text-primary mb-2">{ev.claim}</p>
          <div className="flex flex-wrap gap-1.5 mb-2">
            {ev.sources.map((src) => (
              <span key={src} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-accent/10 text-accent text-[10px] font-semibold hover:bg-accent/20 cursor-pointer transition-colors">
                <ExternalLink className="w-2.5 h-2.5" />
                {src}
              </span>
            ))}
          </div>
          {ev.contradictions > 0 && (
            <span className="text-[10px] font-bold text-danger px-2 py-0.5 rounded-full bg-danger/10">
              {ev.contradictions} contradiction{ev.contradictions > 1 ? "s" : ""}
            </span>
          )}
        </motion.div>
      ))}
    </div>
  );
}
