import { describe, expect, it } from 'vitest';
import {
  getAdvancedSummary,
  getAppearanceSummary,
  getConnectionSummary,
  getProviderSummary,
} from './settingsSummary';

describe('settingsSummary', () => {
  it('returns loading summary before providers initialize', () => {
    expect(getProviderSummary({
      providers: [],
      isLoggedIn: true,
      initialized: false,
      isLoading: false,
      error: null,
    })).toEqual({
      title: '尚未读取',
      subtitle: '等待读取 Provider…',
    });
  });

  it('returns loading summary while providers are fetching', () => {
    expect(getProviderSummary({
      providers: [],
      isLoggedIn: true,
      initialized: true,
      isLoading: true,
      error: null,
    })).toEqual({
      title: '正在加载',
      subtitle: '正在加载 Provider…',
    });
  });

  it('prefers loading summary when fetch has started before initialization completes', () => {
    expect(getProviderSummary({
      providers: [],
      isLoggedIn: true,
      initialized: false,
      isLoading: true,
      error: null,
    })).toEqual({
      title: '正在加载',
      subtitle: '正在加载 Provider…',
    });
  });

  it('returns unconfigured provider summary when list is empty', () => {
    expect(getProviderSummary({
      providers: [],
      isLoggedIn: true,
      initialized: true,
      isLoading: false,
      error: null,
    })).toEqual({
      title: '未配置',
      subtitle: '尚未添加 Provider',
    });
  });

  it('returns fallback summary when providers exist without default', () => {
    expect(getProviderSummary({
      providers: [{ provider_type: 'anthropic', model: 'claude', is_default: false }],
      isLoggedIn: true,
      initialized: true,
      isLoading: false,
      error: null,
    })).toEqual({
      title: '未设默认',
      subtitle: '1 个 Provider · 请选择默认项',
    });
  });

  it('returns default provider model and type when a default exists', () => {
    expect(getProviderSummary({
      providers: [
        { provider_type: 'anthropic', model: 'claude-opus-4-6', is_default: true },
        { provider_type: 'openai', model: 'gpt-4o', is_default: false },
      ],
      isLoggedIn: true,
      initialized: true,
      isLoading: false,
      error: null,
    })).toEqual({
      title: 'claude-opus-4-6',
      subtitle: 'anthropic · 2 个 Provider',
    });
  });

  it('returns provider load error summary when fetch failed', () => {
    expect(getProviderSummary({
      providers: [],
      isLoggedIn: true,
      initialized: true,
      isLoading: false,
      error: 'boom',
    })).toEqual({
      title: '加载失败',
      subtitle: 'Provider 加载失败',
    });
  });

  it('returns logged-out summary without pretending providers are loading', () => {
    expect(getProviderSummary({
      providers: [],
      isLoggedIn: false,
      initialized: false,
      isLoading: false,
      error: null,
    })).toEqual({
      title: '未登录',
      subtitle: '登录后管理 Provider',
    });
  });

  it('returns connection summary for logged in users', () => {
    expect(getConnectionSummary({
      serverUrl: 'http://10.0.2.2:8000',
      connectionStatus: 'ok',
      isLoggedIn: true,
    })).toEqual({
      title: '已连接',
      subtitle: 'http://10.0.2.2:8000 · Owner 已登录',
    });
  });

  it('returns connection summary for logged out users', () => {
    expect(getConnectionSummary({
      serverUrl: 'http://192.168.1.9:8000',
      connectionStatus: 'idle',
      isLoggedIn: false,
    })).toEqual({
      title: '未测试',
      subtitle: 'http://192.168.1.9:8000 · 未登录',
    });
  });

  it('returns appearance summary for system dark mode', () => {
    expect(getAppearanceSummary({
      themeMode: 'system',
      isDark: true,
    })).toEqual({
      title: '跟随系统',
      subtitle: '当前生效：深色模式',
    });
  });

  it('returns advanced summary for logged in users', () => {
    expect(getAdvancedSummary({ isLoggedIn: true })).toEqual({
      title: '2 项设置',
      subtitle: 'Memory · 调试日志',
    });
  });

  it('returns advanced summary for logged out users', () => {
    expect(getAdvancedSummary({ isLoggedIn: false })).toEqual({
      title: '1 项设置',
      subtitle: 'Memory',
    });
  });
});
