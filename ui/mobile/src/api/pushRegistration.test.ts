import { describe, expect, it, vi } from 'vitest';
import { registerDevicePushToken } from './pushRegistration';

describe('registerDevicePushToken', () => {
  it('returns early when notification permission is not granted', async () => {
    const notifications = {
      requestPermissionsAsync: vi.fn(async () => ({ status: 'denied' as const })),
      getDevicePushTokenAsync: vi.fn(),
    };
    const registerDevice = vi.fn();

    const result = await registerDevicePushToken({ notifications, registerDevice });

    expect(result).toBe('skipped-permission');
    expect(notifications.getDevicePushTokenAsync).not.toHaveBeenCalled();
    expect(registerDevice).not.toHaveBeenCalled();
  });

  it('swallows native token errors and reports a skipped registration', async () => {
    const notifications = {
      requestPermissionsAsync: vi.fn(async () => ({ status: 'granted' as const })),
      getDevicePushTokenAsync: vi.fn(async () => {
        throw new Error('firebase missing');
      }),
    };
    const registerDevice = vi.fn();
    const onError = vi.fn();

    const result = await registerDevicePushToken({ notifications, registerDevice, onError });

    expect(result).toBe('skipped-error');
    expect(registerDevice).not.toHaveBeenCalled();
    expect(onError).toHaveBeenCalledTimes(1);
  });
});
