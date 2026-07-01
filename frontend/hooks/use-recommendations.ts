import { useQuery } from '@tanstack/react-query';
import { mockRecommendations } from '@/types/mock-data';
import type { Recommendation } from '@/types/sales';

async function fetchRecommendations(): Promise<Recommendation[]> {
  return Promise.resolve(mockRecommendations);
}

export function useRecommendations() {
  return useQuery({
    queryKey: ['recommendations'],
    queryFn: fetchRecommendations,
  });
}
