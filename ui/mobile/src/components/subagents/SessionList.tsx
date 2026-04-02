import { FlatList, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import type { SessionMeta } from '../../types';

interface Props {
  sessions: SessionMeta[];
  onSelect: (session: SessionMeta) => void;
}

function StatusDot({ status }: { status: SessionMeta['status'] }) {
  const color =
    status === 'active' ? '#34C759' : status === 'idle' ? '#999999' : '#CCCCCC';
  return <View style={[styles.dot, { backgroundColor: color }]} />;
}

export function SessionList({ sessions, onSelect }: Props) {
  if (sessions.length === 0) {
    return (
      <View style={styles.empty}>
        <Text style={styles.emptyText}>暂无进行中的会话</Text>
      </View>
    );
  }

  return (
    <FlatList
      data={sessions}
      keyExtractor={(session) => session.id}
      renderItem={({ item }) => (
        <TouchableOpacity style={styles.row} onPress={() => onSelect(item)}>
          <StatusDot status={item.status} />
          <View style={styles.info}>
            <Text style={styles.title} numberOfLines={1}>
              {item.title}
            </Text>
            <Text style={styles.meta}>
              {item.active_task_count > 0
                ? `${item.active_task_count} 个任务进行中`
                : '空闲'}
            </Text>
          </View>
        </TouchableOpacity>
      )}
    />
  );
}

const styles = StyleSheet.create({
  empty: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24 },
  emptyText: { color: '#999999', fontSize: 14 },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 16,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: '#E0E0E0',
    backgroundColor: '#FFFFFF',
  },
  dot: { width: 10, height: 10, borderRadius: 5, marginRight: 12 },
  info: { flex: 1 },
  title: { fontSize: 15, fontWeight: '500', color: '#111111' },
  meta: { fontSize: 12, color: '#888888', marginTop: 2 },
});
