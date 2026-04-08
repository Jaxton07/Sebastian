import { StyleSheet, Text, TouchableOpacity, type StyleProp, type ViewStyle } from 'react-native';
import { useRouter } from 'expo-router';
import { useTheme } from '../../theme/ThemeContext';
import { RightArrowIcon } from './Icons';

interface Props {
  /** Override the default router.back() behavior. */
  onPress?: () => void;
  /** Optional label override (default: 返回). */
  label?: string;
  /** Optional tint override (default: theme accent). */
  color?: string;
  style?: StyleProp<ViewStyle>;
}

/**
 * Unified back button used across all screens that need a header-level back action.
 * Renders a left-pointing chevron (RightArrowIcon rotated 180°) + "返回" label.
 */
export function BackButton({ onPress, label = '返回', color, style }: Props) {
  const router = useRouter();
  const colors = useTheme();
  const tint = color ?? colors.accent;

  return (
    <TouchableOpacity
      style={[styles.container, style]}
      onPress={onPress ?? (() => router.back())}
      hitSlop={8}
      activeOpacity={0.6}
    >
      <RightArrowIcon
        size={16}
        color={tint}
        style={{ transform: [{ rotate: '180deg' }] }}
      />
      <Text style={[styles.label, { color: tint }]}>{label}</Text>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingVertical: 4,
    paddingRight: 8,
  },
  label: { fontSize: 16 },
});
