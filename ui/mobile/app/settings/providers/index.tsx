import { useEffect } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { ProviderListSection } from '@/src/components/settings/ProviderListSection';
import { SettingsScreenLayout } from '@/src/components/settings/SettingsScreenLayout';
import { useLLMProvidersStore } from '@/src/store/llmProviders';
import { useSettingsStore } from '@/src/store/settings';
import { useTheme } from '@/src/theme/ThemeContext';

export default function ProvidersSettingsScreen() {
  const colors = useTheme();
  const jwtToken = useSettingsStore((state) => state.jwtToken);
  const { fetch, initialized, loading } = useLLMProvidersStore();

  useEffect(() => {
    if (jwtToken && !loading && !initialized) {
      void fetch();
    }
  }, [fetch, initialized, jwtToken, loading]);

  return (
    <SettingsScreenLayout
      title="模型与 Provider"
      subtitle="管理默认模型与各 Provider 配置。"
    >
      {jwtToken ? (
        <ProviderListSection />
      ) : (
        <View style={[styles.feedbackCard, { backgroundColor: colors.cardBackground }]}>
          <Text style={[styles.feedbackTitle, { color: colors.text }]}>请先登录</Text>
          <Text style={[styles.feedbackText, { color: colors.textSecondary }]}>
            登录 Owner 账户后，再管理 Provider 和默认模型。
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
