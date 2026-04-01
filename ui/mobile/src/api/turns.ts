import { apiClient } from './client';
import type { Message, PaginatedMessages, PaginatedSessions, SessionMeta } from '../types';

export async function getSessions(): Promise<SessionMeta[]> {
  const { data } = await apiClient.get<PaginatedSessions>('/api/v1/sessions');
  return data.items;
}

export async function getMessages(sessionId: string): Promise<Message[]> {
  const { data } = await apiClient.get<PaginatedMessages>(`/api/v1/turns/${sessionId}`);
  return data.items;
}

export async function sendTurn(
  sessionId: string | null,
  content: string,
): Promise<{ sessionId: string }> {
  const { data } = await apiClient.post<{ sessionId: string }>('/api/v1/turns', {
    sessionId,
    content,
  });
  return data;
}

export async function cancelTurn(sessionId: string): Promise<void> {
  await apiClient.post(`/api/v1/sessions/${sessionId}/cancel`);
}
