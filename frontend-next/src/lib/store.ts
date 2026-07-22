import { create } from "zustand";

interface AppState {
  // Sidebar
  sidebarCollapsed: boolean;
  toggleSidebar: () => void;

  // Active investigation
  activeJobId: string | null;
  setActiveJobId: (id: string | null) => void;

  // Pipeline statuses
  pipelineStatuses: Record<string, "waiting" | "running" | "complete" | "error">;
  setPipelineStatus: (phase: string, status: "waiting" | "running" | "complete" | "error") => void;
  resetPipeline: () => void;
}

export const useAppStore = create<AppState>((set) => ({
  sidebarCollapsed: false,
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),

  activeJobId: null,
  setActiveJobId: (id) => set({ activeJobId: id }),

  pipelineStatuses: {},
  setPipelineStatus: (phase, status) =>
    set((s) => ({ pipelineStatuses: { ...s.pipelineStatuses, [phase]: status } })),
  resetPipeline: () => set({ pipelineStatuses: {} }),
}));
