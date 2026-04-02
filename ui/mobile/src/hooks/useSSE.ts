import { useEffect, useRef } from 'react';
import { AppState } from 'react-native';
import { useQueryClient } from '@tanstack/react-query';
import { createSSEConnection } from '../api/sse';
import { useSessionStore } from '../store/session';
import { useSettingsStore } from '../store/settings';
import type {
  Approval,
  SSEEvent,
} from '../types';

const MAX_RETRIES = 3;
const BASE_DELAY = 1000;

interface UseSSEOptions {
  onApprovalRequired?: (approval: Approval) => void;
}

export function useSSE(options?: UseSSEOptions) {
  const jwtToken = useSettingsStore((state) => state.jwtToken);
  const queryClient = useQueryClient();
  const retryCount = useRef(0);
  const disconnectRef = useRef<(() => void) | null>(null);
  const approvalHandler = options?.onApprovalRequired;

  function handleEvent(event: SSEEvent) {
    retryCount.current = 0;

    if (event.type === 'turn.response') {
      useSessionStore.getState().clearStreaming();
      queryClient.invalidateQueries({ queryKey: ['messages'] });
    } else if (event.type.startsWith('task.')) {
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
      queryClient.invalidateQueries({ queryKey: ['agent-sessions'] });
      queryClient.invalidateQueries({ queryKey: ['session-tasks'] });
      queryClient.invalidateQueries({ queryKey: ['session-detail'] });
    } else if (event.type === 'user.approval_requested') {
      const data = event.data as {
        approval_id: string;
        task_id: string;
        tool_name: string;
        tool_input: Record<string, unknown>;
        ts?: string;
      };
      approvalHandler?.({
        id: data.approval_id,
        taskId: data.task_id,
        description: `${data.tool_name}: ${JSON.stringify(data.tool_input)}`,
        requestedAt: data.ts ?? new Date().toISOString(),
      });
    } else if (event.type === 'user.intervened') {
      queryClient.invalidateQueries({ queryKey: ['session-detail'] });
      queryClient.invalidateQueries({ queryKey: ['agent-sessions'] });
    }
  }

  function connect() {
    disconnectRef.current?.();
    disconnectRef.current = createSSEConnection(handleEvent, (error) => {
      console.warn('SSE error:', error);
      if (retryCount.current < MAX_RETRIES) {
        const delay = BASE_DELAY * 2 ** retryCount.current;
        retryCount.current += 1;
        setTimeout(connect, delay);
      }
    });
  }

  useEffect(() => {
    if (!jwtToken) return;

    connect();

    const subscription = AppState.addEventListener('change', (state) => {
      if (state === 'active') {
        connect();
        queryClient.invalidateQueries();
      } else if (state === 'background') {
        disconnectRef.current?.();
        disconnectRef.current = null;
      }
    });

    return () => {
      disconnectRef.current?.();
      subscription.remove();
    };
  }, [approvalHandler, jwtToken, queryClient]);
}
