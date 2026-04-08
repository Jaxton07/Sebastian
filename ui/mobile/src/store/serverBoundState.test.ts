import { beforeEach, describe, expect, test, vi } from 'vitest';
import { useComposerStore } from './composer';
import { useConversationStore } from './conversation';
import { useLLMProvidersStore } from './llmProviders';
import { useSessionStore } from './session';
import { useSettingsStore } from './settings';
import * as SettingsModule from './settings';

const secureStore = new Map<string, string>();

vi.mock('../api/llmProviders', () => ({
  getLLMProviders: vi.fn(async () => []),
  createLLMProvider: vi.fn(),
  updateLLMProvider: vi.fn(),
  deleteLLMProvider: vi.fn(),
}));

vi.mock('expo-secure-store', () => ({
  getItemAsync: vi.fn(async (key: string) => secureStore.get(key) ?? null),
  setItemAsync: vi.fn(async (key: string, value: string) => {
    secureStore.set(key, value);
  }),
  deleteItemAsync: vi.fn(async (key: string) => {
    secureStore.delete(key);
  }),
}));

const { getServerConfigInputValue } = SettingsModule as any;

function seedServerBoundState(): void {
  useSettingsStore.setState({
    serverUrl: 'http://old.example.com:8000',
    jwtToken: 'old-token',
    llmProvider: { providerType: 'openai', apiKey: 'secret' },
    themeMode: 'dark',
    connectionStatus: 'fail',
    currentThinkingCapability: 'adaptive',
    isLoaded: true,
  });

  useLLMProvidersStore.setState({
    providers: [
      {
        id: 'provider-1',
        name: 'Old Provider',
        provider_type: 'openai',
        base_url: null,
        api_key: 'secret',
        model: 'gpt-4o',
        thinking_format: null,
        thinking_capability: 'adaptive',
        is_default: true,
        created_at: '2026-04-08T00:00:00.000Z',
        updated_at: '2026-04-08T00:00:00.000Z',
      },
    ],
    loading: true,
    initialized: true,
    error: 'boom',
  });

  useSessionStore.setState({
    sessionIndex: [
      {
        id: 'session-1',
        agent: 'main',
        title: 'Old session',
        status: 'active',
        updated_at: '2026-04-08T00:00:00.000Z',
        task_count: 0,
        active_task_count: 0,
        depth: 0,
        parent_session_id: null,
        last_activity_at: '2026-04-08T00:00:00.000Z',
      },
    ],
    currentSessionId: 'session-1',
    draftSession: true,
    streamingMessage: 'streaming',
  });

  useConversationStore.setState({
    sessions: {
      'session-1': {
        status: 'live',
        messages: [],
        activeTurn: null,
        errorBanner: { code: 'old-error', message: 'old error' },
      },
    },
    draftErrorBanner: { code: 'draft-error', message: 'draft error' },
  });

  useComposerStore.setState({
    effortBySession: { 'session-1': 'high' },
    lastUserChoice: 'max',
  });
}

beforeEach(() => {
  secureStore.clear();
  seedServerBoundState();
});

describe('server-bound reset', () => {
  test('logout clears server-bound state after jwt token is removed', async () => {
    secureStore.set('settings_jwt_token', 'old-token');
    secureStore.set('settings_connection_status', 'fail');

    await useSettingsStore.getState().setJwtToken(null);

    expect(useSettingsStore.getState().jwtToken).toBeNull();
    expect(useSettingsStore.getState().connectionStatus).toBe('idle');
    expect(useSettingsStore.getState().currentThinkingCapability).toBeNull();

    expect(useLLMProvidersStore.getState()).toMatchObject({
      providers: [],
      loading: false,
      initialized: false,
      error: null,
    });
    expect(useSessionStore.getState()).toMatchObject({
      sessionIndex: [],
      currentSessionId: null,
      draftSession: false,
      streamingMessage: '',
    });
    expect(useConversationStore.getState()).toMatchObject({
      sessions: {},
      draftErrorBanner: null,
    });
    expect(useComposerStore.getState()).toMatchObject({
      effortBySession: {},
      lastUserChoice: 'max',
    });
    expect(secureStore.get('settings_jwt_token')).toBeUndefined();
    expect(secureStore.get('settings_connection_status')).toBeUndefined();
  });

  test('changing serverUrl clears server-bound state and keeps the new url', async () => {
    secureStore.set('settings_jwt_token', 'old-token');
    secureStore.set('settings_connection_status', 'fail');

    await useSettingsStore.getState().setServerUrl('http://new.example.com:8000');

    expect(useSettingsStore.getState().serverUrl).toBe('http://new.example.com:8000');
    expect(useSettingsStore.getState().jwtToken).toBeNull();
    expect(useSettingsStore.getState().connectionStatus).toBe('idle');
    expect(useSettingsStore.getState().currentThinkingCapability).toBeNull();

    expect(useLLMProvidersStore.getState().initialized).toBe(false);
    expect(useLLMProvidersStore.getState().providers).toEqual([]);
    expect(useSessionStore.getState().currentSessionId).toBeNull();
    expect(useConversationStore.getState().sessions).toEqual({});
    expect(useComposerStore.getState().effortBySession).toEqual({});
    expect(secureStore.get('settings_jwt_token')).toBeUndefined();
    expect(secureStore.get('settings_connection_status')).toBeUndefined();
  });
});

describe('ServerConfig hydration', () => {
  test('keeps the current draft while hydration is still pending', () => {
    expect(getServerConfigInputValue('http://saved.example.com:8000', '', false)).toBe(
      'http://saved.example.com:8000',
    );
  });

  test('uses the hydrated serverUrl once settings are loaded', () => {
    expect(getServerConfigInputValue('http://typed.example.com:8000', 'http://saved.example.com:8000', true)).toBe(
      'http://saved.example.com:8000',
    );
  });
});
