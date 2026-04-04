import { StyleSheet, Text, View } from 'react-native';
import { useRouter } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { AgentList } from '../../../src/components/subagents/AgentList';
import { useAgents } from '../../../src/hooks/useAgents';
import type { Agent } from '../../../src/types';

export default function SubAgentsScreen() {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { data: agents = [] } = useAgents();

  function handleSelectAgent(agent: Agent) {
    router.push(`/subagents/${agent.id}?name=${agent.name}`);
  }

  return (
    <View style={styles.container}>
      <View style={[styles.header, { paddingTop: insets.top }]}>
        <Text style={styles.headerTitle}>Sub-Agents</Text>
      </View>
      <View style={styles.sectionHeader}>
        <Text style={styles.sectionTitle}>Agent 列表</Text>
        <Text style={styles.sectionSubtitle}>
          先选一个 Sub-Agent，再进入它的会话列表和详情页。
        </Text>
      </View>
      <AgentList agents={agents} onSelect={handleSelectAgent} />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F5F5F5' },
  header: {
    minHeight: 48,
    backgroundColor: '#FFFFFF',
    borderBottomWidth: 1,
    borderBottomColor: '#E0E0E0',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 12,
  },
  headerTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#111111',
  },
  sectionHeader: {
    paddingHorizontal: 16,
    paddingTop: 16,
    paddingBottom: 8,
  },
  sectionTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: '#111111',
  },
  sectionSubtitle: {
    marginTop: 4,
    fontSize: 13,
    lineHeight: 18,
    color: '#6B6B6B',
  },
});
