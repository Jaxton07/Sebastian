import { useQuery } from '@tanstack/react-query';
import { getMessages } from '../api/turns';

export function useMessages(sessionId: string | null) {
  return useQuery({
    queryKey: ['messages', sessionId],
    queryFn: () => getMessages(sessionId!),
    enabled: !!sessionId,
  });
}
