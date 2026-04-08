import { apiClient } from './client';
import type { ThinkingCapability, ThinkingEffort } from '../types';
import { EFFORT_LEVELS_BY_CAPABILITY } from '../types';
import { useSettingsStore } from '../store/settings';
import { useComposerStore } from '../store/composer';

export interface LLMProviderRecord {
  id: string;
  name: string;
  provider_type: string;
  base_url: string | null;
  model: string;
  thinking_format: string | null;
  thinking_capability: ThinkingCapability | null;
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

export async function fetchProviders(): Promise<LLMProviderRecord[]> {
  const { data } = await apiClient.get<{ providers: LLMProviderRecord[] }>(
    '/api/v1/llm-providers',
  );
  return data.providers;
}

export async function syncCurrentThinkingCapability(
  onClamped?: (from: ThinkingEffort, to: ThinkingEffort) => void,
): Promise<void> {
  const providers = await fetchProviders();
  const defaultProvider = providers.find((p) => p.is_default) ?? null;
  const capability = defaultProvider?.thinking_capability ?? null;

  useSettingsStore.getState().setCurrentThinkingCapability(capability);

  if (capability) {
    const allowed = EFFORT_LEVELS_BY_CAPABILITY[capability];
    const changedFrom = useComposerStore.getState().clampAllToCapability(allowed);
    if (changedFrom && onClamped) {
      const after = useComposerStore.getState().lastUserChoice;
      onClamped(changedFrom, after);
    }
  }
}
