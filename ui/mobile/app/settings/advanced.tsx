import { DebugLogging } from '@/src/components/settings/DebugLogging';
import { MemorySection } from '@/src/components/settings/MemorySection';
import { SettingsScreenLayout } from '@/src/components/settings/SettingsScreenLayout';

export default function AdvancedSettingsScreen() {
  return (
    <SettingsScreenLayout
      title="高级"
      subtitle="查看低频设置、调试项以及后续开放的能力入口。"
    >
      <MemorySection />
      <DebugLogging />
    </SettingsScreenLayout>
  );
}
