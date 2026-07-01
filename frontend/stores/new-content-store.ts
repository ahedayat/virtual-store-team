import { create } from 'zustand';
import { attachStoreDevtools } from '@/utils/store-devtools';
import type {
  ContentStep,
  GeneratedDraft,
  NewContentType,
} from '@/types/content';

type NewContentState = {
  step: ContentStep;
  type: NewContentType | null;
  selectedProducts: number[];
  isGenerating: boolean;
  generatedDrafts: GeneratedDraft[];
  selectedDraftId: number | null;
  setStep: (step: ContentStep) => void;
  setType: (type: NewContentType | null) => void;
  toggleProduct: (id: number) => void;
  setIsGenerating: (value: boolean) => void;
  setGeneratedDrafts: (drafts: GeneratedDraft[]) => void;
  setSelectedDraftId: (id: number | null) => void;
  reset: () => void;
};

const initialState = {
  step: 1 as ContentStep,
  type: null as NewContentType | null,
  selectedProducts: [] as number[],
  isGenerating: false,
  generatedDrafts: [] as GeneratedDraft[],
  selectedDraftId: null as number | null,
};

export const useNewContentStore = create<NewContentState>((set) => ({
  ...initialState,
  setStep: (step) => set({ step }),
  setType: (type) => set({ type }),
  toggleProduct: (id) =>
    set((state) => ({
      selectedProducts: state.selectedProducts.includes(id)
        ? state.selectedProducts.filter((p) => p !== id)
        : [...state.selectedProducts, id],
    })),
  setIsGenerating: (value) => set({ isGenerating: value }),
  setGeneratedDrafts: (drafts) => set({ generatedDrafts: drafts }),
  setSelectedDraftId: (id) => set({ selectedDraftId: id }),
  reset: () => set(initialState),
}));

attachStoreDevtools('NewContentStore', useNewContentStore);
