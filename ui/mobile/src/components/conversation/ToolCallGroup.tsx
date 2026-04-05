import { View, StyleSheet } from 'react-native';
import { ToolCallRow } from './ToolCallRow';
import type { RenderBlock } from '../../types';

type ToolBlock = Extract<RenderBlock, { type: 'tool' }>;

interface Props {
  tools: ToolBlock[];
}

export function ToolCallGroup({ tools }: Props) {
  return (
    <View style={styles.container}>
      {tools.map((tool, index) => (
        <View key={tool.toolId}>
          <ToolCallRow
            name={tool.name}
            input={tool.input}
            status={tool.status}
          />
          {/* Vertical connector between consecutive tool calls */}
          {index < tools.length - 1 && <View style={styles.connector} />}
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    paddingVertical: 2,
    paddingLeft: 4,
  },
  connector: {
    width: 1,
    height: 10,
    backgroundColor: '#2a2a2a',
    marginLeft: 3,   // aligns with center of the 8px dot
  },
});
