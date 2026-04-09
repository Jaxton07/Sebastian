import { useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { deleteSession, getAgentSessions } from '../../src/api/sessions';
import { SessionList } from '../../src/components/subagents/SessionList';
import { BackButton } from '../../src/components/common/BackButton';
import { NewChatFAB } from '../../src/components/common/NewChatFAB';
import { ConfirmDialog } from '../../src/components/common/ConfirmDialog';
import { useTheme } from '../../src/theme/ThemeContext';
import type { SessionMeta } from '../../src/types';

export default function AgentSessionsScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const queryClient = useQueryClient();
  const colors = useTheme();
  const { agentId, name } = useLocalSearchParams<{ agentId: string; name?: string }>();
  const agentName = (Array.isArray(name) ? name[0] : name) ?? 'Sub-Agent';
  const normalizedAgentId = (Array.isArray(agentId) ? agentId[0] : agentId) ?? '';
  const [deleteTarget, setDeleteTarget] = useState<SessionMeta | null>(null);

  const { data: sessions = [] } = useQuery({
    queryKey: ['agent-sessions', normalizedAgentId],
    queryFn: () => getAgentSessions(normalizedAgentId),
    enabled: !!normalizedAgentId,
  });

  const { mutate: doDelete } = useMutation({
    mutationFn: (session: SessionMeta) => deleteSession(session.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agent-sessions', normalizedAgentId] });
    },
  });

  function handleSelectSession(session: SessionMeta) {
    router.push(`/subagents/session/${session.id}?agent=${session.agent}`);
  }

  function handleNewChat() {
    router.push(`/subagents/session/new?agent=${normalizedAgentId}`);
  }

  return (
    <View style={[styles.container, { backgroundColor: colors.secondaryBackground }]}>
      <View
        style={[
          styles.header,
          { paddingTop: insets.top, backgroundColor: colors.background, borderBottomColor: colors.borderLight },
        ]}
      >
        <BackButton style={styles.back} />
        <Text style={[styles.headerTitle, { color: colors.text }]} numberOfLines={1}>
          {agentName}
        </Text>
        <View style={styles.back} />
      </View>
      <SessionList sessions={sessions} onSelect={handleSelectSession} onDelete={setDeleteTarget} />
      <ConfirmDialog
        visible={deleteTarget !== null}
        title="删除对话"
        message="确认删除这条对话记录？"
        confirmText="删除"
        destructive
        onCancel={() => setDeleteTarget(null)}
        onConfirm={() => {
          if (deleteTarget) doDelete(deleteTarget);
          setDeleteTarget(null);
        }}
      />
      <NewChatFAB
        label="新对话"
        onPress={handleNewChat}
        style={styles.fab}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  header: {
    minHeight: 48,
    borderBottomWidth: 1,
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
  },
  back: { width: 72 },
  headerTitle: {
    flex: 1,
    fontSize: 16,
    fontWeight: '600',
    textAlign: 'center',
  },
  fab: {
    position: 'absolute',
    bottom: 24,
    right: 16,
  },
});
