import { FlatList, StyleSheet, View } from 'react-native';
import type { Message } from '../../types';
import { MessageBubble } from './MessageBubble';
import { StreamingBubble } from './StreamingBubble';

interface Props {
  messages: Message[];
  streamingContent?: string;
}

export function MessageList({ messages, streamingContent }: Props) {
  return (
    <FlatList
      data={messages}
      keyExtractor={(m) => m.id}
      renderItem={({ item }) => <MessageBubble message={item} />}
      ListFooterComponent={
        streamingContent ? <StreamingBubble content={streamingContent} /> : null
      }
      contentContainerStyle={styles.content}
      onContentSizeChange={() => {}}
      maintainVisibleContentPosition={{ minIndexForVisible: 0 }}
    />
  );
}

const styles = StyleSheet.create({
  content: { paddingBottom: 80 },
});
