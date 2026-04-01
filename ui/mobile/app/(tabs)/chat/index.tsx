import { useState } from 'react';
import { View, StyleSheet } from 'react-native';
import { useSessionStore } from '../../../src/store/session';
import { useMessages } from '../../../src/hooks/useMessages';
import { useSessions } from '../../../src/hooks/useSessions';
import { useSSE } from '../../../src/hooks/useSSE';
import { sendTurn, cancelTurn } from '../../../src/api/turns';
import { useQueryClient } from '@tanstack/react-query';
import { Sidebar } from '../../../src/components/common/Sidebar';
import { EmptyState } from '../../../src/components/common/EmptyState';
import { ChatSidebar } from '../../../src/components/chat/ChatSidebar';
import { MessageList } from '../../../src/components/chat/MessageList';
import { MessageInput } from '../../../src/components/chat/MessageInput';

export default function ChatScreen() {
  useSSE();
  const queryClient = useQueryClient();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { currentSessionId, draftSession, streamingMessage, setCurrentSession, startDraft, persistSession } = useSessionStore();
  const { data: sessions = [] } = useSessions();
  const { data: messages = [] } = useMessages(currentSessionId);
  const isWorking = !!streamingMessage;

  async function handleSend(text: string) {
    const { sessionId } = await sendTurn(currentSessionId, text);
    if (!currentSessionId) {
      persistSession({ id: sessionId, title: text.slice(0, 30), createdAt: new Date().toISOString() });
    }
    queryClient.invalidateQueries({ queryKey: ['messages', sessionId] });
  }

  async function handleStop() {
    if (currentSessionId) await cancelTurn(currentSessionId);
  }

  const isEmpty = !currentSessionId && !draftSession;

  return (
    <View style={styles.container}>
      {isEmpty ? (
        <EmptyState message="发送消息开始对话" />
      ) : (
        <MessageList messages={messages} streamingContent={streamingMessage} />
      )}
      <MessageInput isWorking={isWorking} onSend={handleSend} onStop={handleStop} />
      <Sidebar visible={sidebarOpen} onClose={() => setSidebarOpen(false)}>
        <ChatSidebar
          sessions={sessions}
          currentSessionId={currentSessionId}
          draftSession={draftSession}
          onSelect={(id) => { setCurrentSession(id); setSidebarOpen(false); }}
          onNewChat={() => { startDraft(); setSidebarOpen(false); }}
        />
      </Sidebar>
    </View>
  );
}

const styles = StyleSheet.create({ container: { flex: 1 } });
