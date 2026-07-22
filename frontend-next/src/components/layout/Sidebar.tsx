"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import {
  Search,
  Plus,
  Bookmark,
  LayoutTemplate,
  Database,
  BarChart3,
  Settings,
  Shield,
  FileSearch,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";

const navItems = [
  { icon: FileSearch, label: "Investigations", href: "/" },
  { icon: Bookmark, label: "Bookmarks", href: "/bookmarks" },
  { icon: LayoutTemplate, label: "Templates", href: "/templates" },
  { icon: Database, label: "Datasets", href: "/datasets" },
  { icon: BarChart3, label: "Analytics", href: "/analytics" },
  { icon: Settings, label: "Settings", href: "/settings" },
];

export default function Sidebar() {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);

  return (
    <motion.aside
      animate={{ width: collapsed ? 72 : 260 }}
      transition={{ duration: 0.3, ease: "easeInOut" }}
      className="glass-heavy h-screen flex flex-col sticky top-0 z-50 overflow-hidden"
    >
      {/* Logo */}
      <div className="flex items-center gap-3 px-5 pt-6 pb-4">
        <div className="w-9 h-9 rounded-lg bg-accent/20 flex items-center justify-center flex-shrink-0">
          <Shield className="w-5 h-5 text-accent" />
        </div>
        {!collapsed && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.1 }}
          >
            <h1 className="text-lg font-bold tracking-tight text-text-primary">DIP</h1>
            <p className="text-[10px] font-medium text-text-muted tracking-widest uppercase">
              Strategic Intelligence
            </p>
          </motion.div>
        )}
      </div>

      {/* New Investigation Button */}
      <div className="px-3 mb-2">
        <Link href="/investigations/new">
          <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            className="w-full flex items-center gap-2 px-4 py-2.5 rounded-xl bg-accent text-white font-semibold text-sm transition-all hover:bg-accent/90 hover:shadow-[0_0_20px_rgba(59,130,246,0.3)]"
          >
            <Plus className="w-4 h-4" />
            {!collapsed && <span>New Investigation</span>}
          </motion.button>
        </Link>
      </div>

      {/* Search */}
      {!collapsed && (
        <div className="px-3 mb-4">
          <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-background/50 border border-border">
            <Search className="w-4 h-4 text-text-muted" />
            <input
              type="text"
              placeholder="Search..."
              className="bg-transparent text-sm text-text-primary placeholder:text-text-muted outline-none w-full"
            />
          </div>
        </div>
      )}

      {/* Navigation */}
      <nav className="flex-1 px-3 space-y-1">
        {navItems.map((item) => {
          const isActive = pathname === item.href || (item.href === "/" && pathname === "/");
          return (
            <Link key={item.href} href={item.href}>
              <motion.div
                whileHover={{ x: 4 }}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-colors cursor-pointer ${
                  isActive
                    ? "bg-accent/10 text-accent"
                    : "text-text-muted hover:text-text-primary hover:bg-surface/50"
                }`}
              >
                <item.icon className="w-[18px] h-[18px] flex-shrink-0" />
                {!collapsed && <span>{item.label}</span>}
              </motion.div>
            </Link>
          );
        })}
      </nav>

      {/* Collapse Toggle */}
      <div className="px-3 py-4 border-t border-border">
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="flex items-center gap-2 px-3 py-2 rounded-xl text-text-muted hover:text-text-primary transition-colors text-sm w-full"
        >
          {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
          {!collapsed && <span>Collapse</span>}
        </button>
      </div>
    </motion.aside>
  );
}
