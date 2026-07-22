"use client";

const variants: Record<string, { bg: string; text: string; label: string }> = {
  low:      { bg: "bg-success/10", text: "text-success", label: "LOW" },
  medium:   { bg: "bg-warning/10", text: "text-warning", label: "MEDIUM" },
  high:     { bg: "bg-danger/10",  text: "text-danger",  label: "HIGH" },
  critical: { bg: "bg-danger/20",  text: "text-danger",  label: "CRITICAL" },
  running:  { bg: "bg-accent/10",  text: "text-accent",  label: "RUNNING" },
  complete: { bg: "bg-success/10", text: "text-success", label: "COMPLETE" },
  queued:   { bg: "bg-text-muted/10", text: "text-text-muted", label: "QUEUED" },
};

interface StatusBadgeProps {
  status: string;
  className?: string;
}

export default function StatusBadge({ status, className = "" }: StatusBadgeProps) {
  const v = variants[status.toLowerCase()] || variants.queued;
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold tracking-wider ${v.bg} ${v.text} ${className}`}>
      <span className="w-1.5 h-1.5 rounded-full bg-current" />
      {v.label}
    </span>
  );
}
