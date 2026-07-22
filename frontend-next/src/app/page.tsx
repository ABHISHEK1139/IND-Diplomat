"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import GlassCard from "@/components/ui/GlassCard";
import StatusBadge from "@/components/ui/StatusBadge";
import AnimatedCounter from "@/components/ui/AnimatedCounter";
import {
  Plus,
  Search,
  Shield,
  TrendingUp,
  AlertTriangle,
  Globe,
  Cpu,
  Zap,
  Leaf,
  Swords,
} from "lucide-react";

const recentInvestigations = [
  { id: "inv-001", title: "Ukraine Energy Crisis — Winter 2025 Impact", status: "complete", threat: "high", date: "2 hours ago", icon: Zap },
  { id: "inv-002", title: "AI Race: US-China Chip Export Controls", status: "complete", threat: "critical", date: "5 hours ago", icon: Cpu },
  { id: "inv-003", title: "India Semiconductor Mission — 2035 Outlook", status: "running", threat: "medium", date: "12 hours ago", icon: Globe },
  { id: "inv-004", title: "China-Taiwan Strait Escalation Scenarios", status: "complete", threat: "critical", date: "1 day ago", icon: Swords },
  { id: "inv-005", title: "Climate Change & Arctic Shipping Routes", status: "complete", threat: "medium", date: "2 days ago", icon: Leaf },
  { id: "inv-006", title: "South China Sea — UNCLOS Compliance", status: "complete", threat: "high", date: "3 days ago", icon: AlertTriangle },
];

export default function HomePage() {
  return (
    <div className="max-w-6xl mx-auto space-y-8">
      {/* Hero */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="text-center py-10"
      >
        <div className="inline-flex items-center gap-3 mb-4">
          <div className="w-12 h-12 rounded-2xl bg-accent/20 flex items-center justify-center">
            <Shield className="w-7 h-7 text-accent" />
          </div>
        </div>
        <h1 className="text-4xl font-extrabold tracking-tight text-text-primary">
          Strategic Intelligence Platform
        </h1>
        <p className="text-text-muted mt-2 text-sm max-w-lg mx-auto">
          Investigate. Reason. Forecast. Collaborate. — Powered by LangGraph, DSPy, and Mesa.
        </p>

        {/* CTA */}
        <Link href="/investigations/new">
          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            className="mt-6 inline-flex items-center gap-2 px-8 py-3 rounded-xl bg-accent text-white font-bold text-sm hover:shadow-[0_0_30px_rgba(59,130,246,0.4)] transition-all"
          >
            <Plus className="w-5 h-5" />
            New Investigation
          </motion.button>
        </Link>
      </motion.div>

      {/* Stats Bar */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: "Active Cases", value: 3, icon: TrendingUp, color: "text-accent" },
          { label: "Total Investigations", value: 47, icon: Search, color: "text-success" },
          { label: "Alerts (24h)", value: 5, icon: AlertTriangle, color: "text-warning" },
          { label: "Threat Level", value: "HIGH", icon: Shield, color: "text-danger" },
        ].map((stat) => (
          <GlassCard key={stat.label}>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-[11px] text-text-muted uppercase tracking-wider">{stat.label}</p>
                {typeof stat.value === "number" ? (
                  <AnimatedCounter value={stat.value} className={`text-2xl ${stat.color}`} />
                ) : (
                  <p className={`text-2xl font-bold font-mono ${stat.color}`}>{stat.value}</p>
                )}
              </div>
              <stat.icon className={`w-8 h-8 ${stat.color} opacity-30`} />
            </div>
          </GlassCard>
        ))}
      </div>

      {/* Search */}
      <div className="glass p-4">
        <div className="flex items-center gap-3">
          <Search className="w-5 h-5 text-text-muted" />
          <input
            type="text"
            placeholder="Search previous investigations..."
            className="flex-1 bg-transparent text-sm text-text-primary placeholder:text-text-muted/50 outline-none"
          />
        </div>
      </div>

      {/* Recent Investigations Grid */}
      <div>
        <h2 className="text-sm font-semibold text-text-muted uppercase tracking-widest mb-4">Recent Investigations</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {recentInvestigations.map((inv, i) => (
            <Link key={inv.id} href={`/investigations/${inv.id}`}>
              <motion.div
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.08 }}
              >
                <GlassCard className="h-full">
                  <div className="flex items-start justify-between mb-3">
                    <div className="w-9 h-9 rounded-lg bg-accent/10 flex items-center justify-center">
                      <inv.icon className="w-5 h-5 text-accent" />
                    </div>
                    <StatusBadge status={inv.status === "running" ? "running" : inv.threat} />
                  </div>
                  <h3 className="text-sm font-semibold text-text-primary line-clamp-2 mb-2">{inv.title}</h3>
                  <p className="text-[11px] text-text-muted">{inv.date}</p>
                </GlassCard>
              </motion.div>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
