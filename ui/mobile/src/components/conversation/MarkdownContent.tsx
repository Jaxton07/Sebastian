import Markdown from 'react-native-markdown-display';
import { useTheme, useIsDark } from '../../theme/ThemeContext';

interface Props {
  content: string;
  /** 流式未完成时传 true */
  streaming?: boolean;
}

export function MarkdownContent({ content }: Props) {
  const colors = useTheme();
  const isDark = useIsDark();

  const mdStyles = {
    body: { color: colors.text, fontSize: 15, lineHeight: 22 },
    heading1: { color: colors.text, fontSize: 20, fontWeight: '700' as const, marginBottom: 8 },
    heading2: { color: colors.text, fontSize: 17, fontWeight: '600' as const, marginBottom: 6 },
    heading3: { color: colors.text, fontSize: 15, fontWeight: '600' as const, marginBottom: 4 },
    strong: { color: colors.text, fontWeight: '700' as const },
    em: { fontStyle: 'italic' as const },
    // 行内代码：跟随主题；多行代码块始终保留暗色
    code_inline: {
      backgroundColor: isDark ? '#2a2a3e' : '#EFEFEF',
      color: isDark ? '#a8d8a8' : '#333333',
      fontFamily: 'monospace',
      fontSize: 13,
      paddingHorizontal: 6,
      paddingVertical: 2,
      borderRadius: 10,
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
    list_item: { color: colors.text, marginBottom: 2 },
    blockquote: {
      borderLeftWidth: 3,
      borderLeftColor: colors.border,
      paddingLeft: 12,
      marginVertical: 6,
      opacity: 0.8,
    },
    hr: { borderTopColor: colors.border, borderTopWidth: 1, marginVertical: 12 },
    link: { color: colors.accent, textDecorationLine: 'underline' as const },
    table: { borderWidth: 1, borderColor: colors.border, marginVertical: 8 },
    th: { backgroundColor: colors.secondaryBackground, padding: 8, color: colors.text, fontWeight: '600' as const },
    td: { padding: 8, color: colors.text, borderTopWidth: 1, borderTopColor: colors.border },
  };

  return (
    <Markdown style={mdStyles}>{content}</Markdown>
  );
}
