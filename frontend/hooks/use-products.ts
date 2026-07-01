import { useQuery } from '@tanstack/react-query';
import { mockProducts } from '@/types/mock-data';
import type { Product } from '@/types/content';

async function fetchProducts(): Promise<Product[]> {
  return Promise.resolve(mockProducts);
}

export function useProducts() {
  return useQuery({
    queryKey: ['products'],
    queryFn: fetchProducts,
  });
}
