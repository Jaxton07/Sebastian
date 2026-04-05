import { View, Text, StyleSheet } from 'react-native';

interface Props {
  name: string;
  input: string;
  status: 'running' | 'done' | 'failed';
}

const DOT_COLOR: Record<Props['status'], string> = {
  running: '#f5a623',
  done: '#4caf50',
  failed: '#f44336',
};

export function ToolCallRow({ name, input, status }: Props) {
  // Show first 60 chars of input to keep it one-line
  const inputPreview = input.length > 60 ? `${input.slice(0, 60)}…` : input;

  return (
    <View style={styles.row}>
      <View style={[styles.dot, { backgroundColor: DOT_COLOR[status] }]} />
      <Text style={styles.name}>{name}</Text>
      {inputPreview ? <Text style={styles.input}>{inputPreview}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 4,
    gap: 8,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    flexShrink: 0,
  },
  name: {
    color: '#8888aa',
    fontSize: 13,
    fontWeight: '500',
    flexShrink: 0,
  },
  input: {
    color: '#555566',
    fontSize: 13,
    flex: 1,
  },
});
