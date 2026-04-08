import { StyleSheet, Text, View } from 'react-native';
import { useRouter } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { AgentList } from '@/src/components/subagents/AgentList';
import { BackButton } from '@/src/components/common/BackButton';
import { useAgents } from '@/src/hooks/useAgents';
import { useTheme } from '@/src/theme/ThemeContext';
import type { Agent } from '@/src/types';

export default function SubAgentsScreen() {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const colors = useTheme();
  const { data: agents = [] } = useAgents();

  function handleSelectAgent(agent: Agent) {
    router.push(`/subagents/${agent.id}?name=${agent.name}`);
  }

  return (
    <View style={[styles.container, { backgroundColor: colors.secondaryBackground }]}>
      <View
        style={[
          styles.header,
          { paddingTop: insets.top, backgroundColor: colors.background, borderBottomColor: colors.borderLight },
        ]}
      >
        <BackButton style={styles.backBtn} />
        <Text style={[styles.headerTitle, { color: colors.text }]}>Agent Teams</Text>
        <View style={styles.backBtn} />
      </View>
      <AgentList agents={agents} onSelect={handleSelectAgent} />
    </View>
  );
}

const styles = StyleSheet.create({
  container:   { flex: 1 },
  header: {
    minHeight: 48,
    borderBottomWidth: 1,
    flexDirection: 'row', alignItems: 'center', paddingHorizontal: 12,
  },
  backBtn:     { width: 72 },
  headerTitle: { flex: 1, textAlign: 'center', fontSize: 16, fontWeight: '600' },
});
