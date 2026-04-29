---
date: 2026-04-29
status: draft
topic: attachment-storage-dedup-cleanup-thumbnails
---

# Attachment Storage: Dedup, Ref-Counted Cleanup, Thumbnails

## 1. 背景

`AttachmentStore.upload_bytes` 已经按 SHA-256 把 blob 写到 `blobs/<sha[:2]>/<sha>`，路径是内容寻址的——同内容必然映射到同一文件。但当前实现存在两个问题：

1. **重复写入**：每次上传都把数据写到 `tmp/`，再 `os.replace` 覆盖到目标 blob 路径，即便目标 blob 已经存在内容相同的文件。多次发送同一文件浪费 I/O。
2. **`cleanup` 与共享 blob 的潜在冲突**：现有 `cleanup` 按 record 逐条 `blob.unlink(...)`，没有引用计数。多条 `AttachmentRecord` 指向同一个 blob 时（常见，因为 blob 路径由 SHA 决定），清理任一条都会物理删除 blob，导致其他还在使用的 record 引用一个不存在的文件。该问题在当前没有定时清理调用方时还未暴露，但即将上线"删除 session 后 24h 清理 orphaned record"会立刻触发。

同时，`/api/v1/attachments/{id}/thumbnail` 端点目前直接返回原图（注释 `P0: return the original image as-is`），没有真正的缩略图生成。聊天列表里渲染 256×256 的预览却下载完整原图，对移动端流量和列表加载速度都是浪费。

本次任务一次性解决以上三个相互关联的问题。

## 2. 范围

### P0 范围

- `upload_bytes` 在 blob 已存在时跳过写入。
- `cleanup` 改为引用计数：blob / thumbnail 仅在没有任何 active record 指向其 SHA 时才物理删除。
- 上传图片时同步生成缩略图，缩略图也按 SHA 内容寻址。
- `/thumbnail` 端点优先返回缩略图文件；不存在时 fallback 返回原图（兼容老数据与生成失败场景）。

### 不做

- 不做异步/后台延迟生成缩略图。
- 不做 thumbnail 多档尺寸（只生成 256×256 一档）。
- 不写 migration script 给历史 record 补生成缩略图（依赖 fallback 路径自然兼容）。
- 不动 `mark_session_orphaned` / session 删除路径——清理逻辑只在 `cleanup` 一处处理。
- 不引入并发锁应对 TOCTOU 同内容并发上传（`os.replace` 原子性已保证最终一致，重复 tmp 写入是可接受成本）。

## 3. 总体设计

### 3.1 Blob 去重写入

`AttachmentStore.upload_bytes` 修改片段：

```python
sha = hashlib.sha256(data).hexdigest()
blob_rel = f"blobs/{sha[:2]}/{sha}"
blob_abs = self._root_dir / blob_rel

if not blob_abs.exists():
    blob_abs.parent.mkdir(parents=True, exist_ok=True)
    (self._root_dir / "tmp").mkdir(parents=True, exist_ok=True)
    tmp_path = self._root_dir / "tmp" / str(uuid4())
    try:
        tmp_path.write_bytes(data)
        os.replace(tmp_path, blob_abs)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise
```

DB 层保持每次新建 `AttachmentRecord`（新 UUID），`mark_agent_sent` 状态机不受影响。

### 3.2 引用计数清理

`AttachmentStore.cleanup` 重写关键循环。**核心**：必须先把本批要删除的 record id 收集成集合，再做引用计数查询时排除该集合，避免"两条都过期、彼此看到对方还在 → 都不删 blob → blob 永久孤儿"。

```python
records = list(...)  # 已经查出的待删 record 列表
batch_ids = {r.id for r in records}
shas_in_batch = {r.sha256 for r in records}

# 一次性查出本批 SHA 在批外是否还有 record
remaining = await session.execute(
    select(AttachmentRecord.sha256, func.count())
    .where(
        AttachmentRecord.sha256.in_(shas_in_batch),
        AttachmentRecord.id.notin_(batch_ids),
    )
    .group_by(AttachmentRecord.sha256)
)
remaining_count = {sha: cnt for sha, cnt in remaining.all()}

for r in records:
    if remaining_count.get(r.sha256, 0) == 0:
        blob = self.blob_absolute_path(r)
        blob.unlink(missing_ok=True)
        thumb = self._thumb_absolute_path(r)
        thumb.unlink(missing_ok=True)
    await session.delete(r)
    count += 1
await session.commit()
```

设计要点：

- **按 sha256 查询**：schema 已有 `ix_attachments_sha256` 索引，比按 `blob_path` 查更高效。
- **不限 status**：blob 在用与否的判定是"是否存在任何 record 指向同 SHA"，不区分 uploaded / attached / orphaned。
- **批内 SHA 一次性聚合**：避免每条 record 一次查询，I/O 友好。
- **thumb 与 blob 共用同一 SHA 引用计数**：缩略图和 blob 都按 SHA 内容寻址，存在性同生共死。

### 3.3 缩略图生成

**新增依赖**：`pyproject.toml` 加入 `Pillow`。

**生成位置**：`AttachmentStore.upload_bytes`，在 blob 写入逻辑之后、DB 入库之前。仅对 `kind == "image"` 生成。

**生成参数**：

| 项 | 值 |
|---|---|
| 最大边长 | 256 px（等比缩放，使用 `Image.thumbnail((256, 256))`） |
| 输出格式 | 与原图一致；GIF 取第一帧后用 PNG |
| JPEG quality | 85 |
| 优化 | `optimize=True` |
| 路径 | `thumbs/<sha[:2]>/<sha>.<ext>`（与 blob 同样按 SHA 内容寻址） |
| 写入策略 | 与 blob 一致：先写 tmp，`os.replace` 落位；目标已存在则跳过 |

**扩展名映射**：

```python
_THUMB_EXT_BY_FORMAT = {
    "JPEG": "jpg",
    "PNG": "png",
    "WEBP": "webp",
}
```

GIF 原图被解码后转 PNG 第一帧，扩展名为 `png`。

**Pillow 解码失败的降级**：捕获 `Image.UnidentifiedImageError` / `OSError` / `ValueError`，**不让 upload 失败**——记 warning 日志，跳过缩略图生成，DB 记录正常入库。这意味着 `AttachmentRecord` 不再保证有对应的 thumb 文件；下游逻辑（`/thumbnail` 端点）必须能处理缺失。

**新增字段（可选）**：考虑在 `AttachmentRecord` 加 `thumb_path: str | None`，用于明确"是否生成了缩略图"。但这会引入 schema migration。**P0 暂不加**，端点直接按规则推算路径并 `exists()` 判断。

### 3.4 端点行为

`/api/v1/attachments/{id}/thumbnail` 改为：

1. 取 record，校验 `kind == "image"`。
2. 按 `record.sha256` 推算 thumb 文件路径，逐个尝试 `jpg / png / webp` 三种扩展名（生成时只可能选其中一种）。
3. 命中文件 → 直接返回缩略图，`media_type` 用对应的 MIME。
4. 未命中（老数据 / 生成失败 / blob 已被 cleanup 删除）→ fallback 读取原 blob，与原图同样的 `record.mime_type` 返回。
5. 原 blob 也不存在 → 404。

## 4. 错误处理与降级

| 场景 | 行为 |
|---|---|
| Pillow 解码失败 | upload 成功，跳过 thumb，warning 日志 |
| 同 SHA 并发上传（TOCTOU） | 两次都写 tmp，`os.replace` 互相覆盖；最终一致，无锁 |
| cleanup 中 blob/thumb 文件不存在 | `unlink(missing_ok=True)`，吞掉 |
| 老 record 没有 thumb 文件 | 端点 fallback 返回原图 |
| 端点 thumb 与 blob 都不存在 | 404 |

## 5. 数据迁移

无需 migration。

- 现有 record 的 `blob_path` 不变。
- 现有 record 没有 thumb 文件——端点 fallback 自动返回原图，行为与改动前一致。
- 新上传的 image record 会同步生成 thumb 文件，下次请求开始走缩略图路径。

## 6. 测试策略

### 单元测试（新增 / 扩展 `tests/unit/store/test_attachments.py`）

**Blob 去重写入**：
- 第二次上传同内容：`blob_abs` 文件 `mtime` 不变（mock `os.replace` 验证未被调用）。
- 第二次上传同内容：tmp 目录在调用结束后无新增临时文件。

**引用计数清理**：
- 两条 record 同 SHA、都在过期清理批次内：清理后两条 record 都被删，**blob 也被删**（最后一条引用消失）。
- 两条 record 同 SHA，一条过期一条活跃：清理只删过期 record，**blob 保留**。
- 三条 record 同 SHA，两条过期一条活跃：清理删两条 record，blob 保留。
- 多种 SHA 混合批次：批内每个 SHA 独立判定。

**缩略图生成**：
- 上传 JPEG：`thumbs/<sha[:2]>/<sha>.jpg` 存在，文件大小 < 原图。
- 上传 PNG（带透明度）：thumb 是 PNG，透明度保留（用 Pillow 检查 alpha 通道）。
- 上传 WebP：thumb 是 WebP。
- 上传 GIF：thumb 是 PNG（第一帧）。
- 上传同内容图片两次：thumb 文件路径相同，`mtime` 不变。
- 上传无效图片字节（绕过校验场景）：upload 成功，thumb 文件不存在，warning 日志被记录。

**端点 fallback**：
- thumb 文件存在 → 返回 thumb，MIME 对应正确。
- thumb 文件不存在但 blob 存在 → fallback 返回原图，MIME 是原图 MIME。
- thumb 与 blob 都不存在 → 404。

### 集成测试（扩展 `tests/integration/test_gateway_attachments.py`）

- `send_file` 同一文件两次：返回不同 `attachment_id`，但磁盘 blob 不重复。
- 上传图片后调用 `/thumbnail` 端点：返回缩略图，`Content-Type` 是缩略图格式（不是原图格式时验证差异）。

## 7. 文件改动清单

| 文件 | 改动 |
|---|---|
| `pyproject.toml` | 加 `Pillow` 依赖 |
| `sebastian/store/attachments.py` | `upload_bytes` 加 blob 去重写入；新增缩略图生成；`cleanup` 改引用计数 |
| `sebastian/gateway/routes/attachments.py` | `/thumbnail` 端点改为优先返回缩略图、fallback 原图 |
| `tests/unit/store/test_attachments.py`（如已存在）或新建 | 单元测试 |
| `tests/integration/test_gateway_attachments.py` | 集成测试补充 |
| `sebastian/store/README.md` | 同步说明 blob/thumb 内容寻址、ref counting cleanup 行为 |

## 8. 不变量

- `AttachmentRecord.id` 在每次 `upload_bytes` 都是新 UUID，跨次发送不复用。
- `AttachmentRecord.sha256` 与 `blob_path` 一一对应（`blob_path == f"blobs/{sha[:2]}/{sha}"`）。
- 任何活跃 `AttachmentRecord`（不在 cleanup 待删集合里）都能通过 `blob_path` 找到磁盘文件。
- `kind == "image"` 的 record 的缩略图**不是**不变量——可能因解码失败而缺失，端点必须处理。
