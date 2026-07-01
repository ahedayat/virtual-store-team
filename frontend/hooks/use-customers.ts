import { useQuery } from '@tanstack/react-query';
import { mockCustomers } from '@/types/mock-data';
import type { Customer } from '@/types/support';

async function fetchCustomers(): Promise<Customer[]> {
  return Promise.resolve(mockCustomers);
}

export function useCustomers() {
  return useQuery({
    queryKey: ['customers'],
    queryFn: fetchCustomers,
  });
}
