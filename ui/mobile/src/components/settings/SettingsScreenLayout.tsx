import type { ReactNode } from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { BackButton } from '@/src/components/common/BackButton';
import { useTheme } from '@/src/theme/ThemeContext';

interface Props {
  title: string;
  subtitle: string;
  children: ReactNode;
  showBack?: boolean;
}

export function SettingsScreenLayout({
  title,
  subtitle,
  children,
  showBack = true,
}: Props) {
  const insets = useSafeAreaInsets();
  const colors = useTheme();

  return (
    <ScrollView
      style={[styles.screen, { backgroundColor: colors.settingsBackground }]}
      contentContainerStyle={[
        styles.container,
        { paddingTop: insets.top + 12, paddingBottom: insets.bottom + 32 },
      ]}
    >
      {showBack ? <BackButton style={styles.backBtn} /> : null}

      <View style={styles.hero}>
        <Text style={[styles.heroTitle, { color: colors.text }]}>{title}</Text>
        <Text style={[styles.heroSubtitle, { color: colors.textSecondary }]}>
          {subtitle}
        </Text>
      </View>

      {children}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1 },
  container: { paddingHorizontal: 16 },
  backBtn: { alignSelf: 'flex-start', marginBottom: 8 },
  hero: { marginBottom: 18, paddingHorizontal: 4 },
  heroTitle: { fontSize: 34, fontWeight: '700' },
  heroSubtitle: { marginTop: 6, fontSize: 15, lineHeight: 21 },
});
