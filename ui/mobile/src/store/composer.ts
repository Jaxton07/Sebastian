import { create } from 'zustand';

const DRAFT_KEY = '__draft__';

interface ComposerStore {
  thinkingBySession: Record<string, boolean>;
  getThinking: (sessionId: string | null) => boolean;
  setThinking: (sessionId: string | null, v: boolean) => void;
  migrateDraftToSession: (newSessionId: string) => void;
  clearSession: (sessionId: string) => void;
}

export const useComposerStore = create<ComposerStore>((set, get) => ({
  thinkingBySession: {},

  getThinking(sessionId) {
    const key = sessionId ?? DRAFT_KEY;
    return get().thinkingBySession[key] ?? false;
  },

  setThinking(sessionId, v) {
    const key = sessionId ?? DRAFT_KEY;
    set((s) => ({
      thinkingBySession: { ...s.thinkingBySession, [key]: v },
    }));
  },

  migrateDraftToSession(newSessionId) {
    set((s) => {
      const draftVal = s.thinkingBySession[DRAFT_KEY];
      if (draftVal === undefined) return s;
      const next = { ...s.thinkingBySession };
      if (draftVal) next[newSessionId] = true;
      delete next[DRAFT_KEY];
      return { thinkingBySession: next };
    });
  },

  clearSession(sessionId) {
    set((s) => {
      const next = { ...s.thinkingBySession };
      delete next[sessionId];
      return { thinkingBySession: next };
    });
  },
}));
