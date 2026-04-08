import { create } from 'zustand';
import {
  getLLMProviders,
  createLLMProvider,
  updateLLMProvider,
  deleteLLMProvider,
} from '../api/llmProviders';
import type { LLMProvider, LLMProviderCreate } from '../types';

function mergeProviderWithDefaultExclusivity(
  providers: LLMProvider[],
  provider: LLMProvider,
  mode: 'create' | 'update',
): LLMProvider[] {
  const base =
    mode === 'create'
      ? [...providers, provider]
      : providers.map((item) => (item.id === provider.id ? provider : item));

  if (!provider.is_default) {
    return base;
  }

  return base.map((item) =>
    item.id === provider.id ? item : { ...item, is_default: false },
  );
}

interface LLMProvidersState {
  providers: LLMProvider[];
  loading: boolean;
  initialized: boolean;
  error: string | null;
  reset: () => void;
  fetch: () => Promise<void>;
  create: (body: LLMProviderCreate) => Promise<LLMProvider>;
  update: (id: string, updates: Partial<LLMProviderCreate>) => Promise<void>;
  remove: (id: string) => Promise<void>;
}

export const useLLMProvidersStore = create<LLMProvidersState>((set) => ({
  providers: [],
  loading: false,
  initialized: false,
  error: null,

  reset: () => set({ providers: [], loading: false, initialized: false, error: null }),

  fetch: async () => {
    set({ loading: true, error: null });
    try {
      const providers = await getLLMProviders();
      set({ providers, loading: false, initialized: true });
    } catch (err: unknown) {
      set({
        loading: false,
        initialized: true,
        error: err instanceof Error ? err.message : 'Failed to load providers',
      });
    }
  },

  create: async (body) => {
    const provider = await createLLMProvider(body);
    set((s) => ({
      providers: mergeProviderWithDefaultExclusivity(s.providers, provider, 'create'),
      initialized: true,
      error: null,
    }));
    return provider;
  },

  update: async (id, updates) => {
    const updated = await updateLLMProvider(id, updates);
    set((s) => ({
      initialized: true,
      error: null,
      providers: mergeProviderWithDefaultExclusivity(s.providers, updated, 'update'),
    }));
  },

  remove: async (id) => {
    await deleteLLMProvider(id);
    set((s) => ({
      initialized: true,
      error: null,
      providers: s.providers.filter((p) => p.id !== id),
    }));
  },
}));
