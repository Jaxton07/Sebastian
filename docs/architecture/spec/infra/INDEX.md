# Infra 模块 Spec 索引

*← [Spec 根索引](../INDEX.md)*

---

基础设施设计：发布流程、CI/CD 工作流、部署与安装。

| Spec | 摘要 |
|------|------|
| [release-cicd.md](release-cicd.md) | 首次配置 UX（Web 向导 + CLI 兜底）、版本管理（统一 SemVer）、bootstrap.sh 一键安装、CI 质量门禁（4 job）、release.yml 发版流水线、分支保护与 PR 规范、安全模型 |
| [install-flow.md](install-flow.md) | 数据目录 v2 布局（app/data/logs/run）、启动时自动迁移、`sebastian service` 服务化子命令（systemd/launchd）、install.sh 拆分重构、bootstrap.sh 覆盖保护 |

---

*← [Spec 根索引](../INDEX.md)*
