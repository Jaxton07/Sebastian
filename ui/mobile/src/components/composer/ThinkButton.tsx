import { TouchableOpacity, Text, StyleSheet } from 'react-native';
import { ThinkIcon } from '../common/Icons';
import { useTheme } from '../../theme/ThemeContext';

interface Props {
  active: boolean;
  onPress: () => void;
  disabled?: boolean;
}

const ACTIVE_BG = '#E8F0FE';
const ACTIVE_FG = '#3B82F6';

export function ThinkButton({ active, onPress, disabled }: Props) {
  const colors = useTheme();
  const bg = active ? ACTIVE_BG : colors.inputBackground;
  const fg = active ? ACTIVE_FG : colors.textMuted;

  return (
    <TouchableOpacity
      style={[styles.pill, { backgroundColor: bg }]}
      onPress={onPress}
      disabled={disabled}
      activeOpacity={0.7}
    >
      <ThinkIcon size={16} color={fg} />
      <Text style={[styles.label, { color: fg }]}>思考</Text>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  pill: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 18,
    gap: 6,
  },
  label: {
    fontSize: 14,
    fontWeight: '500',
  },
});
