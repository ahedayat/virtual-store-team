import { create } from 'zustand';
import type { ContentItem, ContentType } from '@/types/content';
import { mockContent } from '@/types/mock-data';
import { attachStoreDevtools } from '@/utils/store-devtools';

type ContentState = {
  filter: ContentType;
  items: ContentItem[];
  editingId: number | null;
  editValue: string;
  setFilter: (filter: ContentType) => void;
  setEditingId: (id: number | null) => void;
  setEditValue: (value: string) => void;
  startEdit: (item: ContentItem) => void;
  saveEdit: (id: number) => void;
  removeItem: (id: number) => void;
};

export const useContentStore = create<ContentState>((set, get) => ({
  filter: 'همه',
  items: mockContent,
  editingId: null,
  editValue: '',
  setFilter: (filter) => set({ filter }),
  setEditingId: (id) => set({ editingId: id }),
  setEditValue: (value) => set({ editValue: value }),
  startEdit: (item) => set({ editingId: item.id, editValue: item.content }),
  saveEdit: (id) => {
    const { items, editValue } = get();
    set({
      items: items.map((item) =>
        item.id === id ? { ...item, content: editValue } : item,
      ),
      editingId: null,
    });
  },
  removeItem: (id) =>
    set((state) => ({ items: state.items.filter((item) => item.id !== id) })),
}));

attachStoreDevtools('ContentStore', useContentStore);
