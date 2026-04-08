# components/settings/

> 上级：[components/](../README.md)

## 目录职责

设置页的 UI 组件集合，负责设置首页状态卡、分类详细页区块、Provider 列表与编辑表单、调试日志开关和 Memory 管理占位项的渲染与交互，整体向 iOS Settings.app 风格靠拢。

## 目录结构

```
settings/
├── ProviderEditorLayout.tsx   # Provider 新增/编辑专用布局（顶部悬浮返回/完成）
├── SettingsScreenLayout.tsx   # 设置页通用容器（返回键、标题、副标题、滚动布局）
├── SettingsCategoryCard.tsx   # 设置首页状态卡（摘要 + 快捷操作）
├── settingsSummary.ts         # 首页摘要文案规则（连接 / Provider / 外观 / 高级）
├── SettingToggleRow.tsx       # 设置列表式开关行（供外观 / 调试开关复用）
├── ServerConfig.tsx           # Server URL 配置与连接测试
├── AccountSettingsSection.tsx # Owner 登录 / 登出区块
├── ProviderListSection.tsx    # Provider 列表、空状态与删除操作
├── ProviderForm.tsx           # Provider 新增 / 编辑表单
├── ThemeSettings.tsx          # 外观设置（日间/夜间主题选择）
├── MemorySection.tsx          # Memory 管理占位入口（不可点击，预留 Phase 3+）
└── DebugLogging.tsx           # 调试日志开关（llm_stream / sse）
```

## 修改导航

| 如果要修改… | 看这里 |
|------------|--------|
| 修改设置首页骨架或标题区 | [SettingsScreenLayout.tsx](SettingsScreenLayout.tsx) |
| 修改设置首页状态卡或快捷操作 | [SettingsCategoryCard.tsx](SettingsCategoryCard.tsx) |
| 修改设置首页摘要文案规则 | [settingsSummary.ts](settingsSummary.ts) |
| 修改通用设置开关行样式 | [SettingToggleRow.tsx](SettingToggleRow.tsx) |
| 修改 Server URL 输入 / 连接测试 | [ServerConfig.tsx](ServerConfig.tsx) |
| 修改 Owner 登录 / 登出区块 | [AccountSettingsSection.tsx](AccountSettingsSection.tsx) |
| 修改 LLM Provider 列表 / 空状态 / 删除入口 | [ProviderListSection.tsx](ProviderListSection.tsx) |
| 修改 Provider 新增 / 编辑页的顶部悬浮操作布局 | [ProviderEditorLayout.tsx](ProviderEditorLayout.tsx) |
| 修改 LLM Provider 新增 / 编辑表单 | [ProviderForm.tsx](ProviderForm.tsx) |
| 修改主题选择（日间/夜间/跟随系统） | [ThemeSettings.tsx](ThemeSettings.tsx) |
| 修改 Memory 管理入口内容 | [MemorySection.tsx](MemorySection.tsx) |
| 修改调试日志开关项 | [DebugLogging.tsx](DebugLogging.tsx) |

---

> 修改本目录后，请同步更新此 README。
