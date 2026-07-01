import { create } from 'zustand';
import { attachStoreDevtools } from '@/utils/store-devtools';

type CoordinatorState = {
  isGenerating: boolean;
  lastUpdate: string;
  setIsGenerating: (value: boolean) => void;
  setLastUpdate: (value: string) => void;
};

export const useCoordinatorStore = create<CoordinatorState>((set) => ({
  isGenerating: false,
  lastUpdate: 'امروز، ۰۸:۳۰ صبح',
  setIsGenerating: (value) => set({ isGenerating: value }),
  setLastUpdate: (value) => set({ lastUpdate: value }),
}));

attachStoreDevtools('CoordinatorStore', useCoordinatorStore);
