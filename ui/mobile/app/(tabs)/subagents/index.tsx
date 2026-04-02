import { useState } from 'react';
import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { useRouter } from 'expo-router';
import { useQuery } from '@tanstack/react-query';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { getAgentSessions } from '../../../src/api/sessions';
import { EmptyState } from '../../../src/components/common/EmptyState';
import { Sidebar } from '../../../src/components/common/Sidebar';
import { AgentSidebar } from '../../../src/components/subagents/AgentSidebar';
import { SessionList } from '../../../src/components/subagents/SessionList';
import { useAgents } from '../../../src/hooks/useAgents';
import { useAgentsStore } from '../../../src/store/agents';
import type { SessionMeta } from '../../../src/types';

export default function SubAgentsScreen() {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { currentAgentId, setCurrentAgent } = useAgentsStore();
  const { data: agents = [] } = useAgents();

  const selectedAgent = agents.find((agent) => agent.id === currentAgentId);

  const { data: sessions = [] } = useQuery({
    queryKey: ['agent-sessions', currentAgentId],
    queryFn: () => getAgentSessions(selectedAgent?.name ?? ''),
    enabled: !!currentAgentId && !!selectedAgent,
  });

  function handleSelectSession(session: SessionMeta) {
    router.push(`/(tabs)/subagents/session/${session.id}?agent=${session.agent}`);
  }

  return (
    <View style={styles.container}>
      <View style={[styles.header, { paddingTop: insets.top }]}>
        <TouchableOpacity
          style={styles.menuButton}
          onPress={() => setSidebarOpen(true)}
        >
          <Text style={styles.menuIcon}>☰</Text>
        </TouchableOpacity>
        <Text style={styles.headerTitle}>
          {selectedAgent ? selectedAgent.name : 'Sub-Agents'}
        </Text>
      </View>
      {!currentAgentId ? (
        <EmptyState message="从左侧选择一个 Sub-Agent 查看会话" />
      ) : (
        <SessionList sessions={sessions} onSelect={handleSelectSession} />
      )}
      <Sidebar visible={sidebarOpen} onClose={() => setSidebarOpen(false)}>
        <AgentSidebar
          agents={agents}
          currentAgentId={currentAgentId}
          onSelect={(id) => {
            setCurrentAgent(id);
            setSidebarOpen(false);
          }}
        />
      </Sidebar>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F5F5F5' },
  header: {
    minHeight: 48,
    backgroundColor: '#FFFFFF',
    borderBottomWidth: 1,
    borderBottomColor: '#E0E0E0',
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
  },
  menuButton: { padding: 8 },
  menuIcon: { fontSize: 20 },
  headerTitle: {
    flex: 1,
    textAlign: 'center',
    fontSize: 16,
    fontWeight: '600',
    marginRight: 36,
  },
});
