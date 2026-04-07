import { TextInput, StyleSheet } from 'react-native';
import { useTheme } from '../../theme/ThemeContext';
import { COMPOSER_LINE_HEIGHT, COMPOSER_MIN_HEIGHT, COMPOSER_MAX_HEIGHT } from './constants';

interface Props {
  value: string;
  onChange: (text: string) => void;
  editable: boolean;
}

export function InputTextArea({ value, onChange, editable }: Props) {
  const colors = useTheme();
  return (
    <TextInput
      style={[styles.input, { color: colors.text }]}
      value={value}
      onChangeText={onChange}
      placeholder="向 Sebastian 发送消息"
      placeholderTextColor={colors.textMuted}
      multiline
      editable={editable}
      scrollEnabled
    />
  );
}

const styles = StyleSheet.create({
  input: {
    fontSize: 15,
    lineHeight: COMPOSER_LINE_HEIGHT,
    minHeight: COMPOSER_MIN_HEIGHT,
    maxHeight: COMPOSER_MAX_HEIGHT,
    paddingTop: 0,
    paddingBottom: 0,
    textAlignVertical: 'top',
  },
});
