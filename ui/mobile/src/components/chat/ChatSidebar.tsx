import { FlatList, View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { DeleteIcon } from '../common/Icons';
import type { SessionMeta } from '../../types';

interface Props {
  sessions: SessionMeta[];
  currentSessionId: string | null;
  draftSession: boolean;
  onSelect: (id: string) => void;
  onNewChat: () => void;
  onDelete: (id: string) => void;
}

export function ChatSidebar({ sessions, currentSessionId, draftSession, onSelect, onNewChat, onDelete }: Props) {
  const showNewChat = !draftSession && (sessions.length > 0 || currentSessionId !== null);

  return (
    <View style={styles.container}>
      {showNewChat && (
        <TouchableOpacity style={styles.newBtn} onPress={onNewChat}>
          <Text style={styles.newBtnText}>+ 新对话</Text>
        </TouchableOpacity>
      )}
      <FlatList
        data={sessions}
        keyExtractor={(s) => s.id}
        renderItem={({ item }) => (
          <View style={[styles.item, item.id === currentSessionId && styles.itemActive]}>
            <TouchableOpacity style={styles.itemContent} onPress={() => onSelect(item.id)}>
              <Text style={styles.itemTitle} numberOfLines={1}>{item.title || '新对话'}</Text>
              <Text style={styles.itemDate}>
                {new Date(item.updated_at).toLocaleDateString()}
              </Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.deleteBtn} onPress={() => onDelete(item.id)}>
              <DeleteIcon size={18} color="#bbb" />
            </TouchableOpacity>
          </View>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, paddingTop: 48 },
  newBtn: { margin: 12, padding: 10, backgroundColor: '#007AFF', borderRadius: 8, alignItems: 'center' },
  newBtnText: { color: '#fff', fontWeight: 'bold' },
  item: {
    flexDirection: 'row',
    alignItems: 'center',
    borderBottomWidth: 1,
    borderBottomColor: '#eee',
  },
  itemActive: { backgroundColor: '#E8F0FE' },
  itemContent: { flex: 1, padding: 14 },
  itemTitle: { fontWeight: '500' },
  itemDate: { color: '#999', fontSize: 12, marginTop: 2 },
  deleteBtn: { paddingHorizontal: 14, paddingVertical: 14 },
});
