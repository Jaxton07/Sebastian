import { View, Text, StyleSheet } from 'react-native';

interface Props { content: string; }

export function StreamingBubble({ content }: Props) {
  if (!content) return null;
  return (
    <View style={styles.row}>
      <View style={styles.bubble}>
        <Text style={styles.text}>{content}</Text>
        <Text style={styles.cursor}>▋</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { paddingHorizontal: 12, paddingVertical: 4, alignItems: 'flex-start' },
  bubble: { maxWidth: '80%', borderRadius: 16, padding: 10, backgroundColor: '#F0F0F0', flexDirection: 'row', flexWrap: 'wrap' },
  text: { color: '#000' },
  cursor: { color: '#007AFF' },
});
