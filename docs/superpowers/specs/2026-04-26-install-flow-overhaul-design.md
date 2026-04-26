# Install Flow Overhaul — Design

**Date**: 2026-04-26
**Branch**: `feat/install-flow-overhaul`
**Status**: Approved

## 1. 背景与目标

Sebastian 定位是"长期后台运行的个人 AI 管家"，但当前安装流程仍把它当一次性 CLI 工具：

- `~/.sebastian/` 一层混了 app 代码、用户数据、运行时状态（pid 文件）
- `install.sh` 末尾 `exec sebastian serve` 把首启向导和长期运行揉在一起，无法干净退出
- 没有系统服务集成（systemd / launchd），用户必须手动 `sebastian serve`
- `bootstrap.sh` 对已存在的安装目录直接 tar 覆盖，残留文件不清理

本次改造目标：

1. **数据目录结构化**：app / data / logs / run 各司其职
2. **服务化**：`sebastian service install/uninstall/start/stop/status` 子命令，支持 user-level systemd 和 launchd
3. **install.sh 拆分**：装完即退，可选询问是否注册服务，不再阻塞
4. **bootstrap.sh 收紧**：目标非空时拒绝覆盖，引导走 `sebastian update`

非目标：

- 不引入新的 daemon 进程管理框架（继续用现有 `sebastian/cli/daemon.py`）
- 不改 `SEBASTIAN_DATA_DIR` 环境变量语义（仍指 root `~/.sebastian/`）
- 不替用户跑 sudo（systemd linger 检测后只提示，不执行）

## 2. 数据目录新布局

```
~/.sebastian/
  app/                  # release 解压物 + venv，sebastian update 只动这里
    .venv/
    sebastian/...
    pyproject.toml
  data/                 # 用户数据
    sebastian.db
    secret.key          # chmod 600
    workspace/
    extensions/
  logs/                 # 日志
    sebastian.log
    service.out.log     # 服务模式 stdout
    service.err.log     # 服务模式 stderr
  run/                  # 运行时状态
    sebastian.pid
    update-backups/     # update 回滚专用
  .layout-v2            # 迁移完成标记，存 schema 版本号 "2\n"
```

**说明**：

- `sessions/` 已废弃（session 现存 db），迁移时直接清理
- `~/.sebastian/backups/`（旧版 update 回滚目录）迁移到 `run/update-backups/`，与"用户数据 backup"概念分开。当前没有真实"用户数据 backup"功能，因此 `data/` 下不建 `backups/`
- `SEBASTIAN_DATA_DIR` 仍指 root，环境变量语义不变

## 3. 配置 API 重构

[sebastian/config/__init__.py](../../../sebastian/config/__init__.py) 调整：

| 原属性 | 新值 / 改动 |
|--------|------------|
| `data_dir` | **保持不变**，= root (`~/.sebastian/`) |
| `database_url` | `f"sqlite+aiosqlite:///{user_data_dir}/sebastian.db"` |
| `sessions_dir` | **删除**（已废弃） |
| `extensions_dir` | `user_data_dir / "extensions"` |
| `workspace_dir` | `user_data_dir / "workspace"` |
| `resolved_secret_key_path()` | `user_data_dir / "secret.key"` |

新增属性：

```python
@property
def user_data_dir(self) -> Path:
    return self.data_dir / "data"

@property
def logs_dir(self) -> Path:
    return self.data_dir / "logs"

@property
def run_dir(self) -> Path:
    return self.data_dir / "run"
```

`ensure_data_dir()` 改为创建 `user_data_dir/extensions/{skills,agents}`、`user_data_dir/workspace`、`logs_dir`、`run_dir`，删掉 `sessions/sebastian`。

## 4. 启动时自动迁移

新增 [sebastian/store/migration.py](../../../sebastian/store/migration.py)::`migrate_layout_v2()`，调用时机：

- `sebastian serve`：启动早期、`init_db()` **之前**调用（必须先于打开 db）
- `sebastian init` / `sebastian init --headless`：在初始化向导**最开始**调用，确保后续写 db / secret.key 用新路径
- 任何依赖 `settings.user_data_dir` 的 CLI 子命令首次访问前调用一次（推荐放进 `cli/__init__.py` 的全局入口装饰器）

```python
def migrate_layout_v2(data_root: Path) -> None:
    marker = data_root / ".layout-v2"
    if marker.exists():
        return

    legacy_db = data_root / "sebastian.db"
    if not legacy_db.exists():
        # 全新安装，建空骨架
        _ensure_new_dirs(data_root)
        marker.write_text("2\n")
        return

    logger.info("Detected v1 layout, migrating to v2...")
    (data_root / "data").mkdir(exist_ok=True)
    (data_root / "run").mkdir(exist_ok=True)
    (data_root / "logs").mkdir(exist_ok=True)

    # 用户数据 → data/
    for name in ["sebastian.db", "secret.key", "workspace", "extensions"]:
        src = data_root / name
        if src.exists():
            shutil.move(str(src), str(data_root / "data" / name))

    # pid → run/
    pid_src = data_root / "sebastian.pid"
    if pid_src.exists():
        shutil.move(str(pid_src), str(data_root / "run" / "sebastian.pid"))

    # 旧 update 回滚目录 → run/update-backups
    legacy_backups = data_root / "backups"
    if legacy_backups.exists():
        shutil.move(str(legacy_backups), str(data_root / "run" / "update-backups"))

    # 已废弃
    sessions = data_root / "sessions"
    if sessions.exists():
        shutil.rmtree(sessions)

    marker.write_text("2\n")
    logger.info("Layout migration v2 complete")
```

**保证**：

- 同一文件系统内 `mv` 是原子的
- 函数失败抛异常，启动直接终止；标记文件只在最后写入，半迁移状态不会被误判完成
- 标记内容 `2\n`，未来再升级直接读数字判断

## 5. 系统服务子命令

新增 [sebastian/cli/service.py](../../../sebastian/cli/service.py)，挂在 `sebastian service` 下。

### 5.1 子命令

```
sebastian service install     # 写 unit/plist + 启用
sebastian service uninstall   # 停止 + 删除 unit/plist
sebastian service start       # 启动
sebastian service stop        # 停止
sebastian service status      # active/inactive + tail logs
```

### 5.2 平台分发

- **Linux** → `~/.config/systemd/user/sebastian.service`，user-level，无需 sudo
- **macOS** → `~/Library/LaunchAgents/com.sebastian.plist`
- **其他平台** → 报错退出 `unsupported platform: <os>`

### 5.3 systemd unit 模板

```ini
[Unit]
Description=Sebastian personal AI butler
After=network-online.target

[Service]
Type=simple
ExecStart=%h/.sebastian/app/.venv/bin/sebastian serve
Restart=on-failure
RestartSec=5
StandardOutput=append:%h/.sebastian/logs/service.out.log
StandardError=append:%h/.sebastian/logs/service.err.log

[Install]
WantedBy=default.target
```

`install` 后调 `systemctl --user daemon-reload && systemctl --user enable --now sebastian.service`。

**Linger 检测**：`loginctl show-user $USER -P Linger`，未开则打印：

```
⚠ 当前用户未开启 linger，重启后服务不会自动拉起。如需开机自启请执行：
    sudo loginctl enable-linger $USER
```

### 5.4 launchd plist 模板

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.sebastian</string>
  <key>ProgramArguments</key>
  <array>
    <string>{HOME}/.sebastian/app/.venv/bin/sebastian</string>
    <string>serve</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>{HOME}/.sebastian/logs/service.out.log</string>
  <key>StandardErrorPath</key><string>{HOME}/.sebastian/logs/service.err.log</string>
</dict>
</plist>
```

`install` 后调 `launchctl load -w ~/Library/LaunchAgents/com.sebastian.plist`。

### 5.5 边界处理

- install 时已存在同名 unit/plist：报错并提示先 `service uninstall`
- status 输出：服务状态 + `tail -n 20 service.err.log`

## 6. install.sh 重构

[scripts/install.sh](../../../scripts/install.sh) 新流程：

```
1. OS / Python 3.12+ 检查（保持）
2. venv 创建 + 依赖安装（保持）
3. sebastian init —— 进入首启向导
   - 已初始化（检测 user_data_dir/sebastian.db 存在）则跳过
   - 未初始化：
     * 有 $DISPLAY 或 macOS → 默认跑 web wizard
     * 否则 → sebastian init --headless
4. 询问："是否注册为开机自启服务？[y/N]" 默认 N
   - y → sebastian service install + sebastian service start
   - n → 打印 hint：你可以稍后跑 sebastian service install 注册
5. 打印下一步指引并退出（不再 exec sebastian serve）
   - 服务已注册：打印 sebastian service status 命令、Android 配置 URL
   - 未注册：打印 sebastian serve 启动命令、Android 配置 URL
```

关键：去掉末尾 `exec sebastian serve`。

## 6.1 dev.sh 同步

[scripts/dev.sh](../../../scripts/dev.sh) 主体不变（仍 `exec sebastian serve --reload`，迁移会在 serve 启动时自动跑），只需调整：

1. **首次初始化提示文案**：把 "启动后会进入初始化向导" 这段保留，再补一行说明新布局：
   ```
   →  首次使用开发数据目录: ~/.sebastian-dev
      数据将分布在 ~/.sebastian-dev/{app,data,logs,run} 子目录
   ```
2. 不需要在 dev.sh 内显式调 `sebastian init`——`sebastian serve` 检测到无 db 会自动唤起 wizard，行为和生产路径保持一致
3. 不需要改端口/路径变量

dev.sh 改动随 commit 5（install.sh 重构）一起提交。

## 7. bootstrap.sh 收紧

[bootstrap.sh](../../../bootstrap.sh) 在解压前增加目标检测：

```bash
if [[ -d "$INSTALL_DIR" && -n "$(ls -A "$INSTALL_DIR" 2>/dev/null)" ]]; then
  if [[ -f "$INSTALL_DIR/pyproject.toml" ]]; then
    color_red "❌ 检测到 $INSTALL_DIR 已有 Sebastian 安装"
    color_red "   全新安装请先删除该目录；升级请使用："
    color_red "       cd $INSTALL_DIR && sebastian update"
    exit 1
  else
    color_red "❌ $INSTALL_DIR 非空但不是 Sebastian 安装目录，已中止以防覆盖"
    exit 1
  fi
fi
```

## 8. 全局一致性修复

### 8.1 daemon pid 路径

[sebastian/cli/daemon.py:8-10](../../../sebastian/cli/daemon.py)：

```python
def pid_path(run_dir: Path) -> Path:
    """Return path of sebastian.pid inside run_dir."""
    return run_dir / "sebastian.pid"
```

形参从 `data_dir` 重命名为 `run_dir`，调用方全部传 `settings.run_dir`。

### 8.2 updater 回滚目录

[sebastian/cli/updater.py:175-179](../../../sebastian/cli/updater.py)：

```python
def _backup_parent() -> Path:
    """Return run_dir/update-backups, creating it if needed."""
    from sebastian.config import settings
    d = settings.run_dir / "update-backups"
    d.mkdir(parents=True, exist_ok=True)
    return d
```

### 8.3 updater 重启 daemon

[sebastian/cli/updater.py:266-267](../../../sebastian/cli/updater.py)：

```python
pf = pid_path(settings.run_dir)  # 原 settings.data_dir
```

### 8.4 文档同步

需要在最后一个 commit 一并更新的文档：

- [README.md](../../../README.md)（项目根）：安装/启动小节改成新布局示意 + 新增"作为系统服务运行"小节，说明 `sebastian service install` 用法；如有目录结构图同步更新
- [sebastian/config/README.md](../../../sebastian/config/README.md)：目录结构表把 `sessions/extensions/workspace` 改成新布局描述，新增 `user_data_dir` / `logs_dir` / `run_dir` 属性说明
- [CLAUDE.md](../../../CLAUDE.md)：第 3 节"构建与启动"和第 6 节"运行时环境变量"中关于 `~/.sebastian/` 直接放 db/secret.key 的描述全部更新为新布局；新增"系统服务"用法段

## 9. 测试

### 9.1 单元测试

- `tests/unit/test_layout_migration.py`（新）
  - v1 → v2：构造旧布局，断言新位置正确、`sessions/` 删除、`backups/` → `run/update-backups/`、`.layout-v2` 存在
  - 已迁移：标记存在时不动文件
  - 全新安装（无 `sebastian.db`）：建空骨架 + 标记
- `tests/unit/test_config_paths.py`（新或扩展）
  - `user_data_dir` / `logs_dir` / `run_dir` 路径正确
  - `database_url` / `extensions_dir` / `workspace_dir` / `resolved_secret_key_path` 全部落在 `data/` 子目录
- `tests/unit/test_service_install.py`（新）
  - 渲染 systemd unit 模板（patch `sys.platform = "linux"`）：验证 ExecStart、StandardOutput、Restart 字段
  - 渲染 launchd plist 模板（patch `sys.platform = "darwin"`）：验证 Label、ProgramArguments、StandardOutPath
  - mock `subprocess.run` 验证 systemctl/launchctl 调用参数
  - install 时目标文件已存在 → raise，提示 uninstall

### 9.2 集成测试

- `tests/integration/test_updater_paths.py`（新）：updater 的 `_backup_parent()` 落到 `run_dir / "update-backups"`，rollback 路径正确

### 9.3 手动验证清单（PR 描述）

1. macOS 本地：`./scripts/dev.sh` 启动，`~/.sebastian-dev/` 自动建出新布局
2. macOS 旧布局迁移：删 `~/.sebastian/.layout-v2` 造旧布局假象 → `sebastian serve` → 看迁移日志和文件位置
3. macOS 服务：`sebastian service install` → `launchctl list | grep sebastian` → `service status` 显示 running → `service uninstall`
4. Linux（Docker 或 VM）：systemd user unit install + status，验证 linger 提示
5. install.sh 全流程：fresh `~/.sebastian-test/` → 看 wizard、看服务注册询问、看退出而非阻塞
6. bootstrap.sh：模拟 `~/.sebastian/app/` 已有 `pyproject.toml` → 跑 bootstrap → 报错引导 `sebastian update`

## 10. 提交计划

单 PR，多 commit，顺序：

1. `refactor(config): 引入 user_data_dir/logs_dir/run_dir`
2. `feat(store): layout v2 自动迁移`
3. `refactor(daemon,updater): pid 与 update 回滚改用 run_dir`
4. `feat(cli): sebastian service install/uninstall/start/stop/status`
5. `refactor(install,dev): 拆分首启与运行，dev.sh 提示同步`
6. `fix(bootstrap): 目标非空时拒绝覆盖`
7. `test: 布局迁移、服务安装、updater 路径单测`
8. `docs: 同步 README、config README、CLAUDE.md`

## 11. 风险与回滚

- **迁移失败**：抛异常终止启动，文件留在原位（mv 已迁的部分仍在新位置），用户可手动 `mv` 回去再修复。设计上不做"半回滚"，因为 mv 是原子的，定位问题更直接
- **服务模板平台差异**：systemd 路径用 `%h` 占位符，launchd 路径用真实 HOME 渲染（plist 不支持环境变量替换）
- **现有 daemon 在跑**：迁移期间用户进程持有旧 pid 文件路径——要求迁移在 daemon 启动早期、读 pid 之前完成；如果是从 systemd/launchd 拉起的服务，service install 后第一次启动会触发迁移，正常
