import { useEffect, type ReactNode } from 'react';
import { AppState } from 'react-native';
import * as Notifications from 'expo-notifications';
import { router, Stack } from 'expo-router';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { StyleSheet } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { KeyboardProvider } from 'react-native-keyboard-controller';
import { getApprovals, registerDevice } from '@/src/api/approvals';
import { syncCurrentThinkingCapability } from '@/src/api/llm';
import { ApprovalModal } from '@/src/components/common/ApprovalModal';
import { useSSE } from '@/src/hooks/useSSE';
import { useApprovalStore } from '@/src/store/approval';
import { useSettingsStore } from '@/src/store/settings';
import { ThemeProvider } from '@/src/theme/ThemeContext';

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 2, staleTime: 30_000 } },
});

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: false,
    shouldShowBanner: true,
    shouldShowList: true,
  }),
});

function AppInit({ children }: { children: ReactNode }) {
  const { load, jwtToken } = useSettingsStore();
  const { pending, grant, deny, setPending } = useApprovalStore();

  async function hydratePendingApproval(): Promise<void> {
    if (!jwtToken) {
      setPending(null);
      return;
    }
    const approvals = await getApprovals().catch(() => []);
    setPending(approvals[0] ?? null);
  }

  useSSE({
    onApprovalRequired: (approval) => setPending(approval),
  });

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!jwtToken) return;
    void (async () => {
      const { status } = await Notifications.requestPermissionsAsync();
      if (status !== 'granted') return;
      const token = (await Notifications.getDevicePushTokenAsync()).data;
      await registerDevice(token).catch(() => {});
    })();
  }, [jwtToken]);

  useEffect(() => {
    void hydratePendingApproval();
  }, [jwtToken]);

  useEffect(() => {
    if (!jwtToken) return;
    void syncCurrentThinkingCapability().catch(() => {
      // 拉失败时 currentThinkingCapability 保持 null，UI 按 disabled 兜底
    });
  }, [jwtToken]);

  useEffect(() => {
    const appStateSubscription = AppState.addEventListener('change', (state) => {
      if (state === 'active') {
        void hydratePendingApproval();
      }
    });
    const subscription = Notifications.addNotificationResponseReceivedListener(
      (response) => {
        const data = response.notification.request.content.data as Record<string, string>;
        if (
          data?.type === 'approval.required' ||
          data?.type === 'user.approval_requested'
        ) {
          router.push('/');
        } else if (data?.type?.startsWith('task.')) {
          router.push('/subagents');
        }
      },
    );
    return () => {
      appStateSubscription.remove();
      subscription.remove();
    };
  }, [jwtToken]);

  return (
    <ThemeProvider>
      {children}
      <ApprovalModal approval={pending} onGrant={grant} onDeny={deny} />
    </ThemeProvider>
  );
}

export default function RootLayout() {
  return (
    <SafeAreaProvider>
      <GestureHandlerRootView style={styles.root}>
        <QueryClientProvider client={queryClient}>
          <KeyboardProvider>
            <AppInit>
              <Stack screenOptions={{ headerShown: false }} />
            </AppInit>
          </KeyboardProvider>
        </QueryClientProvider>
      </GestureHandlerRootView>
    </SafeAreaProvider>
  );
}

const styles = StyleSheet.create({ root: { flex: 1 } });
