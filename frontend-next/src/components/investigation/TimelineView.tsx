"use client";

import dynamic from "next/dynamic";
// Dynamically import react-chrono to avoid SSR window issues
const Chrono = dynamic(() => import("react-chrono").then(mod => mod.Chrono), { ssr: false });

interface TimelineEvent {
  date: string;
  title: string;
  cardTitle: string;
  cardDetailedText: string;
}

export default function TimelineView({ events }: { events: TimelineEvent[] }) {
  if (!events || events.length === 0) return null;

  return (
    <div className="h-[460px] w-full" style={{ overflowX: "hidden" }}>
      <Chrono
        items={events}
        mode="VERTICAL_ALTERNATING"
        theme={{
          primary: "#3B82F6",
          secondary: "#161B2E",
          cardBgColor: "rgba(22, 27, 46, 0.5)",
          titleColor: "#3B82F6",
          titleColorActive: "#3B82F6",
          textColor: "#F1F5F9",
        }}
        cardHeight={80}
        classNames={{
          card: "border border-[#1E2642] backdrop-blur-md !rounded-xl !p-3",
          title: "text-accent !font-bold !text-sm",
          cardTitle: "text-text-primary !font-bold !text-sm !mb-1",
          cardText: "text-text-muted !text-xs",
        }}
      />
    </div>
  );
}
