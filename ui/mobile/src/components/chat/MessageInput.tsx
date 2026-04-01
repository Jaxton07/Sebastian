import { useState } from 'react';
import { View, TextInput, TouchableOpacity, Text, StyleSheet } from 'react-native';

interface Props {
  isWorking: boolean;
  onSend: (text: string) => void;
  onStop: () => void;
}

export function MessageInput({ isWorking, onSend, onStop }: Props) {
  const [text, setText] = useState('');

  function handleSubmit() {
    if (isWorking) { onStop(); return; }
    const trimmed = text.trim();
    if (!trimmed) return;
    onSend(trimmed);
    setText('');
  }

  return (
    <View style={styles.container}>
      <TextInput
        style={styles.input}
        value={text}
        onChangeText={setText}
        placeholder="发消息…"
        multiline
        onSubmitEditing={isWorking ? undefined : handleSubmit}
        blurOnSubmit={false}
      />
      <TouchableOpacity style={[styles.btn, isWorking && styles.btnStop]} onPress={handleSubmit}>
        <Text style={styles.btnText}>{isWorking ? '■' : '↑'}</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { position: 'absolute', bottom: 0, left: 0, right: 0, flexDirection: 'row', padding: 8, backgroundColor: '#fff', borderTopWidth: 1, borderTopColor: '#eee' },
  input: { flex: 1, borderWidth: 1, borderColor: '#ccc', borderRadius: 20, paddingHorizontal: 14, paddingVertical: 8, maxHeight: 100 },
  btn: { width: 36, height: 36, borderRadius: 18, backgroundColor: '#007AFF', alignItems: 'center', justifyContent: 'center', marginLeft: 8, alignSelf: 'flex-end' },
  btnStop: { backgroundColor: '#FF3B30' },
  btnText: { color: '#fff', fontWeight: 'bold' },
});
