# memory

> 上级索引：[sebastian/](../README.md)

## 模块职责

长期记忆系统，为 Agent 提供画像、经历、关系等跨会话记忆能力。

- **工作记忆**：`WorkingMemory`，进程内按 task_id 隔离的临时状态，任务结束后自动清除。
- **长期记忆写入**：候选 artifact 经 validate → resolve → persist → log 流水线落库，LLM 输出永远不直接修改记忆状态，必须经 Normalize / Resolve 流程。
- **长期记忆检索**：每次 LLM turn 前通过 `retrieve_for_prompt()` 拉取画像与经历，拼入 system prompt；`memory_search` 工具支持四通道显式搜索。
- **常驻记忆快照**：高频信息（slot 值）在会话沉淀完成后预建快照，下轮对话前以固定顺序注入 prompt，避免每次走检索流程。
- **LLM 沉淀**：会话结束后后台触发 `SessionConsolidationWorker`，提取候选 artifact，经写入流水线落库。
- **Dynamic Slot System**：LLM 可提议新的记忆维度（slot），提议经校验后写入 DB 并热更新 registry。

会话对话历史不经过本模块，由 `SessionStore` 直接管理（见 [store/README.md](../store/README.md)）。

语义记忆（向量检索）为后续规划能力，当前未实现。

---

## 服务边界

外部调用方只通过 `contracts/` + `services/` 访问记忆功能，不直接操作内部子包。

### `contracts/` — 服务契约模型

| 文件 | 内容 |
|------|------|
| [contracts/retrieval.py](contracts/retrieval.py) | `PromptMemoryRequest`、`PromptMemoryResult`、`ExplicitMemorySearchRequest`、`ExplicitMemorySearchResult` |
| [contracts/writing.py](contracts/writing.py) | `MemoryWriteRequest`、`MemoryWriteResult` |

### `services/` — 服务 Facade

| 文件 | 职责 |
|------|------|
| [services/memory_service.py](services/memory_service.py) | `MemoryService`：顶层 facade，暴露 `retrieve_for_prompt()`、`search()`、`write_candidates()`、`write_candidates_in_session()`、`is_enabled()` |
| [services/retrieval.py](services/retrieval.py) | `MemoryRetrievalService`：封装检索 pipeline |
| [services/writing.py](services/writing.py) | `MemoryWriteService`：封装写入 pipeline |

**外部调用方：**

| 调用方 | 接口 |
|--------|------|
| `BaseAgent._memory_section()` | `MemoryService.retrieve_for_prompt()` |
| `memory_search` 工具 | `MemoryService.search()` |
| `memory_save` 工具 | `MemoryService.write_candidates()` |
| `SessionConsolidationWorker` | `MemoryService.write_candidates_in_session()` |

---

## 目录结构

```
memory/
├── __init__.py
├── contracts/               # 服务契约 Pydantic 模型
│   ├── retrieval.py         # PromptMemoryRequest/Result, ExplicitMemorySearchRequest/Result
│   └── writing.py           # MemoryWriteRequest, MemoryWriteResult
├── services/                # 服务 Facade
│   ├── memory_service.py    # MemoryService — 顶层 facade
│   ├── retrieval.py         # MemoryRetrievalService
│   └── writing.py           # MemoryWriteService
├── stores/                  # 持久化存储 CRUD
│   ├── profile_store.py     # ProfileMemoryStore：画像 CRUD、search_active、supersede
│   ├── episode_store.py     # EpisodeMemoryStore：经历写入、FTS 检索、summary-first 两阶段
│   ├── entity_registry.py   # EntityRegistry：实体 CRUD（entities 表）
│   └── slot_definition_store.py  # SlotDefinitionStore：memory_slots 表 CRUD
├── writing/                 # 写入流水线
│   ├── pipeline.py          # process_candidates()：validate→resolve→persist→log 统一入口
│   ├── resolver.py          # MemoryResolver：冲突检测 + ResolveDecision 生成
│   ├── write_router.py      # persist_decision()：按 kind 分发 artifact 到各 store
│   ├── decision_log.py      # MemoryDecisionLogger：ResolveDecision 写入审计日志
│   ├── feedback.py          # MemorySaveResult + render_memory_save_summary()
│   ├── slot_proposals.py    # SlotProposalHandler：proposed slot 校验、注册、并发 race 保护
│   └── slots.py             # SlotRegistry + 10 个内置 SlotDefinition + DEFAULT_SLOT_REGISTRY
├── retrieval/               # 检索流水线
│   ├── retrieval.py         # MemoryRetrievalPlanner → 查 DB → MemorySectionAssembler
│   ├── retrieval_lexicon.py # 静态词库：各 lane 触发词
│   ├── depth_guard.py       # depth >= 2 的 sub-agent 跳过检索
│   └── segmentation.py      # jieba FTS 分词：索引分词、查询 term、实体词注入
├── consolidation/           # LLM 沉淀
│   ├── consolidation.py     # MemoryConsolidator + SessionConsolidationWorker + MemoryConsolidationScheduler
│   ├── extraction.py        # MemoryExtractor：LLM 提取候选 artifact，支持 slot 拒绝重试
│   ├── prompts.py           # Extractor / Consolidator 共享 prompt 模板
│   └── provider_bindings.py # LLM binding 常量：MEMORY_EXTRACTOR_BINDING / MEMORY_CONSOLIDATOR_BINDING
├── resident/                # 常驻记忆快照
│   ├── resident_snapshot.py # ResidentMemorySnapshotRefresher：快照读写、脏标记、重建触发
│   └── resident_dedupe.py   # canonical_bullet / slot_value_dedupe_key 等去重纯函数
├── constants.py             # 模块级常量
├── errors.py                # 异常体系（InvalidCandidateError / InvalidSlotProposalError 等）
├── startup.py               # init_memory_storage()：建 FTS 虚拟表；seed_builtin_slots；bootstrap_slot_registry
├── store.py                 # MemoryStore：聚合 working memory
├── subject.py               # resolve_subject()：按 scope/session/agent 派生 subject_id
├── trace.py                 # MEMORY_TRACE 调试日志辅助
├── types.py                 # 核心 Pydantic models 与 StrEnum（MemoryArtifact、CandidateArtifact、SlotDefinition 等）
└── working_memory.py        # WorkingMemory：进程内 dict，按 task_id 隔离
```

---

## 关键约束

**LLM 永远不直接修改记忆状态。** `MemoryExtractor` 和 `MemoryConsolidator` 的输出都是候选 artifact，最终写入前必须经过 `process_candidates()` 的 validate → resolve → persist 流程。

---

## 链路文档

- [data-flow.md](data-flow.md) — 读写链路完整解析：检索注入、各通道查库方式、memory_save 工具、Session Consolidation、process_candidates 管道、Slot 边界

---

## 修改导航

| 如果要修改… | 看这里 |
|------------|--------|
| 外部调用记忆系统（检索注入、工具、沉淀） | [services/memory_service.py](services/memory_service.py) |
| 服务入参 / 返回值数据结构 | [contracts/retrieval.py](contracts/retrieval.py)、[contracts/writing.py](contracts/writing.py) |
| 检索服务内部逻辑 | [services/retrieval.py](services/retrieval.py) |
| 写入服务内部逻辑 | [services/writing.py](services/writing.py) |
| 任务临时状态（set/get/clear） | [working_memory.py](working_memory.py) |
| session 对话历史（append_message / get_context_messages） | `SessionStore`（见 [store/README.md](../store/README.md)） |
| 记忆 artifact、slot、决策等数据结构 | [types.py](types.py) |
| slot 定义、内置 slot、候选 artifact slot 校验 | [writing/slots.py](writing/slots.py) |
| SQLite FTS5 中文分词、查询 term 生成、实体词注入 | [retrieval/segmentation.py](retrieval/segmentation.py) |
| 记忆决策审计日志 | [writing/decision_log.py](writing/decision_log.py) |
| Profile 画像写入、查询、supersede | [stores/profile_store.py](stores/profile_store.py) |
| 经历事件写入与 FTS 检索 | [stores/episode_store.py](stores/episode_store.py) |
| 每轮检索 pipeline（planner → fetch → assemble） | [retrieval/retrieval.py](retrieval/retrieval.py) |
| memory 链路调试日志（MEMORY_TRACE） | [trace.py](trace.py) |
| 画像冲突检测与决策生成 | [writing/resolver.py](writing/resolver.py) |
| 实体管理（CRUD） | [stores/entity_registry.py](stores/entity_registry.py) |
| LLM binding 常量（extractor / consolidator） | [consolidation/provider_bindings.py](consolidation/provider_bindings.py) |
| 从会话片段提取候选 artifact（LLM 提取） | [consolidation/extraction.py](consolidation/extraction.py) |
| 候选 artifact 统一写入（validate→resolve→persist→log） | [writing/pipeline.py](writing/pipeline.py) |
| 会话沉淀 Worker、Consolidator、Scheduler | [consolidation/consolidation.py](consolidation/consolidation.py) |
| Extractor / Consolidator 共享 prompt 模板 | [consolidation/prompts.py](consolidation/prompts.py) |
| 动态 slot DB 存储（memory_slots 表 CRUD） | [stores/slot_definition_store.py](stores/slot_definition_store.py) |
| 动态 slot 校验、注册、并发 race 保护 | [writing/slot_proposals.py](writing/slot_proposals.py) |
| memory_save 结构化结果与摘要渲染 | [writing/feedback.py](writing/feedback.py) |
| 常驻记忆快照读写、脏标记、重建触发 | [resident/resident_snapshot.py](resident/resident_snapshot.py) |
| 常驻记忆去重纯函数 | [resident/resident_dedupe.py](resident/resident_dedupe.py) |
| 语义记忆 / 向量检索（待实现） | 新建 `semantic_memory.py`，按需在 `store.py` 注册 |

---

> 修改本目录或模块后，请同步更新此 README。
