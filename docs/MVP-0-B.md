# MVP 0 B：后端与数据交付说明

## 交付范围

B 角色在 A 的工程骨架上交付：

- FastAPI Workspace 与 Model Profile 只读 API；
- PostgreSQL `users/workspaces/memberships/model_profiles` 模型；
- Alembic `002` 迁移，补齐外键、唯一约束和 Check Constraint；
- 幂等的默认用户、Workspace、Membership 和 Mock Profile 初始化；
- 可选 Mac Studio/DGX Spark Qwen 3.6 Profile 初始化；
- Model Profile 公开响应脱敏；
- Credential 加密接口，MVP 0 禁止用明文或 No-op 实现保存真实密钥；
- 流式、原子、不可覆盖且防路径穿越的 Local Storage；
- 统一验证错误和 Request ID；
- Unit/Integration 测试。

## 本地初始化

```bash
alembic upgrade head
python -m app.seed
```

API 容器默认通过 `entrypoint.sh` 自动执行以上两步。生产环境应设置
`AUTO_MIGRATE=false`，并在部署阶段显式迁移。

## 默认记录

```text
default-user@local.invalid
└── Default Workspace (slug=default)
    └── mock-default (provider=mock, status=active)
```

设置下列变量可额外初始化真实 Profile；模型不可达不会阻止系统启动：

```dotenv
MAC_QWEN36_ENABLED=true
MAC_QWEN36_BASE_URL=http://host.docker.internal:30000/v1
MAC_QWEN36_MODEL=qwen36-aggressive-q4km

SPARK_QWEN36_ENABLED=true
SPARK_QWEN36_BASE_URL=http://spark-tunnel:30000/v1
SPARK_QWEN36_MODEL=qwen36-aggressive-q4km
```

## MVP 0 API

```text
GET /api/health
GET /api/workspaces
GET /api/workspaces/{workspace_id}
GET /api/workspaces/{workspace_id}/model-profiles
GET /api/workspaces/{workspace_id}/model-profiles/{profile_id}
```

公开的 Model Profile 只返回脱敏后的 `endpoint_origin` 和
`has_credential`，不会返回 `base_url`、密文或密钥版本。

## 交接给 C

C 应复用：

- `app.models.ModelProfile`；
- `app.repositories.workspaces.get_model_profile`；
- `app.services.credentials.CredentialCipher`；
- Health 中的 `llm/worker/redis` 组件槽位。

C 不应在 Worker 中复制另一套 Profile ORM，也不应直接公开或记录凭据。

## 交接给 D

D 可以通过 OpenAPI 使用 Workspace/Profile 读取接口。MVP 0 模型设置仍可使用
Mock 表单；创建、替换凭据和连接测试属于 MVP 1 的写接口。

## 验证

```bash
pytest tests/unit -v
pytest tests/integration -v
ruff check app tests
```

完整环境使用仓库根目录：

```bash
docker compose up --build
make verify-mvp0
```
