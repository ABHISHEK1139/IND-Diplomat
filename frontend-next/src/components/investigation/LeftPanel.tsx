"use client";

import dynamic from "next/dynamic";
import { Network } from "lucide-react";
import GlassCard from "@/components/ui/GlassCard";

const KnowledgeGraph = dynamic(
  () => import("@/components/investigation/KnowledgeGraph"),
  { ssr: false, loading: () => <div className="flex items-center justify-center h-full text-text-muted text-sm">Loading graph...</div> }
);

interface LeftPanelProps {
  entities: Array<{ id: string; label: string; type: string }>;
  relationships: Array<{ source: string; target: string; label: string }>;
  selectedNode: string | null;
  setSelectedNode: (node: string | null) => void;
}

export default function LeftPanel({ entities, relationships, selectedNode, setSelectedNode }: LeftPanelProps) {
  return (
    <GlassCard hover={false} className="h-full p-2 flex flex-col">
      <div className="flex items-center gap-2 px-3 pt-2 pb-1 shrink-0">
        <Network className="w-4 h-4 text-accent" />
        <h3 className="text-sm font-semibold text-text-primary">Knowledge Graph</h3>
        {selectedNode && (
          <span className="ml-auto text-[10px] px-2 py-0.5 rounded-full bg-accent/10 text-accent font-semibold">
            {selectedNode}
          </span>
        )}
      </div>
      <div className="flex-1 relative min-h-[400px]">
        <KnowledgeGraph
          entities={entities}
          relationships={relationships}
          onNodeClick={setSelectedNode}
        />
      </div>
    </GlassCard>
  );
}
