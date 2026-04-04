/**
 * Icon components using react-native-svg + react-native-svg-transformer.
 * SVG source files live in src/assets/icons/.
 * Metro is configured in metro.config.js to transform .svg imports.
 */
import type { ViewStyle } from 'react-native';
import type { SvgProps } from 'react-native-svg';
import DeleteSvg from '../../assets/icons/delete.svg';

interface IconProps {
  size?: number;
  color?: string;
  style?: ViewStyle;
}

function svgProps(size: number, color: string, style?: ViewStyle): SvgProps {
  return { width: size, height: size, color, fill: color, style };
}

export function DeleteIcon({ size = 16, color = '#bbb', style }: IconProps) {
  return <DeleteSvg {...svgProps(size, color, style)} />;
}
