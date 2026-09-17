"use client";

import { CheckCircle2, AlertTriangle, XCircle, CircleDashed, ShieldAlert, Scale } from "lucide-react";
import { InvestigationResult } from "@/lib/api";

interface DecisionTrailProps {
  result: InvestigationResult | null;
  isDemo?: boolean;
}

type StepState = "done" | "warn" | "fail" | "idle";

function StepIcon({ state }: { state: StepState }) {
  if (state === "done") return <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />;
  if (state === "warn") return <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0" />;
  if (state === "fail") return <XCircle className="w-5 h-5 text-red-400 shrink-0" />;
  return <CircleDashed className="w-5 h-5 text-text-muted shrink-0" />;
}

export default function DecisionTrail({ result, isDemo }: DecisionTrailProps) {
  if (!result) {
    return (
      <p className="text-xs text-text-muted">
        {isDemo ? "Demo preview — run an investigation to see its decision trail." : "No result yet — the trail appears when the pipeline reports."}
      </p>
    );
  }

  const signals = result.raw_sources || [];
  const hypotheses = result.hypotheses || [];
  const redTeam = result.red_team_report || [];
  const verification = typeof result.verification_score === "number" ? result.verification_score : null;
  const gatePassed = verification != null && verification >= 0.7;
  const refusal = result.refusal;
  const status = (result.status || "UNKNOWN").toUpperCase();
  const avgConf =
    hypotheses.length > 0
      ? hypotheses.reduce((s: number, h: any) => s + (typeof h.confidence === "number" ? h.confidence : 0), 0) / hypotheses.length
      : null;

  const steps: Array<{ title: string; state: StepState; lines: string[] }> = [
    {
      title: `1 · Observed — ${signals.length} signal(s) ingested`,
      state: signals.length > 0 ? "done" : "warn",
      lines:
        signals.length > 0
          ? [
              `${signals.length} structured signals reached the world model.`,
              ...(result.xai_sources || []).slice(0, 4).map((s) => `via ${s}`),
            ]
          : ["No signals were ingested — downstream reasoning ran on an empty world model."],
    },
    {
      title: `2 · Hypothesized — ${hypotheses.length} minister portfolio(s)`,
      state: hypotheses.length > 0 ? "done" : "fail",
      lines:
        hypotheses.length > 0
          ? [
              `Mean minister confidence ${avgConf != null ? `${Math.round(avgConf * 100)}%` : "n/a"}.`,
              ...hypotheses.slice(0, 5).map((h: any) => {
                const c = typeof h.confidence === "number" ? `${Math.round(h.confidence * 100)}%` : "n/a";
                const mode = h.decision_mode ? ` [${h.decision_mode}]` : "";
                return `${h.minister || "Minister"}: ${h.type || "assessment"} (${c})${mode}`;
              }),
            ]
          : ["No hypotheses were produced — the council had nothing to debate."],
    },
    {
      title: `3 · Challenged — ${redTeam.length} red-team finding(s)`,
      state: redTeam.length > 0 ? "done" : "idle",
      lines:
        redTeam.length > 0
          ? redTeam.slice(0, 6)
          : ["No adversarial review was recorded for this assessment."],
    },
    {
      title: `4 · Verified — ${verification != null ? `${(verification * 100).toFixed(1)}%` : "no score"} (gate ≥ 70%)`,
      state: verification == null ? "idle" : gatePassed ? "done" : "fail",
      lines: [
        ...(verification != null
          ? [gatePassed ? "Claims met the corroboration gate." : "Claims fell below the corroboration gate — output is suspect."]
          : ["Verification did not run."]),
        ...(result.gate_verdict?.decision ? [`Assessment gate: ${result.gate_verdict.decision}.`] : []),
        ...(result.gate_verdict?.reasons || []).slice(0, 3),
      ],
    },
    {
      title: `5 · Decided — ${result.threat_level || "no level"} · ${status}`,
      state: status === "COMPLETE" ? "done" : status === "REFUSED" || status === "WITHHELD" || status === "ERROR" ? "fail" : "warn",
      lines:
        refusal && refusal.reasons
          ? [...refusal.reasons, ...(refusal.recommendation ? [refusal.recommendation] : [])]
          : status === "COMPLETE"
            ? ["Assessment passed all gates and was released."]
            : [`Pipeline status ${status}; no refusal record was attached.`],
    },
  ];

  return (
    <div className="space-y-4">
      <div className="p-3.5 rounded-xl bg-background/60 border border-border flex items-center gap-2.5">
        <Scale className="w-4 h-4 text-accent shrink-0" />
        <div>
          <h3 className="text-sm font-bold text-text-primary">Why this assessment?</h3>
          <p className="text-xs text-text-muted">
            Every number below traces to a pipeline stage. Nothing here is illustrative
            {isDemo ? " (demo preview data)" : ""} — challenge any step against its evidence.
          </p>
        </div>
      </div>

      <ol className="space-y-3">
        {steps.map((step) => (
          <li key={step.title} className="p-3.5 rounded-xl bg-background/50 border border-border space-y-2">
            <div className="flex items-center gap-2">
              <StepIcon state={step.state} />
              <span className="text-xs font-bold text-text-primary">{step.title}</span>
            </div>
            <ul className="space-y-1 pl-7">
              {step.lines.map((line, i) => (
                <li key={i} className="text-xs text-text-muted leading-relaxed flex items-start gap-1.5">
                  <ShieldAlert className="w-3 h-3 mt-0.5 shrink-0 text-text-muted/60" />
                  <span>{line}</span>
                </li>
              ))}
            </ul>
          </li>
        ))}
      </ol>

      {result.trace_id && (
        <p className="text-[10px] font-mono text-text-muted">
          trace {result.trace_id}
          {result.elapsed_seconds != null ? ` · ${result.elapsed_seconds.toFixed(1)}s` : ""}
        </p>
      )}
    </div>
  );
}
