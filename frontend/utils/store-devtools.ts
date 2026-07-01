import { mountStoreDevtool } from 'simple-zustand-devtools';
import type { StoreApi } from 'zustand';

export function attachStoreDevtools<T extends object>(
  name: string,
  store: StoreApi<T>,
) {
  if (process.env.NODE_ENV === 'development') {
    mountStoreDevtool(name, store as Parameters<typeof mountStoreDevtool>[1]);
  }
}
