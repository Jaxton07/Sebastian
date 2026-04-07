import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { useTheme } from '../../theme/ThemeContext';

interface Props {
  message: string;
  onAction: () => void;
}

export function ErrorBanner({ message, onAction }: Props) {
  const colors = useTheme() as any;
  return (
    <View
      style={[
        styles.container,
        { backgroundColor: colors.errorBg ?? '#FEF2F2', borderColor: colors.errorBorder ?? '#FCA5A5' },
      ]}
    >
      <Text style={[styles.message, { color: colors.errorText ?? '#991B1B' }]}>
        {message}
      </Text>
      <TouchableOpacity onPress={onAction} style={styles.actionBtn}>
        <Text style={[styles.actionText, { color: colors.errorText ?? '#991B1B' }]}>
          前往 Settings →
        </Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    marginHorizontal: 12,
    marginVertical: 8,
    padding: 12,
    borderRadius: 8,
    borderWidth: 1,
  },
  message: {
    fontSize: 14,
    lineHeight: 20,
    marginBottom: 8,
  },
  actionBtn: {
    alignSelf: 'flex-start',
  },
  actionText: {
    fontSize: 14,
    fontWeight: '600',
  },
});
