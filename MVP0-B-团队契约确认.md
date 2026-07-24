# MVP 0：B 角色后端与数据契约确认书

状态：`待 A / B / C / D 共同确认`  
日期：2026-07-24  
适用范围：`local-llm-wiki` MVP 0  
主责：B（后端与数据）

> 本文用于在编码前冻结 MVP 0 的后端技术栈、数据模型、API、初始化、Storage、安全边界和跨角色接口。未确认项不得被视为最终决定；确认后，影响其他角色的修改必须通过 ADR 或契约变更 PR。

## 1. 确认目标

MVP 0 完成后，系统应当能够：

1. 从空仓库通过 Docker Compose 启动；
2. 连接 PostgreSQL，并通过 Alembic 完成迁移；
3. 幂等创建默认用户、默认 Workspace 和默认 Model Profile；
4. 提供稳定的 Health、Workspace 和 Model Profile 读取接口；
5. 通过统一 Storage 接口完成本地不可变文件写入测试；
6. 在模型不可用时保持 API 可启动，并将整体状态显示为 `degraded`；
7. 重启容器后保留数据库和 Storage 数据；
8. 为 C 的 Worker/LLM Adapter 和 D 的前端 Mock 提供稳定契约。

MVP 0 不交付真实资料摄取、Wiki 生成、PDF、问答、引用、登录注册、RBAC、OSS 或生产级模型路由。

## 2. 建议冻结的技术选择

下表为 B 角色建议值。团队确认后，由 A 在镜像、CI 和锁文件中固定具体补丁版本。

| 项目 | 建议 | 确认 |
| --- | --- | --- |
| Python | 3.12 | [ ] |
| Web 框架 | FastAPI | [ ] |
| 数据校验 | Pydantic 2 + pydantic-settings | [ ] |
| ORM | SQLAlchemy 2.x，async API | [ ] |
| PostgreSQL 驱动 | psycopg 3 | [ ] |
| 数据库迁移 | Alembic | [ ] |
| 后端包管理 | `uv` + `pyproject.toml` | [ ] |
| 测试 | pytest + pytest-asyncio + HTTPX | [ ] |
| PostgreSQL | 17，具体镜像版本由 A 固定 | [ ] |
| UUID | 应用侧 UUID4 | [ ] |
| 时间 | PostgreSQL `timestamptz`，统一 UTC | [ ] |
| JSON 扩展字段 | PostgreSQL JSONB | [ ] |
| API 命名 | JSON `snake_case` | [ ] |

约定：不使用 `create_all()` 管理正式数据库结构，所有结构变化必须进入 Alembic。

## 3. 仓库目录契约

```text
backend/
├── app/
│   ├── api/
│   │   ├── health.py
│   │   ├── workspaces.py
│   │   └── model_profiles.py
│   ├── core/
│   │   ├── config.py
│   │   ├── errors.py
│   │   └── lifespan.py
│   ├── db/
│   │   ├── base.py
│   │   ├── session.py
│   │   └── bootstrap.py
│   ├── models/
│   ├── repositories/
│   ├── schemas/
│   ├── services/
│   ├── storage/
│   ├── workers/
│   └── main.py
├── migrations/
├── tests/
│   ├── unit/
│   └── integration/
└── pyproject.toml
```

确认：A/C 共用 `backend/app` 包，不另建一套重复的 Worker 数据模型。

## 4. 服务和责任边界

| 组件 | 主责 | MVP 0 责任 |
| --- | --- | --- |
| Caddy、Compose、CI、Makefile | A | 容器、网络、持久卷、启动和总 Gate |
| FastAPI、PostgreSQL、Alembic | B | API、ORM、迁移、初始化和数据约束 |
| Model Profile 数据和脱敏 | B | 表、Repository、公开响应、Secret 接口 |
| Local Storage | B | 接口、本地实现、不可覆盖和路径安全 |
| Redis、RQ Worker | C | 队列和 Worker 冒烟任务 |
| LLM Provider Adapter | C | Mock/OpenAI-compatible、模型 Health |
| Vite、工作区、模型设置 Mock | D | UI、Mock 数据和 E2E |

跨边界原则：

- C 通过 B 提供的 Repository/Service 读取 Model Profile，不复制 ORM；
- D 以 OpenAPI 和本文示例为契约，不依赖数据库字段；
- A 不在容器入口中使用 `create_all()` 或自行生成默认数据；
- B 不实现 Redis/RQ 和真实模型 HTTP 调用。

## 5. MVP 0 数据模型

### 5.1 `users`

| 字段 | 类型/规则 |
| --- | --- |
| `id` | UUID，主键 |
| `email` | 规范化字符串，全局唯一 |
| `password_hash` | nullable；MVP 3 前不使用 |
| `display_name` | 非空 |
| `status` | `active / disabled` |
| `created_at` | UTC timestamptz |
| `updated_at` | UTC timestamptz |

### 5.2 `workspaces`

| 字段 | 类型/规则 |
| --- | --- |
| `id` | UUID，主键 |
| `owner_id` | FK → users.id |
| `name` | 非空 |
| `slug` | 非空；与 owner 组成唯一约束 |
| `status` | `active / archived` |
| `schema_version` | 正整数，默认 1 |
| `default_model_profile_id` | nullable；Profile 创建后设置 |
| `created_at` | UTC timestamptz |
| `updated_at` | UTC timestamptz |

约束：`(owner_id, slug)` 唯一。默认 Profile 必须是同一 Workspace 下 `scope=workspace` 且 `status=active` 的 Profile。MVP 0 至少由 Service 层验证，并为后续数据库级复合外键预留结构。

### 5.3 `model_profiles`

| 字段 | 类型/规则 |
| --- | --- |
| `id` | UUID，主键 |
| `scope` | `personal / workspace` |
| `owner_user_id` | personal Profile 使用，nullable |
| `workspace_id` | workspace Profile 使用，nullable |
| `profile_key` | 稳定机器标识，不随显示名称修改 |
| `provider` | `mock / ollama / openai_compatible` |
| `display_name` | 用户可见名称 |
| `base_url` | nullable；保存规范化地址 |
| `model_name` | Model ID，nullable |
| `credential_ciphertext` | nullable，禁止公开序列化 |
| `credential_key_version` | nullable |
| `capabilities_json` | JSONB，默认空对象 |
| `status` | `untested / active / invalid / revoked` |
| `last_tested_at` | nullable UTC timestamptz |
| `created_by` | FK → users.id |
| `created_at` | UTC timestamptz |
| `updated_at` | UTC timestamptz |

必须添加 Check Constraint：

```text
scope=personal  → owner_user_id 非空，workspace_id 为空
scope=workspace → workspace_id 非空
```

唯一约束建议：

```text
(workspace_id, profile_key) WHERE scope=workspace
(owner_user_id, profile_key) WHERE scope=personal
```

待团队确认的数据模型变更：在现有设计中加入 `profile_key`，用于幂等初始化、日志和配置引用。`display_name` 允许用户修改，不能承担稳定标识职责。

## 6. 默认数据和模型 Profile 决策

### 6.1 必有默认数据

```text
User
  email: default-user@local.invalid

Workspace
  slug: default
  name: Default Workspace

Model Profile
  profile_key: mock-default
  provider: mock
  status: active
```

### 6.2 推荐决策

- CI 和无模型开发机始终使用 `mock-default`，保证启动和测试确定性；
- 不再将 Ollama 作为唯一默认 Profile；
- 如果环境变量提供 Mac Qwen 配置，则额外幂等创建 `mac-qwen36`；
- 如果环境变量提供 Spark 配置，则额外幂等创建 `spark-qwen36`；
- 真实 Profile 初始状态为 `untested`，不可达不阻止系统启动；
- 是否把 `mac-qwen36` 设为 Workspace 默认值由配置决定；未配置时使用 Mock；
- MVP 0 不做 Mac/Spark 自动回退和负载均衡。

建议环境变量：

```dotenv
DEFAULT_LLM_PROFILE_KEY=mock-default

MAC_QWEN36_ENABLED=false
MAC_QWEN36_BASE_URL=http://host.docker.internal:30000/v1
MAC_QWEN36_MODEL=qwen36-aggressive-q4km

SPARK_QWEN36_ENABLED=false
SPARK_QWEN36_BASE_URL=http://spark-tunnel:30000/v1
SPARK_QWEN36_MODEL=qwen36-aggressive-q4km
```

真实地址是否进入 `.env.example` 由 A 确认；示例不得包含真实 IP、用户名、API Key 或 SSH 信息。

## 7. 初始化契约

初始化命令建议为：

```bash
python -m app.db.bootstrap
```

初始化顺序：

```text
创建/获取 default-user
→ 创建/获取 default-workspace（默认 Profile 暂为空）
→ 创建/获取 mock-default
→ 按环境变量创建可选 Profile
→ 设置 Workspace 默认 Profile
```

必须满足：

- 连续执行 10 次不产生重复记录；
- 两个初始化进程并发执行不产生重复记录；
- 依靠唯一约束和 upsert，而不是“先查询、再盲目插入”；
- 初始化失败时事务整体回滚；
- 不覆盖用户已经修改过的名称、状态或能力数据；
- 模型不可用不导致迁移或初始化失败。

本地启动建议顺序：

```text
等待 PostgreSQL ready
→ alembic upgrade head
→ bootstrap
→ 启动 API/Worker
```

生产环境迁移保持显式步骤，不在每个 API 实例启动时竞争执行。该生产策略在 MVP 5 实现。

## 8. API 契约

Base path：`/api`。

### 8.1 `GET /api/health`

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
  },
  "request_id": "req_example"
}
```

约定：

- `status`：`ok / degraded / unhealthy`；
- 组件状态：`ok / degraded / unavailable`；
- LLM 不可用返回 HTTP 200 + `degraded`；
- PostgreSQL 不可用时不进行任何降级写入；
- B 提供 `api/postgres/storage`，C 提供 `redis/worker/llm`，A 完成集成 Gate。

### 8.2 Workspace

```text
GET /api/workspaces
GET /api/workspaces/{workspace_id}
```

MVP 0 返回默认用户可见的 Workspace。创建、修改、归档可以延后，不阻塞 D。

### 8.3 Model Profile

```text
GET /api/workspaces/{workspace_id}/model-profiles
GET /api/workspaces/{workspace_id}/model-profiles/{profile_id}
```

公开响应示例：

```json
{
  "id": "00000000-0000-0000-0000-000000000000",
  "profile_key": "mac-qwen36",
  "scope": "workspace",
  "provider": "openai_compatible",
  "display_name": "Mac Studio Qwen 3.6",
  "base_url": "http://host.docker.internal:30000/v1",
  "model_name": "qwen36-aggressive-q4km",
  "credential_configured": false,
  "capabilities": {},
  "status": "untested",
  "last_tested_at": null
}
```

MVP 0 建议只实现读取接口。以下写操作先冻结请求/响应 Schema，真实实现放到 MVP 1：

```text
POST  /api/workspaces/{workspace_id}/model-profiles
PATCH /api/workspaces/{workspace_id}/model-profiles/{profile_id}
POST  /api/workspaces/{workspace_id}/model-profiles/{profile_id}/test
```

若团队决定 MVP 0 必须完成真实 Profile 表单联调，需要单独提高 Scope 并明确 B/C 的调用边界。

### 8.4 统一错误格式

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid request.",
    "request_id": "req_example",
    "details": {}
  }
}
```

MVP 0 稳定错误码：

```text
VALIDATION_ERROR
NOT_FOUND
PROFILE_INVALID
STORAGE_UNAVAILABLE
DATABASE_UNAVAILABLE
INTERNAL_ERROR
```

不得在 `message/details` 中返回数据库 DSN、API Key、credential ciphertext、绝对 Storage 路径或服务器堆栈。

## 9. Credential 安全契约

MVP 0 定义接口，但 Gate 不使用真实 API Key：

```python
class CredentialCipher(Protocol):
    def encrypt(self, plaintext: str) -> EncryptedCredential: ...
    def decrypt(self, ciphertext: bytes, key_version: int) -> str: ...
```

约定：

- 禁止 No-op、Base64 或明文实现冒充加密；
- 公开 Pydantic Schema 不包含 ciphertext 和 key version；
- Repository 的普通读取方法默认不加载/返回凭据；
- C 只能通过专用 Service 在实际调用时取得解密值；
- API Key 只允许写入、替换和撤销，不允许读取回显；
- 日志、SSE、错误、审计和测试快照不得包含凭据；
- 真正写入凭据的 API 在加密实现和 Secret 管理确认前保持禁用。

## 10. Local Storage 契约

```python
class Storage(Protocol):
    async def put_immutable(
        self,
        stream,
        storage_key: str,
        expected_sha256: str,
    ) -> StoredObject: ...

    async def open(self, storage_key: str): ...
    async def exists(self, storage_key: str) -> bool: ...
    async def archive(self, storage_key: str) -> None: ...
```

本地实现必须：

- 将所有路径限制在 `LOCAL_STORAGE_PATH`；
- 拒绝绝对路径、`..` 和路径穿越；
- 使用临时文件流式计算 SHA-256；
- 哈希通过后原子提交；
- 相同 key、相同内容允许幂等返回；
- 相同 key、不同内容拒绝覆盖；
- 失败时不留下正式对象；
- 不使用用户原始文件名作为可信物理路径。

MVP 0 不实现 OSS，但不得在业务层直接调用 `open()`、`Path` 或 OSS SDK 绕过 Storage 接口。

## 11. 配置契约

`.env.example` 至少包含：

```dotenv
APP_ENV=local
DATABASE_URL=postgresql+psycopg://wiki:wiki@postgres:5432/wiki
REDIS_URL=redis://redis:6379/0
LOCAL_STORAGE_PATH=/app/storage
DEFAULT_USER_EMAIL=default-user@local.invalid
DEFAULT_WORKSPACE_SLUG=default
DEFAULT_LLM_PROFILE_KEY=mock-default
MAC_QWEN36_ENABLED=false
MAC_QWEN36_BASE_URL=http://host.docker.internal:30000/v1
MAC_QWEN36_MODEL=qwen36-aggressive-q4km
```

配置启动规则：

- 缺少数据库配置：启动失败并给出安全错误；
- 缺少 Redis：API 可按团队 Health 策略启动，但队列标记不可用；
- 缺少真实模型配置：正常启动并使用 Mock；
- Storage Root 无法创建或不可写：禁止文件写入并在 Health 中报告；
- 任何 Secret 不得提供可提交 Git 的默认值。

## 12. 测试契约

### Unit

- Settings 校验；
- Profile scope/check 规则；
- Profile 公共 Schema 脱敏；
- 统一错误格式；
- Storage key 规范化；
- Storage 哈希和不可覆盖。

### Integration

- 空库 `alembic upgrade head`；
- 迁移重复执行；
- 默认数据幂等初始化；
- 并发初始化；
- Workspace/Profile 外键和唯一约束；
- Profile 不能被跨 Workspace 查询；
- PostgreSQL 不可用时 Health 行为；
- Storage 不可写时 Health 行为；
- 容器重启后数据仍存在。

MVP 0 B 角色不测试登录、RBAC、Source、Wiki、RQ 重试和真实模型质量。

## 13. PR 拆分和合并顺序

| 顺序 | PR | 内容 | 依赖 |
| --- | --- | --- | --- |
| B0 | 契约确认 | 本文、OpenAPI 示例、数据模型差异 | 全员确认 |
| B1 | FastAPI 骨架 | Settings、Session、错误、基础 Health | A 提供运行环境约定 |
| B2 | 数据库基础 | ORM、Alembic、三张表、约束 | B1 |
| B3 | 初始化 | default user/workspace/profile | B2 |
| B4 | Storage | 接口、本地实现、安全测试 | B1，可与 B2/B3 并行 |
| B5 | 读取 API | Workspace/Profile、脱敏、集成测试 | B2/B3 |
| B6 | 联调修复 | Compose、Worker、前端、总 Gate | A/C/D 已有骨架 |

避免将 B1～B5 压成一个超大 PR。每个 PR 至少由一名跨角色成员 Review。

## 14. MVP 0 B 角色 Gate

完成条件：

- [ ] FastAPI 能在 Compose 中启动；
- [ ] `/api/docs` 和 `/api/openapi.json` 可访问；
- [ ] 空 PostgreSQL 可迁移到 head；
- [ ] 初始化连续运行不产生重复数据；
- [ ] 默认 Mock Profile 存在；
- [ ] 可选 Mac/Spark Profile 离线不阻塞启动；
- [ ] Profile API 不返回任何凭据字段；
- [ ] Local Storage 拒绝路径穿越和内容覆盖；
- [ ] PostgreSQL/Storage Health 可诊断；
- [ ] 容器重启后数据仍存在；
- [ ] Unit/Integration 测试通过；
- [ ] 日志、测试输出和 Git 中没有 Secret；
- [ ] A/C/D 已能使用冻结契约继续开发。

## 15. 待团队现场确认的问题

1. 是否接受 Python 3.12、SQLAlchemy async、psycopg 3 和 `uv`？
2. PostgreSQL 是否固定 17，还是由 A 选择其他主版本？
3. 是否给 `model_profiles` 增加稳定 `profile_key`？
4. CI/开发默认是否统一使用 `mock-default`？
5. 是否取消“默认 Ollama”假设，改为可选 Mac/Spark OpenAI-compatible Profile？
6. MVP 0 的 Model Profile 是只读联调，还是包含真实创建/测试接口？
7. MVP 0 是否禁止保存真实 API Key，仅交付加密接口和脱敏结构？
8. 本地 Compose 是否执行显式 migration/bootstrap entrypoint？
9. Health 的顶层和组件状态枚举是否接受本文定义？
10. `profile_key`、默认用户邮箱和默认 Workspace slug 是否接受本文建议值？

## 16. 签字区

| 角色 | 姓名 | 结论 | 日期 | 备注 |
| --- | --- | --- | --- | --- |
| A |  | 同意 / 修改后同意 / 不同意 |  |  |
| B |  | 同意 / 修改后同意 / 不同意 |  |  |
| C |  | 同意 / 修改后同意 / 不同意 |  |  |
| D |  | 同意 / 修改后同意 / 不同意 |  |  |

确认后，将本文中的最终决策同步到 README、architecture、data-model、api-contract、testing 和 deployment；若文档之间冲突，以合并后的 OpenAPI、Alembic 迁移和 ADR 为实现期事实来源。
