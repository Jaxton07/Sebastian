import { useQuery } from '@tanstack/react-query';
import { getAgents } from '../api/agents';
import { useSettingsStore } from '../store/settings';

export function useAgents() {
  const jwtToken = useSettingsStore((s) => s.jwtToken);
  return useQuery({
    queryKey: ['agents'],
    queryFn: getAgents,
    enabled: !!jwtToken,
  });
}
