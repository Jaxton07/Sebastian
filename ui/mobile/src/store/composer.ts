import * as SecureStore from 'expo-secure-store';
import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import type { StateStorage } from 'zustand/middleware';
import type { ThinkingEffort } from '../types';

const DRAFT_KEY = '__draft__';
const STORAGE_KEY = 'sebastian_composer_v2';

const secureStorage: StateStorage = {
  getItem: (name) => SecureStore.getItemAsync(name),
  setItem: (name, value) => SecureStore.setItemAsync(name, value),
  removeItem: (name) => SecureStore.deleteItemAsync(name),
};

export interface ClampReport {
  /** 第一项被降级时返回 from→to，否则不返回（表示无降级发生） */
  from: ThinkingEffort;
  to: ThinkingEffort;
}

interface ComposerStore {
  effortBySession: Record<string, ThinkingEffort>;
  lastUserChoice: ThinkingEffort;

  getEffort: (sessionId: string | null) => ThinkingEffort;
  setEffort: (sessionId: string | null, effort: ThinkingEffort) => void;
  migrateDraftToSession: (newSessionId: string) => void;
  clearSession: (sessionId: string) => void;
  resetServerBoundState: () => void;
  clampAllToCapability: (allowedEfforts: readonly ThinkingEffort[]) => ClampReport | null;
}

function clampOne(
  current: ThinkingEffort,
  allowed: readonly ThinkingEffort[],
): ThinkingEffort {
  // always_on / none：UI 不读 effort，固化为 off 避免脏 state
  if (allowed.length === 0) return 'off';
  if (allowed.includes(current)) return current;
  if (allowed.includes('on')) {
    return current === 'off' ? 'off' : 'on';
  }
  if (current === 'max' && allowed.includes('high')) return 'high';
  if (current === 'on' && allowed.includes('medium')) return 'medium';
  if (allowed.includes('off')) return 'off';
  return allowed[0] ?? 'off';
}

export const useComposerStore = create<ComposerStore>()(
  persist(
    (set, get) => ({
      effortBySession: {},
      lastUserChoice: 'off',

      getEffort(sessionId) {
        const key = sessionId ?? DRAFT_KEY;
        return get().effortBySession[key] ?? get().lastUserChoice;
      },

      setEffort(sessionId, effort) {
        const key = sessionId ?? DRAFT_KEY;
        set((s) => ({
          effortBySession: { ...s.effortBySession, [key]: effort },
          lastUserChoice: effort,
        }));
      },

      migrateDraftToSession(newSessionId) {
        set((s) => {
          const draftVal = s.effortBySession[DRAFT_KEY];
          if (draftVal === undefined) return s;
          const next = { ...s.effortBySession };
          next[newSessionId] = draftVal;
          delete next[DRAFT_KEY];
          return { effortBySession: next };
        });
      },

      clearSession(sessionId) {
        set((s) => {
          const next = { ...s.effortBySession };
          delete next[sessionId];
          return { effortBySession: next };
        });
      },

      resetServerBoundState() {
        set({ effortBySession: {} });
      },

      clampAllToCapability(allowedEfforts) {
        const s = get();
        let report: ClampReport | null = null;
        const nextMap: Record<string, ThinkingEffort> = {};
        for (const [k, v] of Object.entries(s.effortBySession)) {
          const clamped = clampOne(v, allowedEfforts);
          nextMap[k] = clamped;
          if (clamped !== v && report === null) {
            report = { from: v, to: clamped };
          }
        }
        const clampedLast = clampOne(s.lastUserChoice, allowedEfforts);
        if (clampedLast !== s.lastUserChoice && report === null) {
          report = { from: s.lastUserChoice, to: clampedLast };
        }
        set({
          effortBySession: nextMap,
          lastUserChoice: clampedLast,
        });
        return report;
      },
    }),
    {
      name: STORAGE_KEY,
      storage: createJSONStorage(() => secureStorage),
      partialize: (s) => ({ lastUserChoice: s.lastUserChoice }),
    },
  ),
);
