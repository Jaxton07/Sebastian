import { AccountSettingsSection } from '@/src/components/settings/AccountSettingsSection';
import { ServerConfig } from '@/src/components/settings/ServerConfig';
import { SettingsScreenLayout } from '@/src/components/settings/SettingsScreenLayout';

export default function ConnectionSettingsScreen() {
  return (
    <SettingsScreenLayout
      title="连接与账户"
      subtitle="配置 Server 连接，并管理 Owner 登录状态。"
    >
      <ServerConfig />
      <AccountSettingsSection />
    </SettingsScreenLayout>
  );
}
