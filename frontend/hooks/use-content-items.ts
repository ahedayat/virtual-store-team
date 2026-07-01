import { useQuery } from '@tanstack/react-query';
import { mockContent } from '@/types/mock-data';
import type { ContentItem } from '@/types/content';

async function fetchContentItems(): Promise<ContentItem[]> {
  return Promise.resolve(mockContent);
}

export function useContentItems() {
  return useQuery({
    queryKey: ['content-items'],
    queryFn: fetchContentItems,
  });
}
