import { apiClient } from './client';

export interface LogState {
  llm_stream_enabled: boolean;
  sse_enabled: boolean;
}

export interface LogConfigPatch {
  llm_stream_enabled?: boolean;
  sse_enabled?: boolean;
}

export async function getLogState(): Promise<LogState> {
  const resp = await apiClient.get<LogState>('/api/v1/debug/logging');
  return resp.data;
}

export async function patchLogState(patch: LogConfigPatch): Promise<LogState> {
  const resp = await apiClient.patch<LogState>('/api/v1/debug/logging', patch);
  return resp.data;
}
