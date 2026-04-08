import { StyleSheet, Text, View } from 'react-native';
import { useRouter } from 'expo-router';
import { ProviderForm } from '@/src/components/settings/ProviderForm';
import { SettingsScreenLayout } from '@/src/components/settings/SettingsScreenLayout';
import { useLLMProvidersStore } from '@/src/store/llmProviders';
import { useSettingsStore } from '@/src/store/settings';
import { useTheme } from '@/src/theme/ThemeContext';
import type { LLMProviderCreate } from '@/src/types';

export default function NewProviderScreen() {
  const router = useRouter();
  const colors = useTheme();
  const jwtToken = useSettingsStore((state) => state.jwtToken);
  const create = useLLMProvidersStore((state) => state.create);

  async function handleSave(data: LLMProviderCreate) {
    await create(data);
    router.replace('/settings/providers');
  }

  return (
    <SettingsScreenLayout
      title="添加 Provider"
      subtitle="新增一个可用模型提供商，并决定是否设为默认。"
    >
      {jwtToken ? (
        <ProviderForm onSave={handleSave} onCancel={() => router.back()} />
      ) : (
        <View style={[styles.feedbackCard, { backgroundColor: colors.cardBackground }]}>
          <Text style={[styles.feedbackTitle, { color: colors.text }]}>请先登录</Text>
          <Text style={[styles.feedbackText, { color: colors.textSecondary }]}>
            登录 Owner 账户后，才能新增 Provider。
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
