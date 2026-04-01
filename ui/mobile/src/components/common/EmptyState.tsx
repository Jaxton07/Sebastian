import { View, Text, StyleSheet } from 'react-native';

interface Props {
  message: string;
  ctaLabel?: string;
  onCta?: () => void;
}

export function EmptyState({ message, ctaLabel, onCta }: Props) {
  return (
    <View style={styles.container}>
      <Text style={styles.message}>{message}</Text>
      {ctaLabel && onCta && (
        <Text style={styles.cta} onPress={onCta}>{ctaLabel}</Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 32 },
  message: { color: '#999', textAlign: 'center', marginBottom: 12 },
  cta: { color: '#007AFF', fontWeight: 'bold' },
});
