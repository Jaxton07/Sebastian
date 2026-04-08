import { useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Platform,
  StyleSheet,
  Text,
  TextInput,
  ToastAndroid,
  TouchableOpacity,
  View,
} from 'react-native';
import { syncCurrentThinkingCapability } from '@/src/api/llm';
import { useTheme } from '@/src/theme/ThemeContext';
import type {
  LLMProvider,
  LLMProviderCreate,
  LLMProviderType,
  ThinkingCapability,
} from '@/src/types';

const PROVIDER_TYPES: LLMProviderType[] = ['anthropic', 'openai'];

const CAPABILITY_OPTIONS: { value: ThinkingCapability | null; label: string; hint: string }[] = [
  { value: null, label: '未设置', hint: '后端不会注入思考相关参数' },
  { value: 'none', label: 'none', hint: '模型不支持思考控制' },
  { value: 'toggle', label: 'toggle', hint: '只支持开/关，无档位' },
  { value: 'effort', label: 'effort', hint: '支持 low/medium/high 三档' },
  { value: 'adaptive', label: 'adaptive', hint: 'Anthropic Adaptive（含 max）' },
  { value: 'always_on', label: 'always_on', hint: '模型必然思考，UI 固定' },
];

const DEFAULT_MODELS: Record<LLMProviderType, string> = {
  anthropic: 'claude-opus-4-6',
  openai: 'gpt-4o',
};

interface Props {
  initial?: LLMProvider;
  onSave: (data: LLMProviderCreate) => Promise<void>;
  onCancel: () => void;
}

export function ProviderForm({ initial, onSave, onCancel }: Props) {
  const colors = useTheme();
  const [name, setName] = useState(initial?.name ?? '');
  const [providerType, setProviderType] = useState<LLMProviderType>(
    initial?.provider_type ?? 'anthropic',
  );
  const [apiKey, setApiKey] = useState(initial?.api_key ?? '');
  const [model, setModel] = useState(initial?.model ?? DEFAULT_MODELS.anthropic);
  const [baseUrl, setBaseUrl] = useState(initial?.base_url ?? '');
  const [isDefault, setIsDefault] = useState(initial?.is_default ?? false);
  const [thinkingCapability, setThinkingCapability] = useState<ThinkingCapability | null>(
    initial?.thinking_capability ?? null,
  );
  const [saving, setSaving] = useState(false);

  function notifyClamped(from: string, to: string) {
    const msg = `${from} 在新模型下不可用，已切换为 ${to}`;
    if (Platform.OS === 'android') {
      ToastAndroid.show(msg, ToastAndroid.SHORT);
    } else {
      Alert.alert('思考档位已调整', msg);
    }
  }

  async function handleSave() {
    if (!name.trim() || !apiKey.trim() || !model.trim()) {
      Alert.alert('错误', '请填写名称、API Key 和模型');
      return;
    }
    setSaving(true);
    try {
      await onSave({
        name: name.trim(),
        provider_type: providerType,
        api_key: apiKey.trim(),
        model: model.trim(),
        base_url: baseUrl.trim() || null,
        thinking_capability: thinkingCapability,
        is_default: isDefault,
      });
      await syncCurrentThinkingCapability((report) => notifyClamped(report.from, report.to));
    } finally {
      setSaving(false);
    }
  }

  return (
    <View style={[styles.form, { backgroundColor: colors.cardBackground }]}>
      <Text style={[styles.label, { color: colors.textSecondary }]}>名称</Text>
      <TextInput
        style={[styles.input, { backgroundColor: colors.inputBackground, color: colors.text }]}
        value={name}
        onChangeText={setName}
        placeholder="如：Claude 家用"
        placeholderTextColor={colors.textMuted}
      />

      <Text style={[styles.label, { color: colors.textSecondary }]}>Provider 类型</Text>
      <View style={[styles.segmented, { backgroundColor: colors.segmentedBg }]}>
        {PROVIDER_TYPES.map((type) => (
          <TouchableOpacity
            key={type}
            style={[
              styles.segment,
              providerType === type && [styles.segmentActive, { backgroundColor: colors.cardBackground }],
            ]}
            onPress={() => {
              setProviderType(type);
              setModel(DEFAULT_MODELS[type]);
            }}
          >
            <Text
              style={[
                styles.segmentText,
                { color: colors.textSecondary },
                providerType === type && { color: colors.text },
              ]}
            >
              {type}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      <Text style={[styles.label, { color: colors.textSecondary }]}>API Key</Text>
      <TextInput
        style={[styles.input, { backgroundColor: colors.inputBackground, color: colors.text }]}
        value={apiKey}
        onChangeText={setApiKey}
        placeholder="sk-ant-... 或 sk-..."
        placeholderTextColor={colors.textMuted}
        secureTextEntry
        autoCapitalize="none"
      />

      <Text style={[styles.label, { color: colors.textSecondary }]}>模型</Text>
      <TextInput
        style={[styles.input, { backgroundColor: colors.inputBackground, color: colors.text }]}
        value={model}
        onChangeText={setModel}
        autoCapitalize="none"
        placeholderTextColor={colors.textMuted}
      />

      <Text style={[styles.label, { color: colors.textSecondary }]}>Base URL（可选，留空用默认）</Text>
      <TextInput
        style={[styles.input, { backgroundColor: colors.inputBackground, color: colors.text }]}
        value={baseUrl}
        onChangeText={setBaseUrl}
        placeholder="https://api.example.com/v1"
        placeholderTextColor={colors.textMuted}
        autoCapitalize="none"
      />

      <TouchableOpacity style={styles.toggleRow} onPress={() => setIsDefault((value) => !value)}>
        <Text style={[styles.toggleLabel, { color: colors.text }]}>设为默认 Provider</Text>
        <Text style={[styles.toggleValue, { color: colors.accent }]}>{isDefault ? '✓' : '○'}</Text>
      </TouchableOpacity>

      <Text style={[styles.label, { color: colors.textSecondary }]}>思考能力（thinking_capability）</Text>
      <View style={styles.capabilityList}>
        {CAPABILITY_OPTIONS.map((option) => {
          const active = thinkingCapability === option.value;
          return (
            <TouchableOpacity
              key={option.label}
              style={[
                styles.capabilityRow,
                {
                  backgroundColor: active ? colors.activeSessionBg : colors.inputBackground,
                  borderColor: active ? colors.accent : 'transparent',
                },
              ]}
              onPress={() => setThinkingCapability(option.value)}
              activeOpacity={0.7}
            >
              <View style={styles.capabilityBody}>
                <Text style={[styles.capabilityLabel, { color: active ? colors.accent : colors.text }]}>
                  {option.label}
                </Text>
                <Text style={[styles.capabilityHint, { color: colors.textSecondary }]}>
                  {option.hint}
                </Text>
              </View>
              {active ? <Text style={[styles.capabilityCheck, { color: colors.accent }]}>✓</Text> : null}
            </TouchableOpacity>
          );
        })}
      </View>

      <View style={styles.buttonRow}>
        <TouchableOpacity
          style={[styles.button, styles.cancelButton, { backgroundColor: colors.inputBackground }]}
          onPress={onCancel}
        >
          <Text style={[styles.cancelText, { color: colors.text }]}>取消</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.button, { backgroundColor: colors.accent }]}
          onPress={handleSave}
          disabled={saving}
        >
          {saving ? <ActivityIndicator color="#fff" /> : <Text style={styles.saveText}>保存</Text>}
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  form: { borderRadius: 14, padding: 16 },
  label: { fontSize: 13, marginBottom: 6, marginTop: 12 },
  input: { minHeight: 46, borderRadius: 12, paddingHorizontal: 14, fontSize: 17 },
  segmented: { flexDirection: 'row', padding: 4, borderRadius: 12 },
  segment: { flex: 1, minHeight: 36, borderRadius: 10, alignItems: 'center', justifyContent: 'center' },
  segmentActive: {},
  segmentText: { fontSize: 15, fontWeight: '500' },
  toggleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginTop: 16,
    paddingVertical: 4,
  },
  toggleLabel: { fontSize: 17 },
  toggleValue: { fontSize: 20 },
  capabilityList: { gap: 8 },
  capabilityRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 10,
    paddingHorizontal: 12,
    borderRadius: 10,
    borderWidth: 1,
  },
  capabilityBody: { flex: 1 },
  capabilityLabel: { fontSize: 15, fontWeight: '500' },
  capabilityHint: { fontSize: 12, marginTop: 2 },
  capabilityCheck: { fontSize: 16 },
  buttonRow: { flexDirection: 'row', gap: 12, marginTop: 20 },
  button: { flex: 1, minHeight: 46, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  cancelButton: {},
  cancelText: { fontSize: 17 },
  saveText: { fontSize: 17, fontWeight: '600', color: '#FFFFFF' },
});
