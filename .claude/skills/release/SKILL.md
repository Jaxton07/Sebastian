---
name: release
description: 发布新版本。同步 dev 到 main，通过 GitHub Actions release workflow 自动构建后端 tarball + Android APK 并发布 GitHub Release。
---

# release - 发布新版本

将 dev 分支的改动合入 main，通过 `gh workflow run release.yml` 触发自动发版，产物包含 backend tarball、签名 APK 和 SHA256SUMS。

## 使用方式

```
/release
```

可选参数：`/release 0.2.6`（直接指定版本号，跳过版本号询问）

## 前置条件（人工完成）

1. 相关改动已通过 PR squash merge 合入 `main`

> CHANGELOG 若尚未填写，步骤 3 会处理。

## CHANGELOG 机制说明（必读）

Release workflow（`.github/workflows/release.yml`）处理 CHANGELOG 的方式：

```python
# 伪代码，见 release.yml sync-version job
content.replace("## [Unreleased]", "## [Unreleased]\n\n## [0.2.6] - 2026-04-10", 1)
```

即：**在 `## [Unreleased]` 后面插入一行版本标题，Unreleased 段下面的条目原封不动保留**。

因此正确的 CHANGELOG 格式是：

```markdown
## [Unreleased]

### Added
- 新功能描述...

### Fixed
- 修复描述...
```

**严禁**在 Unreleased 段内自己写 `## [0.2.6]` 这样的版本标题，否则 workflow 运行后会出现重复标题。

### 分类

按以下顺序使用三级标题，只保留有内容的分类：

- `### Added` — 新功能、新命令、新文件
- `### Changed` — 现有功能的行为变更、接口调整
- `### Fixed` — Bug 修复
- `### Removed` — 删除的功能或文件

### 格式规则

- 每条以 `- ` 开头，写**用户视角的变更**，不是搬运 commit message
- 多行续写缩进 2 空格对齐
- Breaking change 在条目前加 `**[breaking]**` 标记
- 条目粒度：一个用户可感知的变更一条，相关的小改动合并写

### 何时写

每次向 dev 提交功能/修复时就更新 `[Unreleased]`，不要攒到发版前一次性补。

## 执行步骤

### 步骤 1：环境检查

确认当前在 `dev` 分支：

```bash
git branch --show-current
```

若不在 `dev`，切换过去。若有未提交改动，提示用户先处理。

### 步骤 2：同步 dev 到 main

**注意**：本项目使用 squash merge，PR 合并后 dev 的所有历史 commit 已被压缩进 main 的一个新 commit。此时 `git rebase` 会产生大量虚假冲突，必须用 `reset --hard`：

```bash
git fetch origin main
git reset --hard origin/main
git push --force-with-lease
```

### 步骤 3：确认 CHANGELOG

读取 `CHANGELOG.md` 的 `[Unreleased]` 段内容：

```bash
awk '/^## \[Unreleased\]/{found=1; next} found && /^## \[/{exit} found{print}' CHANGELOG.md
```

**情况 A：Unreleased 有内容** → 直接进入步骤 4。

**情况 B：Unreleased 为空** → 需要先补充 CHANGELOG，再合并到 main：

1. 读取 `git log` 找出上个版本 tag 之后的所有 commit，归纳用户可感知的变更
2. 按格式写入 `## [Unreleased]` 段（**只写条目，不写版本号标题**）
3. 提交到 dev 并 push：
   ```bash
   git add CHANGELOG.md
   git commit -m "docs(changelog): 补充 Unreleased 发版记录"
   git push
   ```
4. 创建 PR 并等待用户合并到 main（CI 须全绿）：
   ```bash
   gh pr create --base main --head dev --title "docs(changelog): 补充 Unreleased 发版记录"
   ```
5. 用户合并后，重新执行步骤 2（reset --hard）同步 dev

### 步骤 4：确定版本号

若用户通过参数指定了版本号，直接使用。

否则，读取当前版本：

```bash
grep -m1 '^version' pyproject.toml
```

根据 Unreleased 内容建议版本号：
- 有 `### Added` 或 `### Changed`（含 breaking）→ minor bump
- 仅 `### Fixed` → patch bump

向用户展示建议版本号和 Unreleased 内容摘要，**等待用户确认或修改**。

### 步骤 5：验证 CI 状态

```bash
gh run list --branch main --limit 3 --json status,conclusion,displayTitle,url
```

- 最近一次 `conclusion` 为 `success`：继续
- 其他状态：**警告**用户，展示具体状态，询问是否继续

### 步骤 6：输出确认摘要

打印发布摘要，**暂停并等待用户确认**：

```
即将执行以下操作：

  当前版本：{current_version}
  发布版本：v{version}
  触发方式：gh workflow run release.yml -f version={version} --ref main

  Workflow 将自动：
  - 更新 pyproject.toml + ui/mobile/app.json 版本号
  - 将 CHANGELOG.md [Unreleased] 段插入 [{version}] - YYYY-MM-DD 版本标题
  - commit + tag + push 到 main
  - 构建 backend tarball + 签名 Android APK
  - 发布 GitHub Release

请确认是否继续发布？
```

**等待用户明确确认后再继续。**

### 步骤 7：触发 release workflow

```bash
gh workflow run release.yml -f version={version} --ref main
```

获取 run ID 并开始跟踪：

```bash
gh run list --workflow=release.yml --limit 1 --json databaseId,status,url
gh run watch {run_id} --exit-status
```

Android 构建约 20 分钟，使用后台模式跟踪，完成后通知用户。

### 步骤 8：发版后同步 dev

workflow 完成后，release workflow 在 main 上产生了新 commit（`chore(release): v{version}`）。同样用 reset --hard 同步：

```bash
git fetch origin main
git reset --hard origin/main
git push --force-with-lease
```

### 步骤 9：输出结果

用 `gh repo view --json nameWithOwner` 获取 `{owner}/{repo}`，然后输出：

```
v{version} 发布成功！

GitHub Release：
https://github.com/{owner}/{repo}/releases/tag/v{version}

产物：
- sebastian-backend-v{version}.tar.gz
- sebastian-app-v{version}.apk
- SHA256SUMS

用户端升级：sebastian update
全新安装：curl -fsSL https://raw.githubusercontent.com/{owner}/{repo}/main/bootstrap.sh | bash
```

## 注意事项

- **严禁** 在非 `main` ref 上触发 release workflow
- **严禁** `git push --force` 到 main
- **严禁** 在 Unreleased 段写版本号标题（如 `## [0.2.6]`），workflow 会自动插入
- squash merge 后同步 dev 必须用 `reset --hard origin/main`，不能用 `rebase`（会产生虚假冲突）
- Release workflow 使用 `RELEASE_TOKEN`（admin PAT）push tag 和 commit，绕过分支保护
- tag `v*.*.*` 只有 admin 和 `github-actions[bot]` 可创建
- 若需要回滚，在 GitHub 上删除 release + tag，然后 revert main 上的版本 commit
