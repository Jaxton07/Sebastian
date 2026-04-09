import { useMemo } from 'react';
import { View, Text, ScrollView, StyleSheet } from 'react-native';
import hljs from 'highlight.js/lib/core';
import javascript from 'highlight.js/lib/languages/javascript';
import typescript from 'highlight.js/lib/languages/typescript';
import python from 'highlight.js/lib/languages/python';
import bash from 'highlight.js/lib/languages/bash';
import json from 'highlight.js/lib/languages/json';
import xml from 'highlight.js/lib/languages/xml';
import css from 'highlight.js/lib/languages/css';
import sql from 'highlight.js/lib/languages/sql';
import yaml from 'highlight.js/lib/languages/yaml';
import markdown from 'highlight.js/lib/languages/markdown';
import java from 'highlight.js/lib/languages/java';
import go from 'highlight.js/lib/languages/go';
import rust from 'highlight.js/lib/languages/rust';
import { useIsDark } from '../../theme/ThemeContext';

hljs.registerLanguage('javascript', javascript);
hljs.registerLanguage('js', javascript);
hljs.registerLanguage('typescript', typescript);
hljs.registerLanguage('ts', typescript);
hljs.registerLanguage('python', python);
hljs.registerLanguage('py', python);
hljs.registerLanguage('bash', bash);
hljs.registerLanguage('sh', bash);
hljs.registerLanguage('shell', bash);
hljs.registerLanguage('json', json);
hljs.registerLanguage('html', xml);
hljs.registerLanguage('xml', xml);
hljs.registerLanguage('css', css);
hljs.registerLanguage('sql', sql);
hljs.registerLanguage('yaml', yaml);
hljs.registerLanguage('yml', yaml);
hljs.registerLanguage('markdown', markdown);
hljs.registerLanguage('md', markdown);
hljs.registerLanguage('java', java);
hljs.registerLanguage('go', go);
hljs.registerLanguage('rust', rust);

// Token class -> color mapping (VS Code dark+ inspired)
const DARK_TOKEN_COLORS: Record<string, string> = {
  keyword: '#C586C0',
  built_in: '#DCDCAA',
  type: '#4EC9B0',
  literal: '#569CD6',
  number: '#B5CEA8',
  string: '#CE9178',
  regexp: '#D16969',
  symbol: '#569CD6',
  class: '#4EC9B0',
  function: '#DCDCAA',
  title: '#DCDCAA',
  params: '#9CDCFE',
  comment: '#6A9955',
  doctag: '#608B4E',
  meta: '#569CD6',
  'meta-keyword': '#569CD6',
  'meta-string': '#CE9178',
  attr: '#9CDCFE',
  attribute: '#9CDCFE',
  variable: '#9CDCFE',
  property: '#9CDCFE',
  name: '#9CDCFE',
  tag: '#569CD6',
  selector: '#D7BA7D',
  'selector-id': '#D7BA7D',
  'selector-class': '#D7BA7D',
  'template-variable': '#9CDCFE',
  'template-tag': '#569CD6',
  addition: '#B5CEA8',
  deletion: '#CE9178',
  operator: '#D4D4D4',
  punctuation: '#D4D4D4',
  subst: '#9CDCFE',
  section: '#DCDCAA',
  bullet: '#569CD6',
  link: '#569CD6',
};

const LIGHT_TOKEN_COLORS: Record<string, string> = {
  keyword: '#AF00DB',
  built_in: '#795E26',
  type: '#267F99',
  literal: '#0000FF',
  number: '#098658',
  string: '#A31515',
  regexp: '#811F3F',
  symbol: '#0000FF',
  class: '#267F99',
  function: '#795E26',
  title: '#795E26',
  params: '#001080',
  comment: '#008000',
  doctag: '#008000',
  meta: '#0000FF',
  'meta-keyword': '#0000FF',
  'meta-string': '#A31515',
  attr: '#001080',
  attribute: '#001080',
  variable: '#001080',
  property: '#001080',
  name: '#001080',
  tag: '#800000',
  selector: '#800000',
  'selector-id': '#800000',
  'selector-class': '#800000',
  'template-variable': '#001080',
  'template-tag': '#0000FF',
  addition: '#098658',
  deletion: '#A31515',
  operator: '#000000',
  punctuation: '#000000',
  subst: '#001080',
  section: '#795E26',
  bullet: '#0000FF',
  link: '#0000FF',
};

interface Token {
  text: string;
  className?: string;
}

/**
 * Parse highlight.js HTML output into flat token array.
 * hljs output is simple: text and <span class="hljs-xxx">text</span>, with possible nesting.
 */
function parseHljsHtml(html: string): Token[] {
  const tokens: Token[] = [];
  // Stack for nested spans
  const classStack: string[] = [];
  let i = 0;

  while (i < html.length) {
    if (html[i] === '<') {
      const closeMatch = html.substring(i).match(/^<\/span>/);
      if (closeMatch) {
        classStack.pop();
        i += closeMatch[0].length;
        continue;
      }
      const openMatch = html.substring(i).match(/^<span class="hljs-([^"]*)">/);
      if (openMatch) {
        classStack.push(openMatch[1]);
        i += openMatch[0].length;
        continue;
      }
      // Unknown tag, treat as text
      tokens.push({ text: '<', className: classStack[classStack.length - 1] });
      i++;
    } else {
      // Collect text until next tag
      let end = html.indexOf('<', i);
      if (end === -1) end = html.length;
      const raw = html.substring(i, end);
      // Unescape HTML entities
      const text = raw
        .replace(/&amp;/g, '&')
        .replace(/&lt;/g, '<')
        .replace(/&gt;/g, '>')
        .replace(/&quot;/g, '"')
        .replace(/&#x27;/g, "'")
        .replace(/&#39;/g, "'");
      if (text) {
        tokens.push({ text, className: classStack[classStack.length - 1] });
      }
      i = end;
    }
  }
  return tokens;
}

interface Props {
  code: string;
  language?: string;
}

export function CodeBlock({ code, language }: Props) {
  const isDark = useIsDark();
  const tokenColors = isDark ? DARK_TOKEN_COLORS : LIGHT_TOKEN_COLORS;
  const defaultColor = isDark ? '#D4D4D4' : '#383A42';
  const bgColor = isDark ? '#1E1E2E' : '#F6F8FA';
  const labelColor = isDark ? '#888' : '#999';

  const tokens = useMemo(() => {
    const trimmed = code.replace(/\n$/, '');
    try {
      const lang = language?.toLowerCase();
      if (lang && hljs.getLanguage(lang)) {
        return parseHljsHtml(hljs.highlight(trimmed, { language: lang }).value);
      }
      // Auto-detect
      const result = hljs.highlightAuto(trimmed);
      return parseHljsHtml(result.value);
    } catch {
      return [{ text: trimmed }];
    }
  }, [code, language]);

  return (
    <View style={[styles.container, { backgroundColor: bgColor }]}>
      {language ? (
        <Text style={[styles.label, { color: labelColor }]}>{language}</Text>
      ) : null}
      <ScrollView horizontal showsHorizontalScrollIndicator={false}>
        <Text style={[styles.code, { color: defaultColor }]}>
          {tokens.map((token, i) => {
            if (token.className) {
              const color = tokenColors[token.className] ?? defaultColor;
              return (
                <Text key={i} style={{ color }}>
                  {token.text}
                </Text>
              );
            }
            return token.text;
          })}
        </Text>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    borderRadius: 8,
    marginVertical: 8,
    padding: 12,
    paddingTop: 8,
  },
  label: {
    fontSize: 11,
    fontFamily: 'monospace',
    marginBottom: 6,
    textAlign: 'right',
  },
  code: {
    fontFamily: 'monospace',
    fontSize: 13,
    lineHeight: 20,
  },
});
