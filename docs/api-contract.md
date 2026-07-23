# API 与事件契约

## 通用约定

- Base path：`/api`；
- FastAPI 文档位于 `/api/docs`，OpenAPI JSON 位于 `/api/openapi.json`；
- JSON 使用 `snake_case`；
- ID 使用 UUID 字符串；
- 时间使用 UTC ISO 8601；
- 列表接口使用 cursor pagination；
- 所有 Workspace 资源先授权再查询；
- 无权访问他人资源时优先返回 404，减少资源枚举；
- OpenAPI 是实现期的接口事实来源，本文描述稳定约定。

## 认证

MVP 0～2 自动使用 default user。MVP 3 启用：

```http
POST /api/auth/register
POST /api/auth/login
POST /api/auth/logout
GET  /api/auth/me
```

- Session ID 仅通过 `HttpOnly + Secure + SameSite` Cookie 传递；
- 不将 Session/JWT 放入 `localStorage`；
- 密码使用 Argon2id；
- 改变密码或权限后轮换 Session；
- 写操作使用 SameSite 与 CSRF 防护组合。

## 错误格式

```json
{
  "error": {
    "code": "REVISION_CONFLICT",
    "message": "The page changed since it was opened.",
    "request_id": "req_...",
    "details": {
      "expected_revision": 3,
      "current_revision": 4
    }
  }
}
```

稳定错误码：

```text
VALIDATION_ERROR
UNAUTHENTICATED
FORBIDDEN
NOT_FOUND
DUPLICATE_SOURCE
UNSUPPORTED_FILE_TYPE
FILE_TOO_LARGE
JOB_ALREADY_EXISTS
JOB_NOT_CANCELLABLE
REVISION_CONFLICT
LLM_UNAVAILABLE
SCHEMA_VALIDATION_FAILED
ALIAS_CONFLICT
SCHEMA_VERSION_CONFLICT
RATE_LIMITED
INTERNAL_ERROR
```

## Health

```http
GET /api/health
```

```json
{
  "status": "degraded",
  "components": {
    "api": "ok",
    "postgres": "ok",
    "redis": "ok",
    "worker": "ok",
    "storage": "ok",
    "llm": "unavailable"
  }
}
```

LLM 不可用时返回 200 + degraded，应用仍可浏览已有 Wiki。

## Workspace

```http
GET    /api/workspaces
POST   /api/workspaces
GET    /api/workspaces/{workspace_id}
PATCH  /api/workspaces/{workspace_id}
DELETE /api/workspaces/{workspace_id}
```

DELETE 在 MVP 阶段执行归档，不物理删除。

## 文件树与来源

```http
GET  /api/workspaces/{workspace_id}/tree
POST /api/workspaces/{workspace_id}/sources
POST /api/workspaces/{workspace_id}/source-batches
GET  /api/workspaces/{workspace_id}/source-batches/{batch_id}
GET  /api/workspaces/{workspace_id}/sources/{source_id}
GET  /api/workspaces/{workspace_id}/sources/{source_id}/content
DELETE /api/workspaces/{workspace_id}/sources/{source_id}
```

上传成功：

```http
HTTP/1.1 202 Accepted
```

```json
{
  "source": {
    "id": "SOURCE_ID",
    "filename": "aurora.md",
    "sha256": "...",
    "status": "active"
  },
  "job": {
    "id": "JOB_ID",
    "status": "queued"
  }
}
```

MVP 1：UTF-8 `.md`、`.txt`，默认上限 10 MiB。

MVP 2：文本型 PDF，默认上限 50 MiB；扫描 PDF/OCR 不在早期范围。

`source-batches` 在 MVP 2 启用。Batch 只聚合多个独立 Source/Job，响应包含 total/queued/skipped/completed/failed/cancelled；单个文件失败不回滚其他文件。

## Job

```http
GET  /api/workspaces/{workspace_id}/jobs
GET  /api/workspaces/{workspace_id}/jobs/{job_id}
POST /api/workspaces/{workspace_id}/jobs/{job_id}/retry
POST /api/workspaces/{workspace_id}/jobs/{job_id}/cancel
GET  /api/workspaces/{workspace_id}/jobs/{job_id}/events
```

取消 queued 任务可直接进入 `cancelled`；取消 running 任务先进入 `cancel_requested`，由 Worker 在安全检查点停止。事务提交阶段不强制终止。

状态响应：

```json
{
  "id": "JOB_ID",
  "type": "ingest",
  "status": "running",
  "attempt": 1,
  "max_attempts": 3,
  "progress": {
    "stage": "generating_wiki",
    "current": 2,
    "total": 5
  },
  "error": null
}
```

### Job SSE

`GET .../events` 返回 `text/event-stream`：

```text
event: progress
data: {"stage":"parsing","current":1,"total":4}

event: progress
data: {"stage":"generating_wiki","current":2,"total":4}

event: completed
data: {"job_id":"JOB_ID","affected_page_ids":["PAGE_ID"]}
```

事件类型：`snapshot / progress / completed / failed / cancelled / heartbeat`。

客户端断线后可以使用普通 GET 获取最终状态，不依赖 SSE 补发全部历史。

## Wiki

```http
GET   /api/workspaces/{workspace_id}/wiki
GET   /api/workspaces/{workspace_id}/wiki/{page_id}
GET   /api/workspaces/{workspace_id}/wiki-system/index
GET   /api/workspaces/{workspace_id}/wiki-system/overview
GET   /api/workspaces/{workspace_id}/wiki-system/activity
PATCH /api/workspaces/{workspace_id}/wiki/{page_id}
GET   /api/workspaces/{workspace_id}/wiki/{page_id}/revisions
GET   /api/workspaces/{workspace_id}/wiki/{page_id}/revisions/{revision_no}
POST  /api/workspaces/{workspace_id}/wiki/{page_id}/restore
```

更新必须携带：

```json
{
  "expected_revision_no": 3,
  "markdown": "# Updated page\n...",
  "change_summary": "Correct launch date"
}
```

版本不匹配返回 409。

Wiki 响应包含 `aliases` 和 `summary`。Index/Activity 是只读投影；Overview 是版本化 Wiki 内容。

Index/Activity 从 MVP 1 提供，Overview 从 MVP 2 提供。

## Graph

```http
GET /api/workspaces/{workspace_id}/graph
GET /api/workspaces/{workspace_id}/graph?scope=local&center={page_id}&depth=1
GET /api/workspaces/{workspace_id}/graph?types=wikilink,citation
```

```json
{
  "nodes": [
    {
      "id": "PAGE_ID",
      "label": "Project Aurora",
      "slug": "project-aurora",
      "type": "topic",
      "status": "needs_review",
      "degree": 3,
      "updated_at": "2026-07-23T08:00:00Z"
    }
  ],
  "edges": [
    {
      "id": "LINK_ID",
      "source": "PAGE_ID",
      "target": "OTHER_PAGE_ID",
      "type": "wikilink",
      "weight": 1,
      "has_evidence": true
    }
  ],
  "meta": {
    "scope": "local",
    "depth": 1,
    "truncated": false
  }
}
```

全局图超过服务端配置阈值时返回采样或要求筛选，并将 `truncated` 设为 true。

## Query

```http
POST /api/workspaces/{workspace_id}/queries
GET  /api/workspaces/{workspace_id}/queries/{query_id}
GET  /api/workspaces/{workspace_id}/queries/{query_id}/events
POST /api/workspaces/{workspace_id}/queries/{query_id}/save-to-wiki
```

请求：

```json
{
  "question": "Aurora 什么时候启动？",
  "scope": "local_graph",
  "center_page_id": "PAGE_ID",
  "depth": 1
}
```

创建成功返回：

```http
HTTP/1.1 202 Accepted
```

```json
{
  "query_id": "QUERY_ID",
  "job_id": "JOB_ID",
  "status": "queued",
  "events_url": "/api/workspaces/WORKSPACE_ID/queries/QUERY_ID/events"
}
```

Query 由 RQ Worker 执行。Worker 将实时事件发布到 Redis，FastAPI 转发为 SSE；最终回答、引用和状态保存到 PostgreSQL，因此断线后可通过普通 GET 恢复。

Query SSE：

```text
event: meta
data: {"query_id":"QUERY_ID","candidate_page_ids":["PAGE_ID"]}

event: token
data: {"text":"Project Aurora"}

event: citation
data: {"citation_id":"CITATION_ID","page_id":"PAGE_ID","source_id":"SOURCE_ID"}

event: done
data: {"answer_id":"ANSWER_ID","grounded":true}
```

事件类型：`meta / token / citation / warning / done / error / heartbeat`。

引用必须在 `done` 前完成后端验证。证据不足时 `grounded=false`，回答必须拒绝给出具体事实。

## Lint

```http
POST /api/workspaces/{workspace_id}/lint-jobs
GET  /api/workspaces/{workspace_id}/lint-issues
GET  /api/workspaces/{workspace_id}/lint-issues/{issue_id}
POST /api/workspaces/{workspace_id}/lint-issues/{issue_id}/resolve
POST /api/workspaces/{workspace_id}/lint-issues/{issue_id}/ignore
```

Lint Issue 包含：类型、严重度、页面、证据、建议动作、状态和创建时间。Lint 不自动修改 Wiki。

## Schema

```http
GET  /api/workspaces/{workspace_id}/schema
GET  /api/workspaces/{workspace_id}/schema/versions
GET  /api/workspaces/{workspace_id}/schema/suggestions
GET  /api/workspaces/{workspace_id}/schema/suggestions/{suggestion_id}
POST /api/workspaces/{workspace_id}/schema/suggestions/{suggestion_id}/accept
POST /api/workspaces/{workspace_id}/schema/suggestions/{suggestion_id}/reject
```

接受 Suggestion 必须携带当前 `schema_version`；版本不匹配返回 409。接受操作创建新版本并写审计日志，不在原版本上覆盖。

Schema Suggestion 在 MVP 2 启用；MVP 3～4 启用身份后，创建建议需要 Editor，激活新版本需要 Owner 或项目最终确定的等价权限。

## 成员与邀请

MVP 4：

```http
GET    /api/workspaces/{workspace_id}/members
POST   /api/workspaces/{workspace_id}/invitations
POST   /api/invitations/{token}/accept
PATCH  /api/workspaces/{workspace_id}/members/{user_id}
DELETE /api/workspaces/{workspace_id}/members/{user_id}
```

所有接口按 Owner / Editor / Viewer 权限矩阵测试。

## Export

```http
POST /api/workspaces/{workspace_id}/exports
GET  /api/workspaces/{workspace_id}/exports/{export_id}
GET  /api/workspaces/{workspace_id}/exports/{export_id}/download
```

下载必须鉴权；OSS 模式使用短时签名 URL，不公开 Bucket。

## 版本策略

MVP 阶段 API 不加 URL 版本号；破坏性变更必须同步更新 OpenAPI、Mock、前端和契约测试。首次公开 Beta 前冻结 `/api/v1`。

## 官方参考

- [OWASP Password Storage](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)
- [OWASP Session Management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)
- [PostgreSQL Full Text Search](https://www.postgresql.org/docs/current/textsearch-controls.html)
- [PostgreSQL pg_trgm](https://www.postgresql.org/docs/current/pgtrgm.html)
- [RQ Jobs and Queues](https://python-rq.org/docs/)
