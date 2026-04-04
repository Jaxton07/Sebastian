import { useEffect, useState } from 'react';
import { View, Text, Switch, StyleSheet, Alert } from 'react-native';
import { getLogState, patchLogState } from '../../api/debug';
import { useSettingsStore } from '../../store/settings';

export function DebugLogging() {
  const { jwtToken } = useSettingsStore();
  const [llmStream, setLlmStream] = useState(false);
  const [sse, setSse] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!jwtToken) return;
    getLogState()
      .then((state) => {
        setLlmStream(state.llm_stream_enabled);
        setSse(state.sse_enabled);
      })
      .catch(() => {
        // 未登录或网络错误时静默忽略，保持默认值
      });
  }, [jwtToken]);

  async function toggle(field: 'llm_stream_enabled' | 'sse_enabled', value: boolean) {
    const prev = field === 'llm_stream_enabled' ? llmStream : sse;
    // 乐观更新
    if (field === 'llm_stream_enabled') setLlmStream(value);
    else setSse(value);

    setLoading(true);
    try {
      const updated = await patchLogState({ [field]: value });
      setLlmStream(updated.llm_stream_enabled);
      setSse(updated.sse_enabled);
    } catch {
      // 回滚
      if (field === 'llm_stream_enabled') setLlmStream(prev);
      else setSse(prev);
      Alert.alert('错误', '更新日志开关失败，请检查网络连接');
    } finally {
      setLoading(false);
    }
  }

  if (!jwtToken) return null;

  return (
    <View style={styles.group}>
      <Text style={styles.groupLabel}>调试日志</Text>
      <View style={styles.card}>
        <View style={styles.row}>
          <Text style={styles.rowTitle}>LLM Stream 日志</Text>
          <Switch
            value={llmStream}
            onValueChange={(v) => toggle('llm_stream_enabled', v)}
            disabled={loading}
          />
        </View>
        <View style={[styles.row, styles.lastRow]}>
          <Text style={styles.rowTitle}>SSE 事件日志</Text>
          <Switch
            value={sse}
            onValueChange={(v) => toggle('sse_enabled', v)}
            disabled={loading}
          />
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
    minHeight: 52,
    paddingHorizontal: 16,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: '#D1D1D6',
  },
  lastRow: {
    borderBottomWidth: 0,
  },
  rowTitle: { fontSize: 17, color: '#111111' },
});
