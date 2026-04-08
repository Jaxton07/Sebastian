import { create } from 'zustand';
import type { SessionMeta } from '../types';

const MAX_SESSIONS = 20;

interface SessionState {
  sessionIndex: SessionMeta[];
  currentSessionId: string | null;
  draftSession: boolean;
  streamingMessage: string;
  reset: () => void;
  setCurrentSession: (id: string | null) => void;
  startDraft: () => void;
  persistSession: (meta: SessionMeta) => void;
  appendStreamingDelta: (delta: string) => void;
  clearStreaming: () => void;
}

export const useSessionStore = create<SessionState>((set) => ({
  sessionIndex: [],
  currentSessionId: null,
  draftSession: false,
  streamingMessage: '',

  reset: () =>
    set({
      sessionIndex: [],
      currentSessionId: null,
      draftSession: false,
      streamingMessage: '',
    }),

  setCurrentSession: (id) => set({ currentSessionId: id, draftSession: false }),

  startDraft: () => set({ currentSessionId: null, draftSession: true, streamingMessage: '' }),

  persistSession: (meta) =>
    set((state) => {
      const filtered = state.sessionIndex.filter((s) => s.id !== meta.id);
      const updated = [meta, ...filtered].slice(0, MAX_SESSIONS);
      return { sessionIndex: updated, currentSessionId: meta.id, draftSession: false };
    }),

  appendStreamingDelta: (delta) =>
    set((state) => ({ streamingMessage: state.streamingMessage + delta })),

  clearStreaming: () => set({ streamingMessage: '' }),
}));
