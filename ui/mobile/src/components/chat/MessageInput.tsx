import { useState } from 'react';
import { View, TextInput, TouchableOpacity, Text, StyleSheet } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useTheme } from '../../theme/ThemeContext';

interface Props {
  isWorking: boolean;
  onSend: (text: string) => void;
  onStop: () => void;
}

export function MessageInput({ isWorking, onSend, onStop }: Props) {
  const [text, setText] = useState('');
  const insets = useSafeAreaInsets();
  const colors = useTheme();

  function handleSubmit() {
    if (isWorking) { onStop(); return; }
    const trimmed = text.trim();
    if (!trimmed) return;
    onSend(trimmed);
    setText('');
  }

  return (
    <View style={[styles.container, { paddingBottom: insets.bottom + 8, backgroundColor: colors.background, borderTopColor: colors.borderLight }]}>
      <TextInput
        style={[styles.input, { borderColor: colors.inputBorder, color: colors.text, backgroundColor: colors.inputBackground }]}
        value={text}
        onChangeText={setText}
        placeholder="发消息…"
        placeholderTextColor={colors.textMuted}
        multiline
        onSubmitEditing={isWorking ? undefined : handleSubmit}
        blurOnSubmit={false}
      />
      <TouchableOpacity
        style={[styles.btn, { backgroundColor: isWorking ? colors.error : colors.accent }]}
        onPress={handleSubmit}
      >
        <Text style={styles.btnText}>{isWorking ? '■' : '↑'}</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    position: 'absolute', bottom: 0, left: 0, right: 0,
    flexDirection: 'row', paddingTop: 8, paddingHorizontal: 8, borderTopWidth: 1,
  },
  input: {
    flex: 1, borderWidth: 1,
    borderRadius: 20, paddingHorizontal: 14, paddingVertical: 8, maxHeight: 100,
  },
  btn: {
    width: 36, height: 36, borderRadius: 18,
    alignItems: 'center', justifyContent: 'center', marginLeft: 8, alignSelf: 'flex-end',
  },
  btnText:  { color: '#fff', fontWeight: 'bold' },
});
