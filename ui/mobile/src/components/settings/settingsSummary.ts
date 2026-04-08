export type ConnectionStatus = 'idle' | 'ok' | 'fail';

function formatServerLabel(serverUrl: string): string {
  return serverUrl.trim() || '未设置 Server URL';
}

export function getConnectionSummary(input: {
  serverUrl: string;
  connectionStatus: ConnectionStatus;
  isLoggedIn: boolean;
}): { title: string; subtitle: string } {
  const titleMap: Record<ConnectionStatus, string> = {
    idle: '未测试',
    ok: '已连接',
    fail: '连接失败',
  };

  return {
    title: titleMap[input.connectionStatus],
    subtitle: `${formatServerLabel(input.serverUrl)} · ${input.isLoggedIn ? 'Owner 已登录' : '未登录'}`,
  };
}

export function getProviderSummary(input: {
  providers: Array<{ provider_type: string; model: string; is_default: boolean }>;
  isLoggedIn: boolean;
  initialized: boolean;
  isLoading: boolean;
  error: string | null;
}): { title: string; subtitle: string } {
  if (!input.isLoggedIn) {
    return {
      title: '未登录',
      subtitle: '登录后管理 Provider',
    };
  }

  if (input.error) {
    return {
      title: '加载失败',
      subtitle: 'Provider 加载失败',
    };
  }

  if (input.isLoading) {
    return {
      title: '正在加载',
      subtitle: '正在加载 Provider…',
    };
  }

  if (!input.initialized) {
    return {
      title: '尚未读取',
      subtitle: '等待读取 Provider…',
    };
  }

  if (input.providers.length === 0) {
    return {
      title: '未配置',
      subtitle: '尚未添加 Provider',
    };
  }

  const defaultProvider = input.providers.find((provider) => provider.is_default) ?? null;
  if (!defaultProvider) {
    return {
      title: '未设默认',
      subtitle: `${input.providers.length} 个 Provider · 请选择默认项`,
    };
  }

  return {
    title: defaultProvider.model,
    subtitle: `${defaultProvider.provider_type} · ${input.providers.length} 个 Provider`,
  };
}

export function getAppearanceSummary(input: {
  themeMode: 'system' | 'light' | 'dark';
  isDark: boolean;
}): { title: string; subtitle: string } {
  if (input.themeMode === 'system') {
    return {
      title: '跟随系统',
      subtitle: `当前生效：${input.isDark ? '深色模式' : '浅色模式'}`,
    };
  }

  return {
    title: input.themeMode === 'dark' ? '深色模式' : '浅色模式',
    subtitle: `当前生效：${input.themeMode === 'dark' ? '深色模式' : '浅色模式'}`,
  };
}

export function getAdvancedSummary(input: {
  isLoggedIn: boolean;
}): { title: string; subtitle: string } {
  return input.isLoggedIn
    ? { title: '2 项设置', subtitle: 'Memory · 调试日志' }
    : { title: '1 项设置', subtitle: 'Memory' };
}
