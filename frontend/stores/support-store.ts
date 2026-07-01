import { create } from 'zustand';
import { attachStoreDevtools } from '@/utils/store-devtools';
import type { Customer, Message } from '@/types/support';
import { initialMessages, mockCustomers } from '@/types/mock-data';

type SupportState = {
  activeCustomer: Customer;
  messages: Message[];
  replyText: string;
  isGenerating: boolean;
  showMobileList: boolean;
  setActiveCustomer: (customer: Customer) => void;
  setMessages: (messages: Message[]) => void;
  addMessage: (message: Message) => void;
  setReplyText: (text: string) => void;
  setIsGenerating: (value: boolean) => void;
  setShowMobileList: (value: boolean) => void;
};

export const useSupportStore = create<SupportState>((set) => ({
  activeCustomer: mockCustomers[0],
  messages: initialMessages,
  replyText: '',
  isGenerating: false,
  showMobileList: false,
  setActiveCustomer: (customer) => set({ activeCustomer: customer }),
  setMessages: (messages) => set({ messages }),
  addMessage: (message) =>
    set((state) => ({ messages: [...state.messages, message] })),
  setReplyText: (text) => set({ replyText: text }),
  setIsGenerating: (value) => set({ isGenerating: value }),
  setShowMobileList: (value) => set({ showMobileList: value }),
}));

attachStoreDevtools('SupportStore', useSupportStore);
