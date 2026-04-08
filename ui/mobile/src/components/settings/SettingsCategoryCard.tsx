import type { ReactNode } from 'react';
import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { RightArrowIcon } from '@/src/components/common/Icons';
import { useTheme } from '@/src/theme/ThemeContext';

interface Action {
  key: string;
  label: string;
  onPress: () => void;
  tone?: 'accent' | 'destructive';
}

interface Props {
  label: string;
  title: string;
  subtitle: string;
  onPress: () => void;
  actions?: Action[];
  leading?: ReactNode;
}

export function SettingsCategoryCard({
  label,
  title,
  subtitle,
  onPress,
  actions = [],
  leading,
}: Props) {
  const colors = useTheme();

  return (
    <TouchableOpacity
      activeOpacity={0.85}
      style={[styles.card, { backgroundColor: colors.cardBackground, shadowColor: colors.shadowColor }]}
      onPress={onPress}
    >
      <View style={styles.headerRow}>
        <View style={styles.labelRow}>
          {leading}
          <Text style={[styles.label, { color: colors.textSecondary }]}>{label}</Text>
        </View>
        <RightArrowIcon size={16} color={colors.textSecondary} />
      </View>

      <Text style={[styles.title, { color: colors.text }]}>{title}</Text>
      <Text style={[styles.subtitle, { color: colors.textSecondary }]}>{subtitle}</Text>

      {actions.length ? (
        <View style={[styles.actionsRow, { borderTopColor: colors.borderLight }]}>
          {actions.map((action) => (
            <TouchableOpacity
              key={action.key}
              style={[
                styles.actionButton,
                {
                  backgroundColor:
                    action.tone === 'destructive' ? colors.destructiveBg : colors.inputBackground,
                },
              ]}
              onPress={(event) => {
                event.stopPropagation();
                action.onPress();
              }}
            >
              <Text
                style={[
                  styles.actionText,
                  {
                    color: action.tone === 'destructive' ? colors.error : colors.accent,
                  },
                ]}
              >
                {action.label}
              </Text>
            </TouchableOpacity>
          ))}
        </View>
      ) : null}
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  card: {
    borderRadius: 20,
    padding: 16,
    marginBottom: 12,
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.08,
    shadowRadius: 14,
    elevation: 3,
  },
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  labelRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  label: {
    fontSize: 12,
    fontWeight: '700',
    letterSpacing: 0.8,
    textTransform: 'uppercase',
  },
  title: {
    marginTop: 14,
    fontSize: 24,
    fontWeight: '700',
  },
  subtitle: {
    marginTop: 8,
    fontSize: 14,
    lineHeight: 20,
  },
  actionsRow: {
    flexDirection: 'row',
    gap: 10,
    marginTop: 16,
    paddingTop: 14,
    borderTopWidth: StyleSheet.hairlineWidth,
  },
  actionButton: {
    minHeight: 38,
    paddingHorizontal: 14,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
  },
  actionText: {
    fontSize: 14,
    fontWeight: '600',
  },
});
