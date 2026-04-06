import { createContext, useContext, type ReactNode } from 'react';
import { useColorScheme } from 'react-native';
import { lightColors, darkColors, type ThemeColors } from './colors';
import { useSettingsStore } from '../store/settings';

interface ThemeContextValue {
  colors: ThemeColors;
  isDark: boolean;
}

const ThemeContext = createContext<ThemeContextValue>({
  colors: lightColors,
  isDark: false,
});

export function ThemeProvider({ children }: { children: ReactNode }) {
  const systemScheme = useColorScheme();
  const themeMode = useSettingsStore((s) => s.themeMode);

  let isDark: boolean;
  if (themeMode === 'system') {
    isDark = systemScheme === 'dark';
  } else {
    isDark = themeMode === 'dark';
  }

  const colors = isDark ? darkColors : lightColors;

  return (
    <ThemeContext.Provider value={{ colors, isDark }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme(): ThemeColors {
  return useContext(ThemeContext).colors;
}

export function useIsDark(): boolean {
  return useContext(ThemeContext).isDark;
}
