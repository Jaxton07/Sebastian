import { useState } from 'react';
import { ActivityIndicator, Alert, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { router } from 'expo-router';
import { useLLMProvidersStore } from '@/src/store/llmProviders';
import { useTheme } from '@/src/theme/ThemeContext';
import { ConfirmDialog } from '@/src/components/common/ConfirmDialog';
import type { LLMProvider } from '@/src/types';

export function ProviderListSection() {
  const colors = useTheme();
  const { providers, loading, error, remove } = useLLMProvidersStore();
  const [deleteTarget, setDeleteTarget] = useState<LLMProvider | null>(null);

  async function confirmDelete() {
    if (!deleteTarget) return;
    const target = deleteTarget;
    setDeleteTarget(null);
    try {
      await remove(target.id);
    } catch (err) {
      Alert.alert(
        '删除失败',
        err instanceof Error ? err.message : '删除 Provider 时发生未知错误。',
      );
    }
  }

  if (loading) {
    return <ActivityIndicator style={styles.feedback} />;
  }

  if (error) {
    return (
      <View style={[styles.card, { backgroundColor: colors.cardBackground }]}>
        <Text style={[styles.errorText, { color: colors.error }]}>{error}</Text>
      </View>
    );
  }

  if (providers.length === 0) {
    return (
      <View style={[styles.card, styles.emptyCard, { backgroundColor: colors.cardBackground }]}>
        <Text style={[styles.emptyTitle, { color: colors.text }]}>尚未配置模型 Provider</Text>
        <Text style={[styles.emptySubtitle, { color: colors.textSecondary }]}>
          添加至少一个 Provider 后，Sebastian 才能正常发起对话。
        </Text>
        <TouchableOpacity
          style={[styles.primaryButton, { backgroundColor: colors.accent }]}
          onPress={() => router.push('/settings/providers/new')}
        >
          <Text style={styles.primaryButtonText}>添加 Provider</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <View style={styles.group}>
      {providers.map((provider) => (
        <View key={provider.id} style={[styles.card, { backgroundColor: colors.cardBackground }]}>
          <View style={styles.cardRow}>
            <TouchableOpacity
              style={styles.providerBody}
              onPress={() => router.push(`/settings/providers/${provider.id}`)}
            >
              <Text style={[styles.cardTitle, { color: colors.text }]}>
                {provider.name}
                {provider.is_default ? ' ★' : ''}
              </Text>
              <Text style={[styles.cardSub, { color: colors.textSecondary }]}>
                {provider.provider_type} · {provider.model}
              </Text>
            </TouchableOpacity>
            <View style={styles.cardActions}>
              <TouchableOpacity
                onPress={() => router.push(`/settings/providers/${provider.id}`)}
                style={styles.actionBtn}
              >
                <Text style={[styles.actionText, { color: colors.accent }]}>编辑</Text>
              </TouchableOpacity>
              <TouchableOpacity onPress={() => setDeleteTarget(provider)} style={styles.actionBtn}>
                <Text style={[styles.actionText, { color: colors.error }]}>删除</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      ))}

      <TouchableOpacity
        style={[styles.addButton, { backgroundColor: colors.cardBackground }]}
        onPress={() => router.push('/settings/providers/new')}
      >
        <Text style={[styles.addButtonText, { color: colors.accent }]}>+ 添加 Provider</Text>
      </TouchableOpacity>

      <ConfirmDialog
        visible={deleteTarget !== null}
        title="删除 Provider"
        message={`确认删除 "${deleteTarget?.name ?? ''}"？`}
        confirmText="删除"
        destructive
        onCancel={() => setDeleteTarget(null)}
        onConfirm={confirmDelete}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  group: { marginBottom: 28 },
  feedback: { marginTop: 24 },
  card: {
    borderRadius: 14,
    marginBottom: 8,
    overflow: 'hidden',
  },
  emptyCard: {
    padding: 18,
  },
  emptyTitle: {
    fontSize: 18,
    fontWeight: '600',
  },
  emptySubtitle: {
    marginTop: 8,
    fontSize: 14,
    lineHeight: 20,
  },
  primaryButton: {
    marginTop: 16,
    minHeight: 46,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
  },
  primaryButtonText: {
    fontSize: 17,
    fontWeight: '600',
    color: '#FFFFFF',
  },
  cardRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  providerBody: { flex: 1 },
  cardTitle: { fontSize: 17, fontWeight: '500' },
  cardSub: { fontSize: 13, marginTop: 2 },
  cardActions: { flexDirection: 'row', gap: 12 },
  actionBtn: { padding: 4 },
  actionText: { fontSize: 15 },
  addButton: {
    borderRadius: 14,
    minHeight: 48,
    alignItems: 'center',
    justifyContent: 'center',
  },
  addButtonText: { fontSize: 17 },
  errorText: { fontSize: 15, padding: 16 },
});
