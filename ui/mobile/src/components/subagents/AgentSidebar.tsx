import { FlatList, View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import type { Agent } from '../../types';
import { AgentStatusBadge } from './AgentStatusBadge';

interface Props {
  agents: Agent[];
  currentAgentId: string | null;
  onSelect: (id: string) => void;
}

export function AgentSidebar({ agents, currentAgentId, onSelect }: Props) {
  return (
    <View style={styles.container}>
      <Text style={styles.header}>Sub-Agents</Text>
      <FlatList
        data={agents}
        keyExtractor={(a) => a.id}
        renderItem={({ item }) => (
          <TouchableOpacity
            style={[styles.item, item.id === currentAgentId && styles.itemActive]}
            onPress={() => onSelect(item.id)}
          >
            <Text style={styles.name} numberOfLines={1}>{item.name}</Text>
            <AgentStatusBadge status={item.status} />
          </TouchableOpacity>
        )}
        ListEmptyComponent={<Text style={styles.empty}>暂无活跃 Agent</Text>}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, paddingTop: 48 },
  header: { fontWeight: 'bold', fontSize: 16, padding: 14 },
  item: { padding: 14, borderBottomWidth: 1, borderBottomColor: '#eee', flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  itemActive: { backgroundColor: '#E8F0FE' },
  name: { flex: 1, marginRight: 8 },
  empty: { color: '#999', padding: 14 },
});
