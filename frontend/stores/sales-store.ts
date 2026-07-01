import { create } from 'zustand';
import { attachStoreDevtools } from '@/utils/store-devtools';
import type { EditForm, RecType, Recommendation } from '@/types/sales';
import { mockRecommendations } from '@/types/mock-data';

type SalesState = {
  filter: RecType;
  items: Recommendation[];
  editingId: number | null;
  editForm: EditForm;
  setFilter: (filter: RecType) => void;
  startEdit: (item: Recommendation) => void;
  setEditForm: (form: EditForm) => void;
  updateEditField: (field: keyof EditForm, value: string) => void;
  saveEdit: (id: number) => void;
  removeItem: (id: number) => void;
};

export const useSalesStore = create<SalesState>((set, get) => ({
  filter: 'همه',
  items: mockRecommendations,
  editingId: null,
  editForm: { title: '', description: '', reason: '' },
  setFilter: (filter) => set({ filter }),
  startEdit: (item) =>
    set({
      editingId: item.id,
      editForm: {
        title: item.title,
        description: item.description,
        reason: item.reason,
      },
    }),
  setEditForm: (form) => set({ editForm: form }),
  updateEditField: (field, value) =>
    set((state) => ({
      editForm: { ...state.editForm, [field]: value },
    })),
  saveEdit: (id) => {
    const { items, editForm } = get();
    set({
      items: items.map((item) =>
        item.id === id ? { ...item, ...editForm } : item,
      ),
      editingId: null,
    });
  },
  removeItem: (id) =>
    set((state) => ({ items: state.items.filter((item) => item.id !== id) })),
}));

attachStoreDevtools('SalesStore', useSalesStore);
