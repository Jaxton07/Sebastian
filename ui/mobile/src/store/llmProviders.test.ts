import { beforeEach, describe, expect, test, vi } from 'vitest';
import { useLLMProvidersStore } from './llmProviders';
import type { LLMProvider } from '../types';
import {
  createLLMProvider,
  deleteLLMProvider,
  getLLMProviders,
  updateLLMProvider,
} from '../api/llmProviders';

vi.mock('../api/llmProviders', () => ({
  getLLMProviders: vi.fn(async () => []),
  createLLMProvider: vi.fn(),
  updateLLMProvider: vi.fn(),
  deleteLLMProvider: vi.fn(),
}));

function makeProvider(overrides: Partial<LLMProvider>): LLMProvider {
  return {
    id: overrides.id ?? 'provider-1',
    name: overrides.name ?? 'Claude Home',
    provider_type: overrides.provider_type ?? 'anthropic',
    base_url: overrides.base_url ?? null,
    api_key: overrides.api_key ?? 'secret',
    model: overrides.model ?? 'claude-opus-4-6',
    thinking_format: overrides.thinking_format ?? null,
    thinking_capability: overrides.thinking_capability ?? 'adaptive',
    is_default: overrides.is_default ?? false,
    created_at: overrides.created_at ?? '2026-04-08T00:00:00.000Z',
    updated_at: overrides.updated_at ?? '2026-04-08T00:00:00.000Z',
  };
}

beforeEach(() => {
  vi.mocked(getLLMProviders).mockReset();
  vi.mocked(createLLMProvider).mockReset();
  vi.mocked(updateLLMProvider).mockReset();
  vi.mocked(deleteLLMProvider).mockReset();

  useLLMProvidersStore.setState({
    providers: [],
    loading: false,
    initialized: false,
    error: null,
  });
});

describe('useLLMProvidersStore', () => {
  test('create unsets previous default locally when new provider is default', async () => {
    useLLMProvidersStore.setState({
      providers: [makeProvider({ id: 'provider-1', is_default: true })],
      loading: false,
      initialized: true,
      error: null,
    });

    vi.mocked(createLLMProvider).mockResolvedValue(
      makeProvider({
        id: 'provider-2',
        name: 'OpenAI Work',
        provider_type: 'openai',
        model: 'gpt-4o',
        is_default: true,
      }),
    );

    await useLLMProvidersStore.getState().create({
      name: 'OpenAI Work',
      provider_type: 'openai',
      api_key: 'sk-second',
      model: 'gpt-4o',
      base_url: 'https://api.openai.com/v1',
      is_default: true,
    });

    expect(useLLMProvidersStore.getState().providers).toMatchObject([
      { id: 'provider-1', is_default: false },
      { id: 'provider-2', is_default: true },
    ]);
  });

  test('update unsets previous default locally when provider becomes default', async () => {
    useLLMProvidersStore.setState({
      providers: [
        makeProvider({ id: 'provider-1', is_default: true }),
        makeProvider({
          id: 'provider-2',
          name: 'OpenAI Work',
          provider_type: 'openai',
          model: 'gpt-4o',
          is_default: false,
        }),
      ],
      loading: false,
      initialized: true,
      error: null,
    });

    vi.mocked(updateLLMProvider).mockResolvedValue(
      makeProvider({
        id: 'provider-2',
        name: 'OpenAI Work',
        provider_type: 'openai',
        model: 'gpt-4o',
        is_default: true,
      }),
    );

    await useLLMProvidersStore.getState().update('provider-2', { is_default: true });

    expect(useLLMProvidersStore.getState().providers).toMatchObject([
      { id: 'provider-1', is_default: false },
      { id: 'provider-2', is_default: true },
    ]);
  });
});
