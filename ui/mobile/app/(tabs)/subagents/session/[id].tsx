import { useCallback, useState } from 'react';
import { Alert, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import {
  getSessionDetail,
  getSessionTasks,
  sendTurnToSession,
} from '../../../../src/api/sessions';
import { MessageInput } from '../../../../src/components/chat/MessageInput';
import { MessageList } from '../../../../src/components/chat/MessageList';
import { SessionDetailView } from '../../../../src/components/subagents/SessionDetailView';

type Tab = 'messages' | 'tasks';

export default function SessionDetailScreen() {
  const { id, agent = 'sebastian' } = useLocalSearchParams<{
    id: string;
    agent: string;
  }>();
  const sessionId = (Array.isArray(id) ? id[0] : id) ?? '';
  const agentName = (Array.isArray(agent) ? agent[0] : agent) ?? 'sebastian';
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<Tab>('messages');
  const [sending, setSending] = useState(false);

  const { data: detail } = useQuery({
    queryKey: ['session-detail', sessionId, agentName],
    queryFn: () => getSessionDetail(sessionId, agentName),
    enabled: !!sessionId,
  });

  const { data: tasks = [] } = useQuery({
    queryKey: ['session-tasks', sessionId, agentName],
    queryFn: () => getSessionTasks(sessionId, agentName),
    enabled: !!sessionId,
  });

  const handleSend = useCallback(
    async (text: string) => {
      if (!id) return;
      setSending(true);
      try {
        await sendTurnToSession(sessionId, text, agentName);
        queryClient.invalidateQueries({
          queryKey: ['session-detail', sessionId, agentName],
        });
      } catch {
        Alert.alert('发送失败，请重试');
      } finally {
        setSending(false);
      }
    },
    [agentName, queryClient, sessionId],
  );

  const messages =
    detail?.messages.map((message, index) => ({
      id: String(index),
      sessionId,
      role: message.role,
      content: message.content,
      createdAt: message.ts ?? '',
    })) ?? [];

  return (
    <View style={styles.container}>
      <View style={[styles.header, { paddingTop: insets.top }]}>
        <TouchableOpacity style={styles.back} onPress={() => router.back()}>
          <Text style={styles.backText}>‹ 返回</Text>
        </TouchableOpacity>
        <Text style={styles.title} numberOfLines={1}>
          {detail?.session.title ?? '会话详情'}
        </Text>
      </View>
      <View style={styles.tabs}>
        <TouchableOpacity
          style={[styles.tab, tab === 'messages' && styles.tabActive]}
          onPress={() => setTab('messages')}
        >
          <Text
            style={[styles.tabText, tab === 'messages' && styles.tabTextActive]}
          >
            消息
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.tab, tab === 'tasks' && styles.tabActive]}
          onPress={() => setTab('tasks')}
        >
          <Text style={[styles.tabText, tab === 'tasks' && styles.tabTextActive]}>
            任务 {tasks.length > 0 ? `(${tasks.length})` : ''}
          </Text>
        </TouchableOpacity>
      </View>
      <View style={styles.body}>
        {tab === 'messages' ? (
          <MessageList messages={messages} streamingContent="" />
        ) : (
          <SessionDetailView tasks={tasks} />
        )}
      </View>
      <MessageInput isWorking={sending} onSend={handleSend} onStop={() => {}} />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F5F5F5' },
  header: {
    backgroundColor: '#FFFFFF',
    borderBottomWidth: 1,
    borderBottomColor: '#E0E0E0',
    flexDirection: 'row',
    alignItems: 'center',
    minHeight: 48,
    paddingHorizontal: 12,
  },
  back: { padding: 8, marginRight: 4 },
  backText: { fontSize: 16, color: '#007AFF' },
  title: { flex: 1, fontSize: 15, fontWeight: '600', color: '#111111' },
  tabs: {
    flexDirection: 'row',
    backgroundColor: '#FFFFFF',
    borderBottomWidth: 1,
    borderBottomColor: '#E0E0E0',
  },
  tab: { flex: 1, paddingVertical: 10, alignItems: 'center' },
  tabActive: { borderBottomWidth: 2, borderBottomColor: '#007AFF' },
  tabText: { fontSize: 14, color: '#888888' },
  tabTextActive: { color: '#007AFF', fontWeight: '600' },
  body: { flex: 1 },
});
