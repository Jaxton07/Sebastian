import { apiClient } from './client';
import type { Agent } from '../types';

interface BackendAgentSummary {
  agent_type: string;
  name: string;
  description: string;
  active_session_count: number;
  max_children: number;
}

interface BackendAgentsResponse {
  agents: BackendAgentSummary[];
}

function mapAgentSummary(agent: BackendAgentSummary): Agent {
  return {
    id: agent.agent_type,
    name: agent.name || agent.agent_type,
    description: agent.description,
    status: agent.active_session_count > 0 ? 'working' : 'idle',
    active_session_count: agent.active_session_count,
    max_children: agent.max_children,
  };
}

export async function getAgents(): Promise<Agent[]> {
  const { data } = await apiClient.get<BackendAgentsResponse>('/api/v1/agents');
  return data.agents
    .filter((a) => a.agent_type !== 'sebastian')
    .map(mapAgentSummary);
}

export async function sendAgentCommand(agentId: string, content: string): Promise<void> {
  await apiClient.post(`/api/v1/agents/${agentId}/command`, { content });
}

export async function cancelAgent(agentId: string): Promise<void> {
  await apiClient.post(`/api/v1/agents/${agentId}/cancel`);
}
