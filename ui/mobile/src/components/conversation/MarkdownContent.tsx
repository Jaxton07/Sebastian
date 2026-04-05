import Markdown from 'react-native-markdown-display';
import { StyleSheet } from 'react-native';

interface Props {
  content: string;
  /** 流式未完成时传 true */
  streaming?: boolean;
}

export function MarkdownContent({ content }: Props) {
  return (
    <Markdown style={mdStyles}>{content}</Markdown>
  );
}

const mdStyles = StyleSheet.create({
  body: { color: '#d0d0d0', fontSize: 15, lineHeight: 22 },
  heading1: { color: '#ffffff', fontSize: 20, fontWeight: '700', marginBottom: 8 },
  heading2: { color: '#ffffff', fontSize: 17, fontWeight: '600', marginBottom: 6 },
  heading3: { color: '#e0e0e0', fontSize: 15, fontWeight: '600', marginBottom: 4 },
  strong: { color: '#ffffff', fontWeight: '700' },
  em: { fontStyle: 'italic' },
  code_inline: {
    backgroundColor: '#1e1e2e',
    color: '#a8d8a8',
    fontFamily: 'monospace',
    fontSize: 13,
    paddingHorizontal: 4,
    borderRadius: 3,
  },
  fence: {
    backgroundColor: '#111120',
    padding: 12,
    borderRadius: 8,
    marginVertical: 8,
  },
  code_block: {
    color: '#a8d8a8',
    fontFamily: 'monospace',
    fontSize: 13,
    lineHeight: 20,
  },
  bullet_list: { marginVertical: 4 },
  ordered_list: { marginVertical: 4 },
  list_item: { color: '#d0d0d0', marginBottom: 2 },
  blockquote: {
    borderLeftWidth: 3,
    borderLeftColor: '#3a3a5a',
    paddingLeft: 12,
    marginVertical: 6,
    opacity: 0.8,
  },
  hr: { borderTopColor: '#2a2a3a', borderTopWidth: 1, marginVertical: 12 },
  link: { color: '#7c6af5', textDecorationLine: 'underline' },
  table: { borderWidth: 1, borderColor: '#2a2a3a', marginVertical: 8 },
  th: { backgroundColor: '#1a1a2e', padding: 8, color: '#e0e0e0', fontWeight: '600' },
  td: { padding: 8, color: '#d0d0d0', borderTopWidth: 1, borderTopColor: '#2a2a3a' },
});
