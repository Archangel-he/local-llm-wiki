# MVP 1-C：LLM 摄取模块

## 交付范围

MVP 1-C 完成从既有 `ingest` Job 到 B 层原子 Wiki 提交的闭环：

```text
Source
→ RQ ingest_job(job_id)
→ Markdown/TXT Parser
→ Workspace、Profile 与最多 200 个 Wiki 候选
→ Ollama / OpenAI-compatible / 内建 Mock
→ Schema、引用、重复候选与关系证据校验
→ apply_wiki_operations 单事务提交
→ completed
```

本模块不新增 Upload REST API、数据库迁移或前端接入，也不重写 B 层 Wiki
事务服务。Export、Query、Lint、PDF 与长文档分批属于后续工作。

## 公开接口

- `app.worker.jobs.ingest_job(job_id: str) -> None`：RQ 入口，只接受 Job ID；
- `app.ingest.parse_source(...) -> ParsedSource`：UTF-8 文本解析和稳定行定位；
- `app.ingest.build_ingest_context(...) -> IngestContext`：重新加载当前 Workspace、
  Source、Profile 和 Wiki 候选，不从 Job Snapshot 读取凭据；
- `app.ingest.validate_ingest_batch(...) -> WikiOperationBatch`：C 层提交前校验；
- `LLMAdapter.test_connection()`、`generate_structured()`、`stream()`：两种真实
  Provider 的一致协议。

运行时权威模型仍是 `app.schemas.wiki.WikiOperationBatch`。生成的 JSON Schema
位于 `backend/wiki/schema/ingest.schema.json`，单元测试会阻止它与运行时模型漂移。

## Provider 与安全策略

Ollama 使用 `/api/tags` 和 `/api/chat`，支持 JSON Schema `format` 与 NDJSON
流。OpenAI-compatible 使用 `/v1/models` 和 `/v1/chat/completions`，支持严格
`json_schema` 响应格式与 SSE 流。

每个真实网络请求都在发出前重新解析 Endpoint/DNS。请求不跟随重定向，URL
不得包含用户信息、查询凭据或 fragment。默认策略如下：

- `APP_ENV=local`：允许公网 HTTP(S)，并允许 allowlist 中的本机/私网主机；
- 其他环境：只允许 HTTPS；公网地址默认可用，私网地址必须显式加入 allowlist；
- 任一 DNS 结果为未授权私网、loopback、link-local 或其他特殊地址时拒绝请求。

上游错误只映射为稳定分类：认证失败、模型/Endpoint 不存在、限流、超时、
不可用、Endpoint 被阻止和无效响应。异常和 Worker 日志不携带 URL、Header、
响应正文或凭据。

内建 Seed Mock Profile 可由 Adapter Factory 执行，但公开 Profile 创建服务仍只
允许 `ollama` 与 `openai_compatible`。Mock 与真实 Provider 使用同一结构化协议，
Aurora Fixture 会确定性地产生 Source Summary、Project Aurora、Lin、Alias、Link
和 Citation。

## Parser、Prompt 与校验

Parser 接受 UTF-8/UTF-8 BOM，规范 `CRLF`/`CR` 为 `LF`，并按 Markdown 标题与
文本段落产生 `lines:start-end` locator。它只读取 Raw 对象，不修改原始字节。
空文件、非法 UTF-8 和超出 `INGEST_MAX_SOURCE_CHARS` 的输入都会安全失败；
MVP 1 不静默截断。

Prompt 版本固定为 `mvp1-ingest-v1`。提交前校验包括：

- Schema version、Source ID 和操作数量；
- 恰好一个 Source Summary，且链接到本批次所有抽取页；
- create/update、Page ID 和 expected revision 一致性；
- title、slug、alias 与既有最多 200 个候选的重复；
- Citation 仅引用当前 Workspace/Source，locator 存在且 excerpt 可由片段验证；
- Markdown `source:<uuid>#lines:start-end` 标记必须有对应结构化 Citation；
- `related`/`contradicts` 等推断关系必须引用当前 Source 作为 evidence。

B 层 `apply_wiki_operations` 仍负责锁、最终 revision/alias/source 检查与事务提交。
任何模型、解析或验证失败都发生在提交之前，不会留下部分 Wiki。

## Worker 状态、重试与恢复

Worker 依次报告：

```text
parsing → loading_context → calling_model → validating → committing → completed
```

阶段边界会检查取消请求；提交事务开始后不强制中断。Profile 在执行时按 Job 的
Workspace 重新加载并检查 `active`，凭据只在内存中临时解密。

认证失败、模型不存在和 Endpoint 被阻止不可重试。超时、429、5xx、无效模型
输出、Schema/引用失败和事务冲突可以重试，但 B 层 `max_attempts` 将总尝试数限制
为默认 3 次。RQ ID 使用 `ingest-<job-id>-attempt-<n>`，重复恢复不会创建同一
attempt 的不同 ID。

Redis 或 Worker 重启后，以 PostgreSQL 中 `queued/retrying` 且没有 `rq_job_id`
的记录为准恢复：

```bash
docker compose up -d postgres redis api worker
docker compose exec api python -m app.recover_jobs
```

建议在 Compose 服务健康后执行一次该命令；它是幂等扫描，不会传输 Secret 或
Source 内容到 Redis。

## 配置

```dotenv
LLM_CONNECT_TIMEOUT_SECONDS=5
LLM_REQUEST_TIMEOUT_SECONDS=120
MODEL_ENDPOINT_ALLOWLIST=host.docker.internal,localhost,127.0.0.1,::1
INGEST_MAX_SOURCE_CHARS=120000
INGEST_MAX_EXISTING_PAGES=200
INGEST_PROMPT_VERSION=mvp1-ingest-v1
```

生产环境添加私网模型时，应在 `MODEL_ENDPOINT_ALLOWLIST` 中只列出明确受控的
主机名或 IP，并使用 HTTPS。不要加入整个网段，也不要把 API Key 放入 URL。

## 验收

后端静态检查与测试：

```bash
cd backend
python -m ruff check .
python -m pytest -m "not integration" -q
python -m pytest -q
```

PostgreSQL/Redis/RQ 集成：

```bash
docker compose up -d postgres redis
docker compose run --rm api alembic upgrade head
docker compose run --rm api python -m app.seed
REDIS_TEST_URL=redis://localhost:6379/15 \
DATABASE_URL=postgresql+psycopg://wiki:wiki@localhost:5432/wiki \
python -m pytest tests/integration/test_mvp1_c.py -q
```

前端回归：

```bash
cd frontend
pnpm test
pnpm run build
```

真实模型 Smoke Test 是显式可选项。只有在操作者提供受控 Endpoint、模型名和
凭据后才运行；默认验收不主动访问外部模型。
