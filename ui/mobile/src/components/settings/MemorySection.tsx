import { View, Text, StyleSheet } from 'react-native';

export function MemorySection() {
  return (
    <View style={styles.group}>
      <Text style={styles.groupLabel}>Memory</Text>
      <View style={styles.card}>
        <View style={styles.row}>
          <View>
            <Text style={styles.rowTitle}>Memory 管理</Text>
            <Text style={styles.rowSubtitle}>Episodic / Semantic 配置将随后开放</Text>
          </View>
          <Text style={styles.placeholder}>即将推出</Text>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  group: { marginBottom: 28 },
  groupLabel: {
    marginBottom: 8,
    paddingHorizontal: 4,
    fontSize: 13,
    fontWeight: '600',
    color: '#6D6D72',
    textTransform: 'uppercase',
  },
  card: {
    borderRadius: 14,
    backgroundColor: '#FFFFFF',
    overflow: 'hidden',
  },
  row: {
    minHeight: 68,
    paddingHorizontal: 16,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  rowTitle: { fontSize: 17, color: '#111111' },
  rowSubtitle: { marginTop: 4, fontSize: 13, lineHeight: 18, color: '#8E8E93' },
  placeholder: { fontSize: 13, color: '#8E8E93' },
});
