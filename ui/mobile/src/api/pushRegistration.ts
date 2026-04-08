type NotificationPermissionStatus = {
  status: 'granted' | 'denied' | 'undetermined';
};

type NotificationTokenResponse = {
  data: string;
};

interface NotificationsApi {
  requestPermissionsAsync: () => Promise<NotificationPermissionStatus>;
  getDevicePushTokenAsync: () => Promise<NotificationTokenResponse>;
}

interface RegisterDevicePushTokenInput {
  notifications: NotificationsApi;
  registerDevice: (token: string) => Promise<unknown>;
  onError?: (error: unknown) => void;
}

export async function registerDevicePushToken({
  notifications,
  registerDevice,
  onError,
}: RegisterDevicePushTokenInput): Promise<'registered' | 'skipped-permission' | 'skipped-error'> {
  const { status } = await notifications.requestPermissionsAsync();
  if (status !== 'granted') {
    return 'skipped-permission';
  }

  try {
    const token = (await notifications.getDevicePushTokenAsync()).data;
    await registerDevice(token);
    return 'registered';
  } catch (error) {
    onError?.(error);
    return 'skipped-error';
  }
}
