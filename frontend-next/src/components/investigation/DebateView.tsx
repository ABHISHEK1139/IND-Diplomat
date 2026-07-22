"use client";

import { motion } from "framer-motion";
import { Users } from "lucide-react";

interface DebateEntry {
  expert: string;
  text: string;
  color: string;
}

interface DebateViewProps {
  debate: DebateEntry[];
}

export default function DebateView({ debate }: DebateViewProps) {
  return (
    <div className="space-y-3 overflow-y-auto max-h-[460px] pr-2">
      {debate.map((entry, i) => (
        <motion.div
          key={i}
          initial={{ opacity: 0, x: -10 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: i * 0.1 }}
          className="p-3 rounded-xl bg-background/50 border border-border"
        >
          <div className="flex items-center gap-2 mb-2">
            <div className="w-7 h-7 rounded-lg bg-accent/10 flex items-center justify-center">
              <Users className="w-3.5 h-3.5 text-accent" />
            </div>
            <span className={`text-xs font-bold ${entry.color}`}>{entry.expert}</span>
          </div>
          <p className="text-sm text-text-muted leading-relaxed">{entry.text}</p>
        </motion.div>
      ))}
    </div>
  );
}
