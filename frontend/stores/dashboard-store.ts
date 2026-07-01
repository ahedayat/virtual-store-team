import { create } from 'zustand';
import { attachStoreDevtools } from '@/utils/store-devtools';

type DashboardState = {
  activeAgent: number;
  setActiveAgent: (index: number) => void;
  cycleActiveAgent: () => void;
};

export const useDashboardStore = create<DashboardState>((set) => ({
  activeAgent: 0,
  setActiveAgent: (index) => set({ activeAgent: index }),
  cycleActiveAgent: () =>
    set((state) => ({ activeAgent: (state.activeAgent + 1) % 4 })),
}));

attachStoreDevtools('DashboardStore', useDashboardStore);
