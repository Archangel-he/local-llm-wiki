# MVP0-C 集成与合并说明

本文说明 LLM Adapter 与 RQ Worker 骨架如何接入主工程，以及 A/B/C/D 四条职责线之间的稳定边界。

## 交付范围

MVP0-C 提供：

- Provider-neutral `LLMAdapter` 协议；
- Ollama 与 OpenAI-compatible Provider 骨架；
- 确定性 `MockLLMAdapter`；
- 安全、可分类的 Adapter 错误；
- 临时启动 Profile 桥接；
- RQ Worker 启动、注册健康检查和基础设施 probe job；
- 离线单元测试与显式 Redis 集成测试。

MVP0-C 不实现真实 Ingest、Query、Lint、Export、业务 Job 状态机、Model Profile ORM、凭据加密或前端模型设置。这些能力分别属于 B、后续 MVP 和 D。

## 主工程布局

```text
backend/app/llm/          Provider-neutral 类型、Mock 与 Provider
backend/app/worker/       Worker runner、配置、健康与 probe job
backend/app/services/llm.py
                          旧 services 路径的兼容桥接层
backend/tests/            C 单元测试和 Redis 集成测试
worker/main.py            Compose Worker 的薄入口
```

所有应用代码使用 `app.llm.*` 和 `app.worker.*`。不得重新引入 `backend.llm`、`backend.worker` 或第二套 Ollama Adapter。

## 公共 LLM 契约

```python
health(profile)
test_connection(profile)
generate_structured(profile, schema, messages, options)
stream(profile, messages, options)
```

`RuntimeModelProfile` 是一次调用所需的内存对象。B 层负责授权、状态检查、Endpoint 安全策略和凭据解密；C 只消费它。Profile 的 `repr` 和 `safe_snapshot()` 不输出凭据、URL path、query 或 fragment。

MVP0 中：

- Ollama 只执行有界 Health 探测；
- OpenAI-compatible 只固定 URL/认证和公共接口边界，不主动访问用户 Endpoint；
- 两者尚未启用的生成方法返回明确的 `NOT_ENABLED`；
- Mock 完整实现契约，用于业务和 CI 测试。

## 默认 Profile 桥接

`app.llm.bootstrap.bootstrap_runtime_profile()` 暂时从启动配置构造非秘密默认 Profile。配置缺失或结构无效时返回 `None`，Health 降级但应用不崩溃。

B 分支加入 `model_profiles` 后，只需把 Health 调用处替换为数据库 Profile loader；Provider Adapter 和公开类型不需要依赖 ORM。

## Health 接入

`GET /api/health`：

- 从 PostgreSQL 执行只读探测；
- Ping Redis，并通过 RQ 注册/心跳判断真实 Worker；
- 只探测一个默认模型 Profile；
- LLM 离线、模型未配置或 Worker 未注册时返回 HTTP 200 + `degraded`；
- API 或 PostgreSQL 不可用时返回 `unhealthy` 状态内容。

浏览器只消费 Health JSON，不直接连接 Redis、Mock、Ollama 或外部 API。

## Worker 接入

Compose 继续运行：

```text
python -m worker.main
```

根入口只负责把 `backend` 放入导入路径并调用 `app.worker.runner.main()`。Worker 监听 `RQ_QUEUE_NAME=default`，启动前 Ping Redis，日志不会输出可能带凭据的完整 Redis URL。

MVP1 业务 Handler 必须只接收 `job_id`，再从 PostgreSQL 加载 Workspace、Profile 和任务状态。

## 测试

容器内或 `backend/` 工作目录运行：

```bash
python -m pytest tests/ -m "not integration"
```

Redis 集成测试必须使用可清空的隔离数据库：

```bash
REDIS_TEST_URL=redis://redis:6379/15 python -m pytest tests/ -m integration
```

集成测试会对指定数据库执行 `FLUSHDB`，禁止指向开发、Staging 或 Production 数据库。

## 合并顺序

1. 先合并 A 的 Compose、CI、Health 响应结构和主工程目录。
2. 合并 B 的 FastAPI、数据库与配置基础。
3. 应用 `mvp0-c-against-main.patch`。
4. 若 B 已提供 Model Profile loader，只替换 bootstrap 调用，不修改 Adapter。
5. 合并 D，并让前端仅使用 API 的脱敏 Provider/Model/Health 数据。
6. 运行迁移、C 测试、完整 CI 和 `make verify-mvp0`。

## 冲突热点

- `backend/app/services/llm.py`：保留 C 的兼容桥接，不恢复旧同步 Ollama 类。
- `backend/app/api/health.py`：保留 A 的响应格式，同时使用 C 的 LLM/Worker 探测。
- `worker/main.py`：保留容器入口路径，实际实现放在 `app.worker.runner`。
- `backend/requirements.txt` 与 `backend/pyproject.toml`：保留主工程依赖，并使用 `redis>=5,<7`、`rq>=2,<3`、`httpx>=0.27,<1`。
- B 的 Model Profile：ORM 不进入 `app.llm`；在服务层转换成 `RuntimeModelProfile`。

## 回滚

本交付不创建提交或推送。若需要回滚：

1. 恢复干净 `main` 工作树；
2. 删除新增的 `backend/app/llm`、`backend/app/worker` 和 C 测试；
3. 恢复原 `services/llm.py`、Health、Worker 入口和依赖文件；
4. 重新运行原 MVP0 Gate。

生成的补丁只包含相对干净 `main` 的改动，可用 `git apply --check` 预检，并可用 `git apply -R` 反向撤销。
