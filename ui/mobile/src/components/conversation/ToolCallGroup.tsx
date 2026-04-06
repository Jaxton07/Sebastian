import { View, StyleSheet } from 'react-native';
import { ToolCallRow } from './ToolCallRow';
import type { RenderBlock } from '../../types';

type ToolBlock = Extract<RenderBlock, { type: 'tool' }>;

interface Props {
  tools: ToolBlock[];
}

export function ToolCallGroup({ tools }: Props) {
  if (tools.length === 0) return null;

  return (
    <View style={styles.container}>
      {tools.map((tool, i) => (
        <ToolCallRow
          key={tool.toolId}
          name={tool.name}
          input={tool.input}
          status={tool.status}
          result={tool.result}
          isFirst={i === 0}
          isLast={i === tools.length - 1}
          showLine={tools.length > 1}
        />
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    paddingVertical: 2,
    paddingLeft: 4,
  },
});
