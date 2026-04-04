import EventSource from 'react-native-sse';
import { useSettingsStore } from '../store/settings';
import type { SSEEvent } from '../types';

export type SSEHandler = (event: SSEEvent) => void;

export function createSSEConnection(onEvent: SSEHandler, onError: (err: Error) => void): () => void {
  const { serverUrl, jwtToken } = useSettingsStore.getState();

  const es = new EventSource(`${serverUrl}/api/v1/stream`, {
    headers: { Authorization: `Bearer ${jwtToken ?? ''}` },
  });

  es.addEventListener('message', (e) => {
    if (!e.data) return;
    try {
      const parsed = JSON.parse(e.data) as SSEEvent & { event?: string };
      const event = {
        type: parsed.type ?? parsed.event,
        data: parsed.data,
      } as SSEEvent;
      onEvent(event);
    } catch { /* skip malformed */ }
  });

  es.addEventListener('error', (e) => {
    if (e.type === 'error' || e.type === 'exception') {
      onError(new Error((e as { message?: string }).message ?? 'SSE error'));
    }
  });

  return () => {
    es.close();
  };
}
