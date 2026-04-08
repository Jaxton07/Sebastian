import * as SecureStore from 'expo-secure-store';
import { create } from 'zustand';
import type { LLMProviderType, ThinkingCapability } from '../types';
import { useComposerStore } from './composer';
import { useConversationStore } from './conversation';
import { useLLMProvidersStore } from './llmProviders';
import { useSessionStore } from './session';

const KEYS = {
  serverUrl: 'settings_server_url',
  jwtToken: 'settings_jwt_token',
  llmProviderType: 'settings_llm_provider_type',
  llmApiKey: 'settings_llm_api_key',
  themeMode: 'settings_theme_mode',
  connectionStatus: 'settings_connection_status',
} as const;

interface LocalLLMConfig {
  providerType: LLMProviderType;
  apiKey: string;
}

interface SettingsState {
  serverUrl: string;
  jwtToken: string | null;
  llmProvider: LocalLLMConfig | null;
  themeMode: 'system' | 'light' | 'dark';
  connectionStatus: 'idle' | 'ok' | 'fail';
  currentThinkingCapability: ThinkingCapability | null;
  isLoaded: boolean;
  load: () => Promise<void>;
  setServerUrl: (url: string) => Promise<void>;
  setJwtToken: (token: string | null) => Promise<void>;
  setLlmProvider: (provider: LocalLLMConfig) => Promise<void>;
  setThemeMode: (mode: 'system' | 'light' | 'dark') => Promise<void>;
  setConnectionStatus: (status: 'idle' | 'ok' | 'fail') => Promise<void>;
  setCurrentThinkingCapability: (cap: ThinkingCapability | null) => void;
}

async function clearPersistedServerBoundState(): Promise<void> {
  await Promise.all([
    SecureStore.deleteItemAsync(KEYS.jwtToken),
    SecureStore.deleteItemAsync(KEYS.connectionStatus),
  ]);
}

function clearServerBoundState(set: (patch: Partial<SettingsState>) => void): void {
  useLLMProvidersStore.getState().reset();
  useSessionStore.getState().reset();
  useConversationStore.getState().reset();
  useComposerStore.getState().resetServerBoundState();
  set({
    jwtToken: null,
    connectionStatus: 'idle',
    currentThinkingCapability: null,
  });
}

export function getServerConfigInputValue(
  currentInput: string,
  serverUrl: string,
  isLoaded: boolean,
): string {
  return isLoaded ? serverUrl : currentInput;
}

export const useSettingsStore = create<SettingsState>((set, get) => ({
  serverUrl: '',
  jwtToken: null,
  llmProvider: null,
  themeMode: 'system',
  connectionStatus: 'idle',
  currentThinkingCapability: null,
  isLoaded: false,

  load: async () => {
    const [serverUrl, jwtToken, providerType, apiKey, themeMode, connectionStatus] = await Promise.all([
      SecureStore.getItemAsync(KEYS.serverUrl),
      SecureStore.getItemAsync(KEYS.jwtToken),
      SecureStore.getItemAsync(KEYS.llmProviderType),
      SecureStore.getItemAsync(KEYS.llmApiKey),
      SecureStore.getItemAsync(KEYS.themeMode),
      SecureStore.getItemAsync(KEYS.connectionStatus),
    ]);
    const llmProvider =
      providerType && apiKey
        ? { providerType: providerType as LLMProviderType, apiKey }
        : null;
    set({
      serverUrl: serverUrl ?? '',
      jwtToken: jwtToken ?? null,
      llmProvider,
      themeMode: (themeMode === 'light' || themeMode === 'dark' ? themeMode : 'system'),
      connectionStatus:
        connectionStatus === 'ok' || connectionStatus === 'fail' ? connectionStatus : 'idle',
      isLoaded: true,
    });
  },

  setServerUrl: async (url) => {
    const previousServerUrl = get().serverUrl;
    await SecureStore.setItemAsync(KEYS.serverUrl, url);
    set({ serverUrl: url });
    if (previousServerUrl !== url) {
      await clearPersistedServerBoundState();
      clearServerBoundState(set);
    }
  },

  setJwtToken: async (token) => {
    if (token === null) {
      await clearPersistedServerBoundState();
      clearServerBoundState(set);
      return;
    }
    await SecureStore.setItemAsync(KEYS.jwtToken, token);
    set({ jwtToken: token });
  },

  setLlmProvider: async (provider) => {
    await Promise.all([
      SecureStore.setItemAsync(KEYS.llmProviderType, provider.providerType),
      SecureStore.setItemAsync(KEYS.llmApiKey, provider.apiKey),
    ]);
    set({ llmProvider: provider });
  },

  setThemeMode: async (mode) => {
    await SecureStore.setItemAsync(KEYS.themeMode, mode);
    set({ themeMode: mode });
  },

  setConnectionStatus: async (status) => {
    await SecureStore.setItemAsync(KEYS.connectionStatus, status);
    set({ connectionStatus: status });
  },

  setCurrentThinkingCapability(cap) {
    set({ currentThinkingCapability: cap });
  },
}));
