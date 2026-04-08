import { useEffect } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { ProviderForm } from '@/src/components/settings/ProviderForm';
import { SettingsScreenLayout } from '@/src/components/settings/SettingsScreenLayout';
import { useLLMProvidersStore } from '@/src/store/llmProviders';
import { useSettingsStore } from '@/src/store/settings';
import { useTheme } from '@/src/theme/ThemeContext';
import type { LLMProviderCreate } from '@/src/types';

export default function EditProviderScreen() {
  const { providerId } = useLocalSearchParams<{ providerId: string }>();
  const router = useRouter();
  const colors = useTheme();
  const jwtToken = useSettingsStore((state) => state.jwtToken);
  const { providers, initialized, loading, error, fetch, update } = useLLMProvidersStore();
  const resolvedProviderId = Array.isArray(providerId) ? providerId[0] : providerId;

  useEffect(() => {
    if (jwtToken && !initialized && !loading) {
      void fetch();
    }
  }, [fetch, initialized, jwtToken, loading]);

  async function handleSave(data: LLMProviderCreate) {
    if (!resolvedProviderId) {
      return;
    }
    await update(resolvedProviderId, data);
    router.replace('/settings/providers');
  }

  const provider = providers.find((item) => item.id === resolvedProviderId);

  return (
    <SettingsScreenLayout
      title="编辑 Provider"
      subtitle="更新模型提供商配置，并保持默认项设置清晰。"
    >
      {!jwtToken ? (
        <View style={[styles.feedbackCard, { backgroundColor: colors.cardBackground }]}>
          <Text style={[styles.feedbackTitle, { color: colors.text }]}>请先登录</Text>
          <Text style={[styles.feedbackText, { color: colors.textSecondary }]}>
            登录 Owner 账户后，再进入模型与 Provider 页面管理配置。
          </Text>
        </View>
      ) : error ? (
        <View style={[styles.feedbackCard, { backgroundColor: colors.cardBackground }]}>
          <Text style={[styles.feedbackTitle, { color: colors.text }]}>加载失败</Text>
          <Text style={[styles.feedbackText, { color: colors.error }]}>{error}</Text>
        </View>
      ) : !initialized || loading ? (
        <View style={[styles.feedbackCard, { backgroundColor: colors.cardBackground }]}>
          <Text style={[styles.feedbackText, { color: colors.textSecondary }]}>正在加载 Provider…</Text>
        </View>
      ) : provider ? (
        <ProviderForm
          initial={provider}
          onSave={handleSave}
          onCancel={() => router.back()}
        />
      ) : (
        <View style={[styles.feedbackCard, { backgroundColor: colors.cardBackground }]}>
          <Text style={[styles.feedbackTitle, { color: colors.text }]}>未找到 Provider</Text>
          <Text style={[styles.feedbackText, { color: colors.textSecondary }]}>
            该 Provider 可能已被删除，请返回列表页重新确认。
          </Text>
        </View>
      )}
    </SettingsScreenLayout>
  );
}

const styles = StyleSheet.create({
  feedbackCard: {
    borderRadius: 14,
    padding: 18,
  },
  feedbackTitle: {
    fontSize: 17,
    fontWeight: '600',
  },
  feedbackText: {
    marginTop: 8,
    fontSize: 14,
    lineHeight: 20,
  },
});
