import { useState } from 'react';
import { View, StyleSheet, Alert, TouchableOpacity, Text } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useAgentsStore } from '../../../src/store/agents';
import { useAgents } from '../../../src/hooks/useAgents';
import { sendAgentCommand, cancelAgent } from '../../../src/api/agents';
import { Sidebar } from '../../../src/components/common/Sidebar';
import { EmptyState } from '../../../src/components/common/EmptyState';
import { AgentSidebar } from '../../../src/components/subagents/AgentSidebar';
import { MessageList } from '../../../src/components/chat/MessageList';
import { MessageInput } from '../../../src/components/chat/MessageInput';

export default function SubAgentsScreen() {
  const insets = useSafeAreaInsets();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { currentAgentId, streamingOutput, isWorking, setCurrentAgent } = useAgentsStore();
  const { data: agents = [] } = useAgents();

  async function handleSend(text: string) {
    if (!currentAgentId) return;
    try {
      await sendAgentCommand(currentAgentId, text);
    } catch {
      Alert.alert('发送失败，请重试');
    }
  }

  async function handleStop() {
    if (!currentAgentId) return;
    await cancelAgent(currentAgentId);
  }

  return (
    <View style={styles.container}>
      <View style={[styles.header, { paddingTop: insets.top }]}>
        <TouchableOpacity style={styles.menuButton} onPress={() => setSidebarOpen(true)}>
          <Text style={styles.menuIcon}>☰</Text>
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Sub-Agents</Text>
      </View>
      {!currentAgentId ? (
        <EmptyState message="从左侧选择一个 Sub-Agent 查看输出" />
      ) : (
        <MessageList messages={[]} streamingContent={streamingOutput} />
      )}
      <MessageInput isWorking={isWorking} onSend={handleSend} onStop={handleStop} />
      <Sidebar visible={sidebarOpen} onClose={() => setSidebarOpen(false)}>
        <AgentSidebar
          agents={agents}
          currentAgentId={currentAgentId}
          onSelect={(id) => { setCurrentAgent(id); setSidebarOpen(false); }}
        />
      </Sidebar>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  header: {
    minHeight: 48,
    backgroundColor: '#ffffff',
    borderBottomWidth: 1,
    borderBottomColor: '#e0e0e0',
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
  },
  menuButton: {
    padding: 8,
  },
  menuIcon: {
    fontSize: 20,
  },
  headerTitle: {
    flex: 1,
    textAlign: 'center',
    fontSize: 16,
    fontWeight: '600',
    marginRight: 36,
  },
});
