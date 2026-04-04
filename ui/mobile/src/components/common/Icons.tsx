/**
 * Icon components adapted from openJax/ui/web/src/pic/icon.
 * SVG source files live in src/assets/icons/ for reference.
 *
 * React Native does not support SVG natively without react-native-svg.
 * These components use Text with Unicode characters as stand-ins until
 * react-native-svg is added to the project.
 */
import { Text, type TextStyle } from 'react-native';

interface IconProps {
  size?: number;
  color?: string;
  style?: TextStyle;
}

export function TrashIcon({ size = 16, color = '#999', style }: IconProps) {
  return (
    <Text style={[{ fontSize: size, color, lineHeight: size + 2 }, style]}>
      🗑
    </Text>
  );
}

export function EditIcon({ size = 16, color = '#999', style }: IconProps) {
  return (
    <Text style={[{ fontSize: size, color, lineHeight: size + 2 }, style]}>
      ✏️
    </Text>
  );
}

export function CloseIcon({ size = 16, color = '#999', style }: IconProps) {
  return (
    <Text style={[{ fontSize: size, color, lineHeight: size + 2 }, style]}>
      ✕
    </Text>
  );
}
