import { View, StyleSheet } from 'react-native';
import { ThinkingBlock } from './ThinkingBlock';
import { ToolCallGroup } from './ToolCallGroup';
import { MarkdownContent } from './MarkdownContent';
import type { RenderBlock } from '../../types';

type ToolBlock = Extract<RenderBlock, { type: 'tool' }>;

interface Props {
  blocks: RenderBlock[];
}

/** 将连续的 tool block 合并为一个 ToolCallGroup，其余块按顺序渲染。 */
function groupBlocks(blocks: RenderBlock[]): Array<RenderBlock | ToolBlock[]> {
  const result: Array<RenderBlock | ToolBlock[]> = [];
  let i = 0;
  while (i < blocks.length) {
    if (blocks[i].type === 'tool') {
      const group: ToolBlock[] = [];
      while (i < blocks.length && blocks[i].type === 'tool') {
        group.push(blocks[i] as ToolBlock);
        i++;
      }
      result.push(group);
    } else {
      result.push(blocks[i]);
      i++;
    }
  }
  return result;
}

export function AssistantMessage({ blocks }: Props) {
  if (blocks.length === 0) return null;

  const grouped = groupBlocks(blocks);

  return (
    <View style={styles.container}>
      {grouped.map((item, index) => {
        if (Array.isArray(item)) {
          return <ToolCallGroup key={`tools-${index}`} tools={item} />;
        }
        if (item.type === 'thinking') {
          return (
            <ThinkingBlock
              key={item.blockId}
              text={item.text}
              done={item.done}
            />
          );
        }
        if (item.type === 'text') {
          return (
            <MarkdownContent
              key={item.blockId}
              content={item.text}
              streaming={!item.done}
            />
          );
        }
        return null;
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    paddingHorizontal: 16,
    paddingVertical: 8,
  },
});
