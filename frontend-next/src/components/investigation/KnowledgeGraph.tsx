"use client";

import { useCallback, useMemo } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  Node,
  Edge,
  useNodesState,
  useEdgesState,
  ConnectionMode,
  MarkerType,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

// Custom node colors by entity type
const typeColors: Record<string, string> = {
  country:      "#3B82F6",
  organization: "#10B981",
  person:       "#F59E0B",
  technology:   "#8B5CF6",
  sector:       "#EF4444",
  event:        "#EC4899",
  default:      "#64748B",
};

interface KnowledgeGraphProps {
  entities: Array<{ id: string; label: string; type: string }>;
  relationships: Array<{ source: string; target: string; label: string }>;
  onNodeClick?: (nodeId: string) => void;
}

export default function KnowledgeGraph({ entities, relationships, onNodeClick }: KnowledgeGraphProps) {
  // Convert entities to React Flow nodes in a circular layout
  const initialNodes: Node[] = useMemo(() => {
    const radius = 220;
    const centerX = 300;
    const centerY = 280;

    return entities.map((entity, i) => {
      const angle = (2 * Math.PI * i) / entities.length;
      const color = typeColors[entity.type] || typeColors.default;

      return {
        id: entity.id,
        data: { label: entity.label },
        position: {
          x: centerX + radius * Math.cos(angle),
          y: centerY + radius * Math.sin(angle),
        },
        style: {
          background: `${color}20`,
          border: `2px solid ${color}`,
          borderRadius: "12px",
          padding: "8px 16px",
          color: "#F1F5F9",
          fontSize: "12px",
          fontWeight: 600,
          backdropFilter: "blur(8px)",
          boxShadow: `0 0 12px ${color}30`,
          cursor: "pointer",
        },
      };
    });
  }, [entities]);

  // Convert relationships to React Flow edges
  const initialEdges: Edge[] = useMemo(
    () =>
      relationships.map((rel, i) => ({
        id: `e-${i}`,
        source: rel.source,
        target: rel.target,
        label: rel.label,
        type: "smoothstep",
        animated: true,
        style: { stroke: "#3B82F640", strokeWidth: 1.5 },
        labelStyle: { fill: "#94A3B8", fontSize: 10, fontWeight: 500 },
        markerEnd: { type: MarkerType.ArrowClosed, color: "#3B82F660" },
      })),
    [relationships]
  );

  const [nodes, , onNodesChange] = useNodesState(initialNodes);
  const [edges, , onEdgesChange] = useEdgesState(initialEdges);

  const handleNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      onNodeClick?.(node.id);
    },
    [onNodeClick]
  );

  return (
    <div className="w-full h-full min-h-[400px] rounded-xl overflow-hidden" style={{ background: "#0B1020" }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={handleNodeClick}
        connectionMode={ConnectionMode.Loose}
        fitView
        proOptions={{ hideAttribution: true }}
      >
        <Background color="#1E264220" gap={20} />
        <Controls
          style={{
            background: "#161B2E",
            border: "1px solid #1E2642",
            borderRadius: "12px",
          }}
        />
        <MiniMap
          nodeColor={(node) => {
            const borderColor = (node.style?.border as string) || "#64748B";
            // Extract the color from the border string
            const match = borderColor.match(/#[0-9A-Fa-f]{6}/);
            return match ? match[0] : "#64748B";
          }}
          style={{
            background: "#161B2E",
            border: "1px solid #1E2642",
            borderRadius: "12px",
          }}
          maskColor="rgba(11, 16, 32, 0.7)"
        />
      </ReactFlow>
    </div>
  );
}
