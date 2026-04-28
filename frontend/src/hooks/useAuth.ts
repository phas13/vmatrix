import { useQuery } from '@tanstack/react-query';
import { getMe } from '../api/auth';
import type { User } from '../types/domain';

export function useAuth(): { user: User | undefined; isLoading: boolean; isError: boolean } {
  const { data: user, isLoading, isError } = useQuery({
    queryKey: ['auth', 'me'],
    queryFn: getMe,
    retry: false,
  });
  return { user, isLoading, isError };
}
