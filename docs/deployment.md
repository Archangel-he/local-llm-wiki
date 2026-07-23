# 部署与运维设计

## 环境

| 环境 | 用途 | 数据 |
| --- | --- | --- |
| Local | 开发和 MVP 验证 | 测试数据 |
| Staging | 阿里云部署演练 | 脱敏/固定 Fixtures |
| Production | 老师和真实用户使用 | 真实数据 |

Staging 与 Production 使用独立数据库、Storage 前缀和 Secret。

## Docker Compose 服务

```text
gateway     Caddy，静态前端和反向代理
api         FastAPI
worker      RQ Worker
postgres    PostgreSQL
redis       Redis
```

macOS 本地 Ollama 默认不进入 Compose，以使用 Metal：

```dotenv
LLM_PROVIDER=ollama
LLM_BASE_URL=http://host.docker.internal:11434
LLM_MODEL=<installed-model>
```

Linux/GPU 服务器可将 Ollama 作为同机服务或独立内网服务。以上变量用于首次启动时创建默认 Ollama Profile；用户后续在 Web 设置中选择 Ollama 或 OpenAI-compatible API。

## 配置

`.env.example` 只包含无秘密默认值和字段说明：

```dotenv
APP_ENV=local
PUBLIC_BASE_URL=http://localhost:8000
DATABASE_URL=postgresql+psycopg://wiki:wiki@postgres:5432/wiki
REDIS_URL=redis://redis:6379/0
STORAGE_BACKEND=local
LOCAL_STORAGE_PATH=/app/storage
LLM_PROVIDER=ollama
LLM_BASE_URL=http://host.docker.internal:11434
LLM_MODEL=<model>
MODEL_CREDENTIAL_ENCRYPTION_KEY_FILE=/run/secrets/model_credential_key
MAX_UPLOAD_MB=10
JOB_MAX_ATTEMPTS=3
```

生产 Secret 不提交 Git：

```text
DATABASE_PASSWORD
SESSION_SECRET
MODEL_CREDENTIAL_ENCRYPTION_KEY
OSS_ACCESS_KEY_ID
OSS_ACCESS_KEY_SECRET
```

本地开发可以通过受限权限的 Secret 文件提供模型凭据主密钥；生产环境优先使用阿里云 KMS/Secrets Manager 或 Docker Secret 挂载，不把主密钥写进数据库、镜像、Git 或普通日志。数据库只保存 API Key 密文和 `credential_key_version`。

## Local 启动目标

```bash
cp .env.example .env
docker compose up --build
docker compose exec api alembic upgrade head
```

访问：

```text
http://localhost:8000
http://localhost:8000/api/docs
http://localhost:8000/api/health
```

开发前端可单独启用 Vite HMR，但验收必须使用 Compose 中的构建产物。

## 阿里云部署前清单

必须获得服务器信息：

```text
ECS 实例规格
操作系统和版本
vCPU / RAM
GPU 型号 / GPU 数量 / 显存
系统盘和数据盘
公网 IP 和带宽
域名和 DNS 管理权限
Docker 安装权限
安全组修改权限
是否允许使用 OSS
```

在信息确认前，不承诺 27B 模型在云端的速度。

## 模型部署模式

### 模式 A：同机模型

ECS 有足够 GPU/显存或 CPU/RAM：

```text
API/Worker → 同机 Ollama
```

优点：部署简单、数据不出服务器。局限：模型与 Web 争抢资源。

### 模式 B：独立模型服务器

```text
ECS Web/API → VPC 私网 → GPU Model Server
```

优点：应用与推理解耦。模型端口只对应用安全组开放。

### 模式 C：开发期 Mac Studio

仅用于短期测试，不作为生产默认方案。若临时连接，必须使用受控 VPN/隧道和鉴权，不直接把 Ollama 端口暴露公网。

阿里云上的 API/Worker 无法直接访问访问者 Mac 的 `localhost:11434`。若 Ollama 运行在个人 Mac，当前只支持网站也在该 Mac 上的 localhost 模式；云端访问个人 Mac 需要未来单独设计有身份、加密和出站连接的 Local Connector，不属于当前 MVP。

### 模式 D：用户自备 OpenAI-compatible API

```text
Browser → API 保存 write-only API Key
Worker → HTTPS → 用户配置的模型服务
```

- 用户必须知道任务所需的来源/Wiki 片段会离开本服务器；
- API Key 认证加密保存，Worker 只在调用时短暂解密；
- 首期只承诺 OpenAI-compatible chat/streaming 语义；
- Profile 必须先通过连接和能力测试；
- 外部服务的价格、配额、保留策略和可用性由用户确认。

## 自定义 Endpoint 安全策略

Local 与 Production 使用不同策略：

- Local：允许系统预设的 `host.docker.internal` Ollama 地址；其他地址仍需校验；
- Production：默认只允许 HTTPS 公网 Endpoint；
- 私网模型服务需要部署管理员配置 hostname/CIDR allowlist；
- 拒绝 loopback、link-local、云元数据地址、未授权 RFC1918/ULA 和非 HTTP(S) scheme；
- DNS 解析后的所有 IP 都要检查，连接前再次解析，降低 DNS rebinding 风险；
- 禁止自动跟随重定向，或对每个重定向目标重新执行同样检查；
- 限制连接/读取超时、响应大小、并发和允许端口；
- 上游错误只返回脱敏摘要，不透传可能包含凭据的响应头和正文。

## 网络和 HTTPS

公网只开放：

```text
80/tcp
443/tcp
```

`22/tcp` 只允许可信固定 IP。以下端口不得公网开放：

```text
5432 PostgreSQL
6379 Redis
11434 Ollama
对象存储管理端口
```

Caddy：

- 提供静态前端；
- `/api/*` 反向代理 FastAPI；
- 处理域名 HTTPS；
- 保留 SSE 流式响应；
- 生成 request ID 或透传应用 request ID。

## Storage 选择

### 本地/ECS 数据盘

适合首个部署，运维简单。要求：

- Storage 路径单独挂载；
- 磁盘空间告警；
- 定期异机备份；
- 容器删除不影响数据。

### OSS

适合正式多用户：

- Bucket 默认私有；
- API 校验权限后读取或生成短时签名 URL；
- Raw 使用内容寻址 key；
- 开启适当的版本/生命周期策略前先确认成本；
- 不将 OSS 密钥发送给浏览器。

## 数据库迁移

部署顺序：

1. 备份数据库；
2. 拉取已标记版本；
3. 启动/更新 PostgreSQL 和 Redis；
4. 运行 `alembic upgrade head`；
5. 启动 API 与 Worker；
6. 运行 Health 和只读 Smoke；
7. 切换网关流量；
8. 执行生产 E2E。

破坏性迁移必须提供回滚或向前修复方案，不在启动时隐式执行。

## 备份

备份对象：

```text
PostgreSQL dump / base backup
Raw 与附件
应用配置（不含明文 Secret）
Schema/Prompt 版本
Model Profile 密文和非秘密元数据
```

模型凭据主密钥与数据库备份分开保管。恢复演练必须证明：没有主密钥不能解密 Profile；授权恢复主密钥后可以测试 Profile；轮换后旧密文完成渐进重加密。不得为了“方便恢复”导出明文 API Key。

最低验收不是“备份命令成功”，而是恢复演练：

```text
创建测试 Workspace
→ 摄取固定来源
→ 备份
→ 清空隔离测试环境
→ 恢复
→ Wiki、引用、图谱和 Raw 哈希全部一致
```

实际备份频率、保留期和 RPO/RTO 在老师确认真实数据重要性后确定。

## 日志与监控

结构化日志字段：

```text
timestamp
level
service
request_id
job_id
workspace_id
user_id
model_profile_id
model_provider
model_name
event
duration_ms
error_code
```

不得记录：密码、Session、API Key、Authorization header、带敏感 query 的 Base URL、OSS Secret、完整私人文件内容和不必要的完整 Prompt。

最低监控：

- API 健康与错误率；
- PostgreSQL/Redis 可用性；
- Worker 心跳；
- 队列长度和最老 Job 等待时间；
- Job 成功/失败/重试；
- 各 Provider/Profile 的脱敏可用性、调用耗时、429 和错误率；
- 磁盘使用率；
- 备份最后成功时间。

## 故障恢复

- LLM 不可用：Health degraded，Wiki 浏览继续可用；
- Profile invalid/revoked：禁止新任务，提示 Owner/用户测试或更换；
- 外部 API 429/5xx：按 Retry-After/退避策略重试，不切换到另一 Profile 造成不可审计结果；
- Redis 重启：根据 PostgreSQL queued/retrying Job 恢复入队；
- Worker 中断：超时扫描将 stale running Job 转 retrying；
- Storage 不可用：禁止创建 Source，既有 Wiki 仍可读；
- PostgreSQL 不可用：API 返回统一不可用错误，不进行降级写入；
- SSE 断开：客户端重新获取 Job/Query 状态。

## 发布验收

- 使用 Git tag/commit SHA 构建镜像；
- `.env.example` 与实际配置项一致；
- Migration、备份和恢复测试通过；
- 80/443、SSH 和内部端口检查通过；
- HTTPS、Cookie 和限流生效；
- 两用户隔离 E2E 通过；
- 模型不可用时只读能力通过；
- 回滚步骤经过 Staging 演练。

## 官方参考

- [阿里云 ECS 安全组](https://help.aliyun.com/zh/ecs/user-guide/security-group-rules/)
- [阿里云 ECS HTTPS](https://help.aliyun.com/zh/ecs/user-guide/ssl)
- [阿里云 GPU 实例](https://help.aliyun.com/zh/ecs/user-guide/gpu-accelerated-compute-optimized-and-vgpu-accelerated-instance-families-1)
- [OSS HTTPS](https://help.aliyun.com/zh/oss/user-guide/access-oss-by-https-protocol)
- [Caddy reverse proxy](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy)
- [Ollama API](https://docs.ollama.com/api/introduction)
- [OWASP Secrets Management](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)
- [OWASP SSRF Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html)
