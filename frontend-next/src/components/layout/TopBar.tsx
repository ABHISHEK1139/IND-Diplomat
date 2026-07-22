"use client";

import { usePathname } from "next/navigation";
import { ShieldCheck, Bell, Search, ChevronRight } from "lucide-react";

export default function TopBar() {
  const pathname = usePathname();
  
  // Basic breadcrumbs based on pathname
  const paths = pathname.split("/").filter(Boolean);
  
  return (
    <div className="h-16 border-b border-border bg-surface/50 backdrop-blur-md flex items-center justify-between px-6 sticky top-0 z-40">
      {/* Breadcrumbs */}
      <div className="flex items-center gap-2 text-sm">
        <span className="text-text-muted">DIP Workspace</span>
        {paths.map((p, i) => (
          <div key={i} className="flex items-center gap-2">
            <ChevronRight className="w-4 h-4 text-border" />
            <span className={i === paths.length - 1 ? "text-text-primary font-medium" : "text-text-muted"}>
              {p.charAt(0).toUpperCase() + p.slice(1).replace("-", " ")}
            </span>
          </div>
        ))}
      </div>

      {/* Right Actions */}
      <div className="flex items-center gap-4">
        <div className="hidden md:flex items-center gap-2 bg-background border border-border rounded-full px-3 py-1.5 text-xs text-text-muted focus-within:border-accent/50 focus-within:ring-1 focus-within:ring-accent/50 transition-all">
          <Search className="w-3.5 h-3.5" />
          <input 
            type="text" 
            placeholder="Search entities..." 
            className="bg-transparent outline-none w-32 placeholder:text-text-muted/50"
          />
        </div>
        
        <button className="relative text-text-muted hover:text-text-primary transition-colors">
          <Bell className="w-5 h-5" />
          <span className="absolute 0 right-0 w-2 h-2 bg-accent rounded-full border border-surface"></span>
        </button>

        <div className="flex items-center gap-2 pl-4 border-l border-border">
          <div className="flex flex-col items-end">
            <span className="text-sm font-semibold text-text-primary leading-none">A. Kumar</span>
            <span className="text-[10px] text-accent font-mono mt-1">TS//SCI CLEARANCE</span>
          </div>
          <div className="w-9 h-9 rounded-full bg-accent/20 border border-accent/30 flex items-center justify-center">
            <ShieldCheck className="w-5 h-5 text-accent" />
          </div>
        </div>
      </div>
    </div>
  );
}
