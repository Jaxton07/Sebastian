import { useEffect } from 'react';
import { router } from 'expo-router';
import { checkHealth, logout } from '@/src/api/auth';
import { SettingsCategoryCard } from '@/src/components/settings/SettingsCategoryCard';
import { SettingsScreenLayout } from '@/src/components/settings/SettingsScreenLayout';
import {
  getAdvancedSummary,
  getAppearanceSummary,
  getConnectionSummary,
  getProviderSummary,
} from '@/src/components/settings/settingsSummary';
import { useLLMProvidersStore } from '@/src/store/llmProviders';
import { useSettingsStore } from '@/src/store/settings';
import { useIsDark } from '@/src/theme/ThemeContext';

export default function SettingsScreen() {
  const {
    connectionStatus,
    isLoaded,
    jwtToken,
    serverUrl,
    setConnectionStatus,
    setJwtToken,
    themeMode,
  } = useSettingsStore();
  const { providers, loading, initialized, error, fetch } = useLLMProvidersStore();
  const isDark = useIsDark();

  useEffect(() => {
    if (jwtToken && !loading && !initialized) {
      void fetch();
    }
  }, [fetch, initialized, jwtToken, loading]);

  async function handleTestConnection() {
    const ok = await checkHealth();
    await setConnectionStatus(ok ? 'ok' : 'fail');
  }

  async function handleLogout() {
    try {
      await logout();
    } catch {
      // allow local logout even if server call fails
    }
    await setJwtToken(null);
  }

  const connectionSummary = getConnectionSummary({
    serverUrl,
    connectionStatus,
    isLoggedIn: !!jwtToken,
  });
  const providerSummary = getProviderSummary({
    providers,
    isLoggedIn: !!jwtToken,
    initialized,
    isLoading: loading,
    error,
  });
  const appearanceSummary = getAppearanceSummary({ themeMode, isDark });
  const advancedSummary = getAdvancedSummary({ isLoggedIn: !!jwtToken });

  return (
    <SettingsScreenLayout
      title="设置"
      subtitle="查看当前状态，并进入对应分类完成详细配置。"
    >
      <SettingsCategoryCard
        label="Connection"
        title={isLoaded ? connectionSummary.title : '正在加载'}
        subtitle={isLoaded ? connectionSummary.subtitle : '正在读取本地设置…'}
        onPress={() => router.push('/settings/connection')}
        actions={[
          { key: 'test-connection', label: '测试连接', onPress: handleTestConnection },
          ...(jwtToken
            ? [{ key: 'logout', label: '退出登录', onPress: handleLogout, tone: 'destructive' as const }]
            : []),
        ]}
      />

      <SettingsCategoryCard
        label="Models"
        title={isLoaded ? providerSummary.title : '正在加载'}
        subtitle={isLoaded ? providerSummary.subtitle : '正在读取 Provider 状态…'}
        onPress={() => router.push('/settings/providers')}
      />

      <SettingsCategoryCard
        label="Appearance"
        title={appearanceSummary.title}
        subtitle={appearanceSummary.subtitle}
        onPress={() => router.push('/settings/appearance')}
      />

      <SettingsCategoryCard
        label="Advanced"
        title={advancedSummary.title}
        subtitle={advancedSummary.subtitle}
        onPress={() => router.push('/settings/advanced')}
      />
    </SettingsScreenLayout>
  );
}
