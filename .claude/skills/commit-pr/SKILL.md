---
name: commit-pr
description: 提交代码并创建 PR 的标准流程。包含 rebase 检查、lint 验证、原子提交、PR 创建，防止重复 commit 和冲突。
---

# commit-pr - 提交代码并创建 PR

标准化从提交到 PR 的完整流程，确保 dev 与 main 同步、提交干净、CI 能过。

## 使用方式

```
/commit-pr
```

仅提交不建 PR：`/commit-pr --no-pr`

## 执行步骤

### 步骤 1：分支与同步检查

确认当前在 `dev` 分支：

```bash
git branch --show-current
```

若不在 `dev`，**终止**并提示切换。

同步 main 并 rebase：

```bash
git fetch origin main
git rebase origin/main
```

**这一步不可跳过。** 这是防止 PR 包含已合并 commit 的关键。

若 rebase 有冲突：
- 展示冲突文件列表
- 提示用户手动解决后再运行

rebase 成功后推送：

```bash
git push --force-with-lease
```

### 步骤 2：检查工作区状态

```bash
git status
git diff --stat
```

若没有可提交的改动，**终止**并提示。

展示改动摘要，让用户确认哪些文件需要提交。

### 步骤 3：危险文件检查

扫描改动文件，**拒绝**以下文件进入提交：

- `.env`、`*.key`、`credentials.*`、`secret.*` — 密钥/凭证
- `*.bak.*`、`.sebastian.bak.*` — 备份目录
- `node_modules/`、`.venv/`、`__pycache__/` — 依赖/缓存
- `*.pyc`、`.DS_Store` — 系统/编译产物

若发现上述文件在 untracked 中，**警告**用户并建议加入 `.gitignore`。

### 步骤 4：Lint 与格式化

后端改动：

```bash
ruff check sebastian/ tests/
ruff format --check sebastian/ tests/
```

若格式不对，自动修复：

```bash
ruff format sebastian/ tests/
```

前端改动（`ui/mobile/` 下有改动时）：

```bash
cd ui/mobile && npx tsc --noEmit
```

**Lint 不过不允许提交。**

### 步骤 5：运行测试

后端改动时：

```bash
pytest tests/unit/ -x -q
```

测试失败则**终止**，提示修复。

### 步骤 6：构建 commit

逐文件添加（**严禁** `git add .` 或 `git add -A`）：

```bash
git add <file1> <file2> ...
```

commit message 格式：`类型(范围): 中文摘要`

- 类型：`feat` / `fix` / `docs` / `refactor` / `chore` / `test` / `style` / `ci`
- 可在类型前加 emoji（参考 git log 现有风格）
- 一个 commit 只做一件事，保持原子化
- 末尾附 `Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>`（或当前实际模型）

若改动涉及多个不相关主题，拆分为多个 commit。

### 步骤 7：推送

```bash
git push
```

### 步骤 8：创建 PR（除非 `--no-pr`）

创建前再次确认 dev 领先 main 的 commit：

```bash
git log origin/main..HEAD --oneline
```

**关键检查：**
- 若 commit 数量异常多（>10），**暂停**并提示用户确认，可能是 rebase 不彻底
- 若 commit message 中出现已知的 main 上的 squash merge 标题（如 `#xx`），说明有重复，**终止**

确认无误后创建 PR：

```bash
gh pr create --base main --head dev --title "{title}" --body "$(cat <<'EOF'
## Summary
{1-3 条要点}

## Test plan
{验证步骤 checklist}

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

PR 规范：
- title 与 commit message 风格一致，控制在 70 字以内
- base 永远是 `main`
- Summary 写改了什么、为什么改
- Test plan 写验证步骤 checklist

### 步骤 9：输出结果

```
✓ 已提交并推送到 dev

Commits:
{commit list}

PR: {pr_url}
```

## PR 合并后

合并使用 squash merge（`gh pr merge --squash`）。

合并后必须立即同步 dev：

```bash
git fetch origin main
git rebase origin/main
git push --force-with-lease
```

**这一步防止下次 PR 出现重复 commit。** 若在 `/release` 之后执行，release workflow 产生的 version commit 也会在这一步同步进来。

## 常见问题

### PR 包含了已合并的 commit

原因：dev 没 rebase 到最新 main。

修复：

```bash
git fetch origin main
git rebase origin/main
git push --force-with-lease
```

squash merge 的 commit 会被 git 自动 skip（内容已在 main 中）。若有文件级冲突（如 CHANGELOG），解决后 `git rebase --continue`。

### CHANGELOG 冲突

原因：release workflow 修改了 main 上的 CHANGELOG（翻转 Unreleased 段），而 dev 上也有 CHANGELOG 改动。

处理：rebase 时保留 main 的版本（`git checkout --theirs CHANGELOG.md`），然后在 Unreleased 段重新添加新内容。
