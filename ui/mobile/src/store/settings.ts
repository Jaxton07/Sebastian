import * as SecureStore from 'expo-secure-store';
import { create } from 'zustand';
import type { LLMProvider } from '../types';

const KEYS = {
  serverUrl: 'settings_server_url',
  jwtToken: 'settings_jwt_token',
  llmProvider: 'settings_llm_provider',
} as const;

interface SettingsState {
  serverUrl: string;
  jwtToken: string | null;
  llmProvider: LLMProvider | null;
  isLoaded: boolean;
  load: () => Promise<void>;
  setServerUrl: (url: string) => Promise<void>;
  setJwtToken: (token: string | null) => Promise<void>;
  setLlmProvider: (provider: LLMProvider) => Promise<void>;
}

export const useSettingsStore = create<SettingsState>((set) => ({
  serverUrl: '',
  jwtToken: null,
  llmProvider: null,
  isLoaded: false,

  load: async () => {
    const [serverUrl, jwtToken, raw] = await Promise.all([
      SecureStore.getItemAsync(KEYS.serverUrl),
      SecureStore.getItemAsync(KEYS.jwtToken),
      SecureStore.getItemAsync(KEYS.llmProvider),
    ]);
    set({
      serverUrl: serverUrl ?? '',
      jwtToken: jwtToken ?? null,
      llmProvider: raw ? (JSON.parse(raw) as LLMProvider) : null,
      isLoaded: true,
    });
  },

  setServerUrl: async (url) => {
    await SecureStore.setItemAsync(KEYS.serverUrl, url);
    set({ serverUrl: url });
  },

  setJwtToken: async (token) => {
    if (token === null) await SecureStore.deleteItemAsync(KEYS.jwtToken);
    else await SecureStore.setItemAsync(KEYS.jwtToken, token);
    set({ jwtToken: token });
  },

  setLlmProvider: async (provider) => {
    await SecureStore.setItemAsync(KEYS.llmProvider, JSON.stringify(provider));
    set({ llmProvider: provider });
  },
}));
