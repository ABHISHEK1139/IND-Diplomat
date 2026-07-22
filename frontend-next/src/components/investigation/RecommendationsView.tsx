"use client";

interface Recommendation {
  option: string;
  impact: string;
  confidence: number;
}

interface RecommendationsViewProps {
  recommendations: Recommendation[];
}

export default function RecommendationsView({ recommendations }: RecommendationsViewProps) {
  return (
    <div className="space-y-2">
      {recommendations.map((rec, idx) => (
        <div key={idx} className="flex items-center justify-between p-3 rounded-xl bg-background/50 border border-border">
          <div>
            <p className="text-sm font-medium text-text-primary">{rec.option}</p>
            <p className="text-[11px] text-text-muted">Impact: {rec.impact}</p>
          </div>
          <span className="text-xs font-bold font-mono text-accent">{rec.confidence}%</span>
        </div>
      ))}
    </div>
  );
}
