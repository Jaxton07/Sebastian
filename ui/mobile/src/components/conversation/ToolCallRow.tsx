import { View, Text, StyleSheet } from 'react-native';
import { useTheme } from '../../theme/ThemeContext';

interface Props {
  name: string;
  input: string;
  status: 'running' | 'done' | 'failed';
}

const DOT_COLOR: Record<Props['status'], string> = {
  running: '#f5a623',
  done: '#4caf50',
  failed: '#f44336',
};

/** Priority-ordered param keys to extract per tool name. */
const KEY_PRIORITY: Record<string, string[]> = {
  Bash:              ['command'],
  Read:              ['file_path'],
  Write:             ['file_path'],
  Edit:              ['file_path'],
  Grep:              ['pattern', 'path'],
  Glob:              ['pattern', 'path'],
  delegate_to_agent: ['goal'],
};

const GENERIC_KEYS = ['command', 'file_path', 'path', 'goal', 'pattern', 'query'];

/** Extract a human-readable summary from the JSON input string. */
function extractInputSummary(name: string, input: string): string {
  if (!input) return '';
  let parsed: Record<string, unknown>;
  try {
    parsed = JSON.parse(input) as Record<string, unknown>;
  } catch {
    // Not JSON (e.g. already a plain string) — truncate directly
    return input.length > 80 ? `${input.slice(0, 80)}…` : input;
  }

  const keys = KEY_PRIORITY[name] ?? GENERIC_KEYS;
  for (const key of keys) {
    const val = parsed[key];
    if (typeof val === 'string' && val.trim()) {
      const text = val.trim();
      return text.length > 80 ? `${text.slice(0, 80)}…` : text;
    }
  }

  // Fallback: first string value found in the object
  for (const val of Object.values(parsed)) {
    if (typeof val === 'string' && val.trim()) {
      const text = val.trim();
      return text.length > 80 ? `${text.slice(0, 80)}…` : text;
    }
  }

  return '';
}

export function ToolCallRow({ name, input, status }: Props) {
  const colors = useTheme();
  const inputPreview = extractInputSummary(name, input);

  return (
    <View style={styles.row}>
      <View style={[styles.dot, { backgroundColor: DOT_COLOR[status] }]} />
      <Text style={[styles.name, { color: colors.textSecondary }]}>{name}</Text>
      {inputPreview ? <Text style={[styles.input, { color: colors.textMuted }]}>{inputPreview}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 4,
    gap: 8,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    flexShrink: 0,
  },
  name: {
    fontSize: 13,
    fontWeight: '500',
    flexShrink: 0,
  },
  input: {
    fontSize: 13,
    flex: 1,
  },
});
