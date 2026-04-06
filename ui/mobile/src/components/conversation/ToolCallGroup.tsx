import { View, StyleSheet } from 'react-native';
import { ToolCallRow } from './ToolCallRow';
import { useTheme } from '../../theme/ThemeContext';
import type { RenderBlock } from '../../types';

type ToolBlock = Extract<RenderBlock, { type: 'tool' }>;

interface Props {
  tools: ToolBlock[];
}

export function ToolCallGroup({ tools }: Props) {
  const colors = useTheme();

  if (tools.length === 0) return null;

  return (
    <View style={styles.container}>
      {/* Continuous vertical line — absolute positioned behind the dots */}
      {tools.length > 1 && (
        <View
          style={[
            styles.verticalLine,
            { backgroundColor: colors.border },
          ]}
        />
      )}

      {tools.map((tool) => (
        <ToolCallRow
          key={tool.toolId}
          name={tool.name}
          input={tool.input}
          status={tool.status}
          result={tool.result}
        />
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    position: 'relative',
    paddingVertical: 2,
    paddingLeft: 4,
  },
  verticalLine: {
    position: 'absolute',
    left: 7,        // center of 8px dot at paddingLeft:4 → 4 + 3 = 7
    top: 8,         // vertically aligned with center of first dot (paddingVertical:4 + dot radius 4)
    bottom: 8,      // aligned with center of last dot
    width: 1,
    zIndex: 0,
  },
});
