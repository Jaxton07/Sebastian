import { Text, StyleSheet } from 'react-native';
import type { AgentStatus } from '../../types';

const COLOR: Record<AgentStatus, string> = {
  idle: '#999',
  working: '#007AFF',
  waiting_approval: '#FF9500',
  completed: '#34C759',
  failed: '#FF3B30',
};

interface Props {
  status: AgentStatus;
}

export function AgentStatusBadge({ status }: Props) {
  return (
    <Text style={[styles.badge, { backgroundColor: COLOR[status] }]}>{status}</Text>
  );
}

const styles = StyleSheet.create({
  badge: { color: '#fff', fontSize: 11, paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4, overflow: 'hidden' },
});
