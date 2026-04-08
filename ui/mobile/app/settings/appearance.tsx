import { SettingsScreenLayout } from '@/src/components/settings/SettingsScreenLayout';
import { ThemeSettings } from '@/src/components/settings/ThemeSettings';

export default function AppearanceSettingsScreen() {
  return (
    <SettingsScreenLayout
      title="外观"
      subtitle="调整主题模式和当前界面显示风格。"
    >
      <ThemeSettings />
    </SettingsScreenLayout>
  );
}
