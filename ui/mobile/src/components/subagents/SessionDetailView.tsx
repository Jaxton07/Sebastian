import { FlatList, StyleSheet, Text, View } from 'react-native';
import type { TaskDetail } from '../../types';

interface Props {
  tasks: TaskDetail[];
}

function taskStatusColor(status: TaskDetail['status']): string {
  switch (status) {
    case 'running':
      return '#FF9500';
    case 'completed':
      return '#34C759';
    case 'failed':
      return '#FF3B30';
    case 'cancelled':
      return '#999999';
    default:
      return '#007AFF';
  }
}

export function SessionDetailView({ tasks }: Props) {
  if (tasks.length === 0) {
    return (
      <View style={styles.empty}>
        <Text style={styles.emptyText}>暂无任务</Text>
      </View>
    );
  }

  return (
    <FlatList
      data={tasks}
      keyExtractor={(task) => task.id}
      contentContainerStyle={styles.list}
      renderItem={({ item }) => (
        <View style={styles.card}>
          <View style={styles.cardHeader}>
            <Text style={[styles.status, { color: taskStatusColor(item.status) }]}>
              {item.status.toUpperCase()}
            </Text>
          </View>
          <Text style={styles.goal}>{item.goal}</Text>
          <Text style={styles.meta}>
            {new Date(item.created_at).toLocaleString()}
          </Text>
        </View>
      )}
    />
  );
}

const styles = StyleSheet.create({
  empty: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24 },
  emptyText: { color: '#999999', fontSize: 14 },
  list: { padding: 12 },
  card: {
    backgroundColor: '#FFFFFF',
    borderRadius: 10,
    padding: 14,
    marginBottom: 10,
    shadowColor: '#000000',
    shadowOpacity: 0.05,
    shadowRadius: 4,
    elevation: 2,
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    marginBottom: 6,
  },
  status: { fontSize: 11, fontWeight: '700', letterSpacing: 0.5 },
  goal: { fontSize: 14, color: '#111111', lineHeight: 20 },
  meta: { fontSize: 11, color: '#AAAAAA', marginTop: 6 },
});
