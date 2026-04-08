import { useState } from 'react';
import {
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { login, logout } from '@/src/api/auth';
import { useSettingsStore } from '@/src/store/settings';
import { useTheme } from '@/src/theme/ThemeContext';

export function AccountSettingsSection() {
  const colors = useTheme();
  const { jwtToken, setJwtToken } = useSettingsStore();
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  async function handleLogin() {
    try {
      const token = await login(password);
      await setJwtToken(token);
      setPassword('');
      setError('');
    } catch {
      setError('登录失败，请检查密码');
    }
  }

  async function handleLogout() {
    try {
      await logout();
    } catch {
      // ignore logout errors to allow local session reset
    }
    await setJwtToken(null);
  }

  return (
    <View style={styles.group}>
      <Text style={[styles.groupLabel, { color: colors.textSecondary }]}>账户</Text>
      {jwtToken ? (
        <View style={[styles.card, { backgroundColor: colors.cardBackground }]}>
          <View style={[styles.row, { borderBottomColor: colors.border }]}>
            <Text style={[styles.rowTitle, { color: colors.text }]}>Owner 登录</Text>
            <Text style={[styles.statusOk, { color: colors.success }]}>已登录</Text>
          </View>
          <TouchableOpacity
            style={[styles.destructiveButton, { backgroundColor: colors.destructiveBg }]}
            onPress={handleLogout}
          >
            <Text style={[styles.destructiveButtonText, { color: colors.error }]}>退出登录</Text>
          </TouchableOpacity>
        </View>
      ) : (
        <View style={[styles.card, { backgroundColor: colors.cardBackground }]}>
          <View style={[styles.row, { borderBottomColor: colors.border }]}>
            <Text style={[styles.rowTitle, { color: colors.text }]}>Owner 登录</Text>
            <Text style={[styles.statusIdle, { color: colors.textSecondary }]}>未登录</Text>
          </View>
          <View style={styles.inputBlock}>
            <Text style={[styles.inputLabel, { color: colors.textSecondary }]}>密码</Text>
            <TextInput
              style={[styles.input, { backgroundColor: colors.inputBackground, color: colors.text }]}
              value={password}
              onChangeText={setPassword}
              placeholder="输入 Owner 密码"
              placeholderTextColor={colors.textMuted}
              secureTextEntry
            />
          </View>
          {error ? <Text style={[styles.error, { color: colors.error }]}>{error}</Text> : null}
          <TouchableOpacity
            style={[styles.primaryButton, { backgroundColor: colors.accent }]}
            onPress={handleLogin}
          >
            <Text style={styles.primaryButtonText}>登录</Text>
          </TouchableOpacity>
        </View>
      )}
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
    textTransform: 'uppercase',
  },
  card: { borderRadius: 14, overflow: 'hidden' },
  row: {
    minHeight: 52,
    paddingHorizontal: 16,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  rowTitle: { fontSize: 17 },
  statusOk: { fontSize: 15, fontWeight: '600' },
  statusIdle: { fontSize: 15 },
  inputBlock: { paddingHorizontal: 16, paddingTop: 14, paddingBottom: 10 },
  inputLabel: { marginBottom: 8, fontSize: 13 },
  input: { minHeight: 46, borderRadius: 12, paddingHorizontal: 14, fontSize: 17 },
  error: { paddingHorizontal: 16, paddingBottom: 10, fontSize: 13 },
  primaryButton: {
    marginHorizontal: 16,
    marginBottom: 16,
    minHeight: 46,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
  },
  primaryButtonText: { fontSize: 17, fontWeight: '600', color: '#FFFFFF' },
  destructiveButton: {
    margin: 16,
    minHeight: 46,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
  },
  destructiveButtonText: { fontSize: 17, fontWeight: '600' },
});
