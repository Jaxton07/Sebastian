import { View, Text, StyleSheet } from 'react-native';
import type { Message } from '../../types';

interface Props { message: Message; }

export function MessageBubble({ message }: Props) {
  const isUser = message.role === 'user';
  return (
    <View style={[styles.row, isUser ? styles.rowUser : styles.rowAssistant]}>
      <View style={[styles.bubble, isUser ? styles.bubbleUser : styles.bubbleAssistant]}>
        <Text style={isUser ? styles.textUser : styles.textAssistant}>{message.content}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { paddingHorizontal: 12, paddingVertical: 4 },
  rowUser: { alignItems: 'flex-end' },
  rowAssistant: { alignItems: 'flex-start' },
  bubble: { maxWidth: '80%', borderRadius: 16, padding: 10 },
  bubbleUser: { backgroundColor: '#007AFF' },
  bubbleAssistant: { backgroundColor: '#F0F0F0' },
  textUser: { color: '#fff' },
  textAssistant: { color: '#000' },
});
