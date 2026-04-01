import { useState } from 'react';
import { View, StyleSheet } from 'react-native';
import { useAgentsStore } from '../../../src/store/agents';
import { useAgents } from '../../../src/hooks/useAgents';
import { sendAgentCommand, cancelAgent } from '../../../src/api/agents';
import { Sidebar } from '../../../src/components/common/Sidebar';
import { EmptyState } from '../../../src/components/common/EmptyState';
import { AgentSidebar } from '../../../src/components/subagents/AgentSidebar';
import { MessageList } from '../../../src/components/chat/MessageList';
import { MessageInput } from '../../../src/components/chat/MessageInput';

export default function SubAgentsScreen() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { currentAgentId, streamingOutput, isWorking, setCurrentAgent } = useAgentsStore();
  const { data: agents = [] } = useAgents();

  async function handleSend(text: string) {
    if (!currentAgentId) return;
    await sendAgentCommand(currentAgentId, text);
  }

  async function handleStop() {
    if (!currentAgentId) return;
    await cancelAgent(currentAgentId);
  }

  return (
    <View style={styles.container}>
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

const styles = StyleSheet.create({ container: { flex: 1 } });
