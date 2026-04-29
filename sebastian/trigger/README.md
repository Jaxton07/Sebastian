# trigger — 主动触发引擎

> 上级索引：[sebastian/](../README.md)

## 模块职责

`trigger/` 是 Sebastian 的后台任务调度基础设施，负责无用户输入情况下的主动执行。第一版实现单实例进程内 async 调度器，管理周期性系统维护任务（如附件清理）。

## 目录结构

```
trigger/
├── __init__.py      # 空模块入口
├── scheduler.py     # ScheduledJob, JobRegistry, SchedulerRunner
├── job_runs.py      # ScheduledJobRunStore：scheduled_job_runs 表读写
├── jobs.py          # register_builtin_jobs(...)：内置任务注册
└── README.md
```

## 修改导航

| 如果要修改… | 看这里 |
|------------|--------|
| 调度循环、并发策略、timeout 处理 | [scheduler.py](scheduler.py) 的 `SchedulerRunner` |
| 运行历史读写（start / finish / skipped） | [job_runs.py](job_runs.py) 的 `ScheduledJobRunStore` |
| 内置任务注册（新增/修改 job） | [jobs.py](jobs.py) 的 `register_builtin_jobs` |
| `scheduled_job_runs` ORM 模型 | [../store/models.py](../store/models.py) 的 `ScheduledJobRunRecord` |
| Gateway 启动/关闭集成 | [../gateway/app.py](../gateway/app.py) lifespan |

## 设计要点

- **Job definition 在代码中**，不持久化到数据库。重启后由 `ScheduledJobRunStore.get_last_success_at` 推导 `next_run_at`，避免重启瞬间集中执行。
- **`skip_if_running` 并发策略**：同一 job 上一次未结束时下一次触发只写 `skipped` 记录，不并发执行。
- **poll_interval 默认 30s**，可在构造 `SchedulerRunner` 时传入更短的值（如测试环境）。
- **Scheduler shutdown 必须在 `get_engine().dispose()` 之前**（gateway lifespan 已保证）。
- 进程崩溃可能留下 `status="running"` 的孤儿行，不影响重启恢复（恢复只查 `status="success"`）。

## 未来扩展接入点

- 新增系统维护任务：在 `jobs.py` 的 `register_builtin_jobs` 中 `registry.register(...)` 一行。
- 用户业务触发（提醒、定时消息）：新增 `user_triggers` 业务表 + `TriggerDispatcher`；scheduler 注册一个扫描 job，不在 `trigger/` 内处理业务语义。

---

> 修改本目录或模块后，请同步更新此 README。
