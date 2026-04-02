import { useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, StyleSheet } from 'react-native';
import { useSettingsStore } from '../../store/settings';
import { checkHealth } from '../../api/auth';

export function ServerConfig() {
  const { serverUrl, setServerUrl } = useSettingsStore();
  const [input, setInput] = useState(serverUrl);
  const [status, setStatus] = useState<'idle' | 'ok' | 'fail'>('idle');

  async function handleSave() {
    await setServerUrl(input.trim());
    const ok = await checkHealth();
    setStatus(ok ? 'ok' : 'fail');
  }

  return (
    <View style={styles.group}>
      <Text style={styles.groupLabel}>连接</Text>
      <View style={styles.card}>
        <View style={styles.row}>
          <Text style={styles.rowTitle}>Server URL</Text>
          <Text
            style={[
              styles.statusText,
              status === 'ok' && styles.statusOk,
              status === 'fail' && styles.statusFail,
            ]}
          >
            {status === 'ok' ? '已连接' : status === 'fail' ? '失败' : '未测试'}
          </Text>
        </View>
        <View style={styles.inputBlock}>
          <TextInput
            style={styles.input}
            value={input}
            onChangeText={setInput}
            placeholder="http://192.168.1.x:8000"
            placeholderTextColor="#A0A0A5"
            autoCapitalize="none"
            keyboardType="url"
          />
        </View>
        <TouchableOpacity style={styles.button} onPress={handleSave}>
          <Text style={styles.buttonText}>保存并测试</Text>
        </TouchableOpacity>
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
  rowTitle: { fontSize: 17, color: '#111111' },
  statusText: { fontSize: 15, color: '#8E8E93' },
  statusOk: { color: '#34C759', fontWeight: '600' },
  statusFail: { color: '#FF3B30', fontWeight: '600' },
  inputBlock: { padding: 16, paddingBottom: 12 },
  input: {
    minHeight: 46,
    borderRadius: 12,
    backgroundColor: '#F2F2F7',
    paddingHorizontal: 14,
    fontSize: 17,
    color: '#111111',
  },
  button: {
    marginHorizontal: 16,
    marginBottom: 16,
    minHeight: 46,
    borderRadius: 12,
    backgroundColor: '#007AFF',
    alignItems: 'center',
    justifyContent: 'center',
  },
  buttonText: { fontSize: 17, fontWeight: '600', color: '#FFFFFF' },
});
