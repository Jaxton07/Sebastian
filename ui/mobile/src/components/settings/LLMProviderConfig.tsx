import { useEffect, useState } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  ActivityIndicator,
  Alert,
  StyleSheet,
} from 'react-native';
import { useLLMProvidersStore } from '../../store/llmProviders';
import type { LLMProvider, LLMProviderCreate, LLMProviderType } from '../../types';

const PROVIDER_TYPES: LLMProviderType[] = ['anthropic', 'openai'];

const DEFAULT_MODELS: Record<LLMProviderType, string> = {
  anthropic: 'claude-opus-4-6',
  openai: 'gpt-4o',
};

function ProviderForm({
  initial,
  onSave,
  onCancel,
}: {
  initial?: LLMProvider;
  onSave: (data: LLMProviderCreate) => Promise<void>;
  onCancel: () => void;
}) {
  const [name, setName] = useState(initial?.name ?? '');
  const [providerType, setProviderType] = useState<LLMProviderType>(
    initial?.provider_type ?? 'anthropic',
  );
  const [apiKey, setApiKey] = useState(initial?.api_key ?? '');
  const [model, setModel] = useState(initial?.model ?? DEFAULT_MODELS.anthropic);
  const [baseUrl, setBaseUrl] = useState(initial?.base_url ?? '');
  const [isDefault, setIsDefault] = useState(initial?.is_default ?? false);
  const [saving, setSaving] = useState(false);

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
        is_default: isDefault,
      });
    } finally {
      setSaving(false);
    }
  }

  return (
    <View style={styles.form}>
      <Text style={styles.label}>名称</Text>
      <TextInput style={styles.input} value={name} onChangeText={setName} placeholder="如：Claude 家用" />

      <Text style={styles.label}>Provider 类型</Text>
      <View style={styles.segmented}>
        {PROVIDER_TYPES.map((pt) => (
          <TouchableOpacity
            key={pt}
            style={[styles.segment, providerType === pt && styles.segmentActive]}
            onPress={() => {
              setProviderType(pt);
              setModel(DEFAULT_MODELS[pt]);
            }}
          >
            <Text style={[styles.segmentText, providerType === pt && styles.segmentTextActive]}>
              {pt}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      <Text style={styles.label}>API Key</Text>
      <TextInput
        style={styles.input}
        value={apiKey}
        onChangeText={setApiKey}
        placeholder="sk-ant-... 或 sk-..."
        secureTextEntry
        autoCapitalize="none"
      />

      <Text style={styles.label}>模型</Text>
      <TextInput style={styles.input} value={model} onChangeText={setModel} autoCapitalize="none" />

      <Text style={styles.label}>Base URL（可选，留空用默认）</Text>
      <TextInput
        style={styles.input}
        value={baseUrl}
        onChangeText={setBaseUrl}
        placeholder="https://api.example.com/v1"
        autoCapitalize="none"
      />

      <TouchableOpacity
        style={styles.toggleRow}
        onPress={() => setIsDefault((v) => !v)}
      >
        <Text style={styles.toggleLabel}>设为默认 Provider</Text>
        <Text style={styles.toggleValue}>{isDefault ? '✓' : '○'}</Text>
      </TouchableOpacity>

      <View style={styles.buttonRow}>
        <TouchableOpacity style={[styles.btn, styles.btnCancel]} onPress={onCancel}>
          <Text style={styles.btnCancelText}>取消</Text>
        </TouchableOpacity>
        <TouchableOpacity style={[styles.btn, styles.btnSave]} onPress={handleSave} disabled={saving}>
          {saving ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Text style={styles.btnSaveText}>保存</Text>
          )}
        </TouchableOpacity>
      </View>
    </View>
  );
}

export function LLMProviderConfig() {
  const { providers, loading, error, fetch, create, update, remove } = useLLMProvidersStore();
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<LLMProvider | null>(null);

  useEffect(() => {
    fetch();
  }, []);

  async function handleCreate(data: LLMProviderCreate) {
    await create(data);
    setShowForm(false);
  }

  async function handleUpdate(data: LLMProviderCreate) {
    if (!editing) return;
    await update(editing.id, data);
    setEditing(null);
  }

  async function handleDelete(provider: LLMProvider) {
    Alert.alert('删除 Provider', `确认删除 "${provider.name}"？`, [
      { text: '取消', style: 'cancel' },
      {
        text: '删除',
        style: 'destructive',
        onPress: async () => {
          await remove(provider.id);
        },
      },
    ]);
  }

  if (showForm || editing) {
    return (
      <View style={styles.group}>
        <Text style={styles.groupLabel}>模型</Text>
        <ProviderForm
          initial={editing ?? undefined}
          onSave={editing ? handleUpdate : handleCreate}
          onCancel={() => {
            setShowForm(false);
            setEditing(null);
          }}
        />
      </View>
    );
  }

  return (
    <View style={styles.group}>
      <Text style={styles.groupLabel}>模型</Text>

      {loading && <ActivityIndicator style={{ marginBottom: 12 }} />}
      {error && <Text style={styles.errorText}>{error}</Text>}

      {providers.map((p) => (
        <View key={p.id} style={styles.card}>
          <View style={styles.cardRow}>
            <View style={{ flex: 1 }}>
              <Text style={styles.cardTitle}>
                {p.name}
                {p.is_default ? ' ★' : ''}
              </Text>
              <Text style={styles.cardSub}>
                {p.provider_type} · {p.model}
              </Text>
            </View>
            <View style={styles.cardActions}>
              <TouchableOpacity onPress={() => setEditing(p)} style={styles.actionBtn}>
                <Text style={styles.actionBtnText}>编辑</Text>
              </TouchableOpacity>
              <TouchableOpacity onPress={() => handleDelete(p)} style={styles.actionBtn}>
                <Text style={[styles.actionBtnText, { color: '#FF3B30' }]}>删除</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      ))}

      <TouchableOpacity style={styles.addBtn} onPress={() => setShowForm(true)}>
        <Text style={styles.addBtnText}>+ 添加 Provider</Text>
      </TouchableOpacity>
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
    marginBottom: 8,
    overflow: 'hidden',
  },
  cardRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  cardTitle: { fontSize: 17, color: '#111111', fontWeight: '500' },
  cardSub: { fontSize: 13, color: '#8E8E93', marginTop: 2 },
  cardActions: { flexDirection: 'row', gap: 12 },
  actionBtn: { padding: 4 },
  actionBtnText: { fontSize: 15, color: '#007AFF' },
  addBtn: {
    borderRadius: 14,
    backgroundColor: '#FFFFFF',
    minHeight: 48,
    alignItems: 'center',
    justifyContent: 'center',
  },
  addBtnText: { fontSize: 17, color: '#007AFF' },
  form: {
    borderRadius: 14,
    backgroundColor: '#FFFFFF',
    padding: 16,
  },
  label: { fontSize: 13, color: '#6D6D72', marginBottom: 6, marginTop: 12 },
  input: {
    minHeight: 46,
    borderRadius: 12,
    backgroundColor: '#F2F2F7',
    paddingHorizontal: 14,
    fontSize: 17,
    color: '#111111',
  },
  segmented: {
    flexDirection: 'row',
    padding: 4,
    borderRadius: 12,
    backgroundColor: '#F2F2F7',
  },
  segment: { flex: 1, minHeight: 36, borderRadius: 10, alignItems: 'center', justifyContent: 'center' },
  segmentActive: { backgroundColor: '#FFFFFF' },
  segmentText: { fontSize: 15, color: '#6D6D72', fontWeight: '500' },
  segmentTextActive: { color: '#111111' },
  toggleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginTop: 16,
    paddingVertical: 4,
  },
  toggleLabel: { fontSize: 17, color: '#111111' },
  toggleValue: { fontSize: 20, color: '#007AFF' },
  buttonRow: { flexDirection: 'row', gap: 12, marginTop: 20 },
  btn: { flex: 1, minHeight: 46, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  btnCancel: { backgroundColor: '#F2F2F7' },
  btnSave: { backgroundColor: '#007AFF' },
  btnCancelText: { fontSize: 17, color: '#111111' },
  btnSaveText: { fontSize: 17, fontWeight: '600', color: '#FFFFFF' },
  errorText: { color: '#FF3B30', fontSize: 15, marginBottom: 8 },
});
