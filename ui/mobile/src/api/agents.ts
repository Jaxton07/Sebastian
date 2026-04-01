import { apiClient } from './client';
import type { Agent } from '../types';

export async function getAgents(): Promise<Agent[]> {
  const { data } = await apiClient.get<Agent[]>('/api/v1/agents');
  return data;
}

export async function sendAgentCommand(agentId: string, content: string): Promise<void> {
  await apiClient.post(`/api/v1/agents/${agentId}/command`, { content });
}

export async function cancelAgent(agentId: string): Promise<void> {
  await apiClient.post(`/api/v1/agents/${agentId}/cancel`);
}
