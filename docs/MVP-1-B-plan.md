# MVP 1 B：后端与数据实施计划

## 目标

交付 Markdown/TXT 摄取闭环的后端入口与权威持久化层：安全接收 Raw Source，创建可恢复的 Ingest Job，为 C 提供稳定的任务读取接口，并将 C 验证后的 Wiki operations 在一个短事务中提交。

本计划以 `docs/api-contract.md`、`docs/data-model.md`、`docs/workflows.md` 和 `docs/wiki-schema.md` 为权威输入。

## 非目标

- Parser、Prompt、Ingest Schema 内容生成和引用语义验证由 C 负责；
- 文件树、上传交互、Job 进度和 Wiki 页面 UI 由 D 负责；
- PDF、批量上传、登录、多用户隔离和向量检索不进入 MVP 1；
- B 不允许模型或 Worker 直接写数据库表，统一通过事务服务提交。

## 可复用的 MVP 0 基础

- FastAPI、统一错误格式和 Request ID；
- PostgreSQL、SQLAlchemy、Alembic；
- 默认用户、Workspace 和 Membership；
- Model Profile ORM、脱敏读取和默认 Workspace Profile；
- 不可变、原子、SHA-256 寻址的 Local Storage；
- Redis/RQ Worker、Mock/Ollama/OpenAI-compatible Adapter；
- 后端单元/集成测试和 Compose CI。

## 交付批次

### B1：数据模型和迁移

新增 Alembic `003`，创建：

- `sources`；
- `jobs`；
- `audit_logs`；
- `wiki_pages`；
- `wiki_revisions`；
- `page_aliases`；
- `wiki_links`；
- `citations`。

必须在数据库层落实：

- Source：`UNIQUE(workspace_id, sha256)`；
- Wiki Page：`UNIQUE(workspace_id, slug)`；
- Source Summary：`UNIQUE(workspace_id, primary_source_id)`；
- Revision：`UNIQUE(page_id, revision_no)`；
- Alias：`UNIQUE(workspace_id, alias_normalized)`；
- Job 状态、类型、attempt/max_attempts 和 progress 范围约束；
- 所有 Source、Page、Link、Citation 的 Workspace 归属校验；
- 循环外键使用命名约束和 `use_alter`，保证 downgrade 可执行。

Job 活跃幂等索引覆盖 `queued/running/retrying/completed`，相同幂等键不重复创建任务。

### B2：上传与 Source API

实现：

```http
POST   /api/workspaces/{workspace_id}/sources
GET    /api/workspaces/{workspace_id}/sources/{source_id}
GET    /api/workspaces/{workspace_id}/sources/{source_id}/content
DELETE /api/workspaces/{workspace_id}/sources/{source_id}
```

上传规则：

- multipart 字段固定为 `file`；
- 只接受 `.md`、`.txt`；
- 默认上限 10 MiB，在流式读取过程中强制限制；
- 严格 UTF-8，不自动替换非法字节；
- MIME 仅允许 `text/markdown`、`text/plain` 和安全的缺省文本类型；
- 原始文件名只作为元数据，Storage Key 不使用用户文件名；
- 写入过程中计算 SHA-256，Raw 字节不可覆盖；
- 相同 Workspace、相同 SHA-256 返回既有 Source/Job，不创建重复记录；
- DELETE 只将 Source 设为 `archived`，不删除 Raw。

推荐重复上传仍返回 `202`，响应增加 `deduplicated: true`，避免把正常幂等重试表现为错误。

### B3：Job 创建、状态和恢复

实现：

```http
GET  /api/workspaces/{workspace_id}/jobs
GET  /api/workspaces/{workspace_id}/jobs/{job_id}
POST /api/workspaces/{workspace_id}/jobs/{job_id}/retry
POST /api/workspaces/{workspace_id}/jobs/{job_id}/cancel
GET  /api/workspaces/{workspace_id}/jobs/{job_id}/events
```

上传事务一次创建 Source、queued Job 和 AuditLog。事务提交后只向 RQ 传递 `job_id`，不传文件内容、API Key 或数据库对象。

若 RQ enqueue 失败：

- API 不删除已提交 Job；
- Job 保持 `queued`；
- 恢复扫描器重新入队没有 `rq_job_id` 或 RQ 记录缺失的 queued Job；
- `rq_job_id` 使用确定性值，避免恢复扫描重复入队。

Job 状态转换集中在服务层，C 通过该服务更新 running、progress、retrying、completed、failed，不直接拼写任意状态。

### B4：Model Profile 写接口与凭据

实现 Workspace Profile 的 POST/PATCH/DELETE/test/model-policy：

```http
POST  /api/workspaces/{workspace_id}/model-profiles
PATCH /api/workspaces/{workspace_id}/model-profiles/{profile_id}
DELETE /api/workspaces/{workspace_id}/model-profiles/{profile_id}
POST  /api/workspaces/{workspace_id}/model-profiles/{profile_id}/test
PUT   /api/workspaces/{workspace_id}/model-policy
```

边界：

- B 校验、加密、保存 Profile，并提供脱密后的运行时配置；
- C 执行 Provider 连接测试并返回规范化结果；
- D 只提交 write-only `api_key`，任何 GET/SSE/日志/AuditLog 均不得回显。

凭据实现使用带认证加密，不接受 Base64、明文或 no-op：

- AES-256-GCM；
- 主密钥从环境/Secret 注入，不进入数据库；
- ciphertext 包含随机 nonce 和认证标签；
- AAD 绑定 Profile ID 与 key version；
- 支持 key version，为后续轮换保留入口；
- 缺少有效主密钥时拒绝保存真实 API Key。

Base URL 在持久化前拒绝 userinfo、fragment 和敏感 query 参数；连接测试前由 C 再执行 DNS、重定向和 SSRF 校验。

### B5：Wiki 原子提交服务

提供内部 Python 服务，不在 MVP 1 暴露任意“直接执行 JSON”公网接口。输入必须是 C 已通过 Schema 和引用验证的 typed operations。

单事务顺序：

1. 锁定涉及的 Wiki Page；
2. 校验 Workspace、Source、Profile、Job 和 expected revision；
3. 检查 title/slug/alias 重复候选与冲突；
4. 创建新 Revision，旧 Revision 永不覆盖；
5. 更新 Page 的 current revision；
6. 重建该 Revision 的 Alias、Link 和 Citation；
7. 创建追加式 AuditLog；
8. 将 Job 标记 completed。

任一步失败全部回滚。`REVISION_CONFLICT`、`ALIAS_CONFLICT` 和跨 Workspace 引用必须是稳定、可测试的失败结果。

### B6：Wiki 读取投影

为 D 提供 MVP 1 所需的最小读取接口：

```http
GET /api/workspaces/{workspace_id}/tree
GET /api/workspaces/{workspace_id}/wiki
GET /api/workspaces/{workspace_id}/wiki/{page_id}
GET /api/workspaces/{workspace_id}/wiki-system/index
GET /api/workspaces/{workspace_id}/wiki-system/activity
GET /api/workspaces/{workspace_id}/graph
```

Index、Activity 和 Graph 从 PostgreSQL 确定性投影，不创建第二份权威文件。Overview 留到 MVP 2。

## 跨角色接口

### A 需要确认

- 上传 multipart 字段和重复上传响应；
- Source/Job/Wiki OpenAPI schema；
- Job 状态机、SSE event 名称和 Gate fixture；
- Ingest operation 的版本号及兼容策略；
- MVP 1 是否把 Profile 写接口与上传闭环放在同一 Gate。

### 提供给 C

- Worker 入口只接收 `job_id`；
- Job/Source/Profile 的 scoped repository；
- Profile 凭据只在调用边界短暂解密；
- 状态更新服务和取消检查点；
- `apply_wiki_operations(...)` 原子事务入口；
- 稳定错误码，不暴露数据库异常。

### 提供给 D

- 上传 `202` 响应；
- Source、Job、Wiki、Graph 的 OpenAPI schema；
- Job GET 和 SSE；
- Profile write-only 凭据语义；
- 可复用的确定性 Aurora fixture。

## 测试计划

### 单元测试

- 文件名规范化、扩展名、MIME、UTF-8 和大小限制；
- SHA-256、相同内容幂等和不可变 Storage；
- alias/title/slug 规范化与冲突；
- Job 状态转换；
- 凭据 AES-GCM round trip、篡改失败和错误 key version；
- 所有公开 schema 不含 ciphertext、API Key 和完整 Base URL 凭据。

### PostgreSQL/Redis 集成测试

- 空库 upgrade、downgrade/upgrade 和 seed 幂等；
- 同一 Source 并发上传只创建一条 Source/Job；
- enqueue 失败后 Job 可恢复；
- Wiki operations 全成功或全部回滚；
- revision、alias 和 citation 冲突；
- 跨 Workspace 引用拒绝；
- Profile revoked/invalid/untested 时禁止创建 Ingest Job；
- API、SSE、日志和 AuditLog 不泄露凭据。

### MVP 1 B Gate

```text
上传 aurora-a.md
→ 202 + Source/Job
→ Raw 下载哈希一致
→ 重复上传返回相同 Source/Job
→ C Mock Worker 提交 Source Summary 与页面
→ Wiki/Index/Activity/Graph 可读取
→ 注入事务失败时无半提交
→ 重启后数据仍存在
```

## 推荐 PR 顺序

1. `B1 schema`：003 迁移、ORM 和约束测试；
2. `B2 upload`：Source/Storage/Job 创建和恢复入队；
3. `B3 profiles`：Profile 写接口、加密和连接测试桥接；
4. `B4 wiki transaction`：Revision/Alias/Link/Citation 原子提交；
5. `B5 read APIs`：Tree/Wiki/Index/Activity/Graph；
6. `B6 integration`：与 C/D fixture、SSE 和完整 Gate 收口。

每个 PR 均应从最新 `main` 创建，包含迁移/测试/契约更新，不在一个超大 PR 中同时交付全部 MVP 1。

## 开工条件

以下默认值若 A 未提出异议，B 按此实施：

- upload multipart 字段为 `file`；
- 重复上传返回 `202 + deduplicated=true`；
- 原始文件严格 UTF-8，大小按原始字节计算；
- RQ payload 仅含 `job_id`；
- Wiki 写入只有内部事务服务；
- Profile 主密钥缺失时允许无凭据 Ollama，不允许保存真实 API Key；
- MVP 1 使用默认用户，但所有记录继续携带 `workspace_id/created_by`。
