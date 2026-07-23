# local-llm-wiki

从 localhost 起步，构建一个可部署、可协作、持续生长的 LLM Wiki。

`local-llm-wiki` 是 [Andrej Karpathy 的 LLM Wiki 构想](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)的工程化实现：系统不只在提问时临时检索原始文档，而是让 LLM 持续阅读新资料、整理概念、维护交叉引用，并将结果沉淀为可读、可追溯、可持续演化的 Markdown Wiki。

项目首先在 Mac Studio 上通过 Ollama 和本地 27B 模型完成闭环验证，之后部署到阿里云服务器，并逐步支持多用户与团队协作。

> [!IMPORTANT]
> 项目目前处于设计与初始化阶段。本 README 描述目标架构、分阶段 MVP 和验收标准，代码与启动配置尚未全部实现。

## 核心理念

传统 RAG 通常在每次提问时重新检索和拼接文档片段；LLM Wiki 则把已经完成的归纳、关联和冲突检查保存在一个持续演化的知识层中。

- **Raw sources**：用户提供的原始资料，只读保存，作为事实来源。
- **Wiki**：由 LLM 创建和维护的 Markdown 页面，包括主题、实体、摘要、引用和交叉链接。
- **Schema**：约束 LLM 如何摄取、查询和维护 Wiki 的规则文件。

人的工作是选择资料、提出问题和校验结果；模型负责归纳、归档、链接与日常维护。

## 实施策略

项目从零开始，因此采用：

> **单用户产品体验，多用户数据基础。**

第一版启动后自动进入默认用户和默认知识空间，不开发注册、登录、邀请和角色管理；但数据库、API、文件路径和任务从第一天就包含 `user_id` 与 `workspace_id`。

这样既能尽快验证“资料 → Wiki → 问答 → 增量维护”的核心价值，也能避免后续增加多用户时重写存储和业务逻辑。

### 第一阶段暂不实现

- 注册、登录和找回密码；
- 邀请成员和邮件通知；
- Owner / Editor / Viewer 权限；
- 管理后台和用户配额；
- 多人并发编辑。

### 第一阶段必须保留

- PostgreSQL 作为业务主数据库；
- 所有业务数据归属于 `workspace_id`；
- 默认用户和默认知识空间；
- 按知识空间隔离的文件路径；
- 可替换的文件存储和模型服务接口；
- 数据库迁移、后台任务和审计日志；
- 跨知识空间访问测试。

DuckDB 不再承担用户、权限和并发任务等在线业务数据；未来如有需要，可将其用于本地分析或数据导出。

## 目标

- 在 localhost 完成从资料摄取到 Wiki 问答的完整闭环。
- 通过 Ollama 调用 Mac Studio 上的本地 27B 模型。
- 将 Markdown、文本和 PDF 等资料摄取为结构化 Wiki。
- 根据新增资料增量更新已有页面，而不是重复生成孤立摘要。
- 回答问题时给出可追溯的 Wiki 页面和原始来源。
- 检查矛盾、过期内容、孤立页面和缺失链接。
- 从数据层支持用户、知识空间和团队权限隔离。
- 使用 Docker Compose 统一管理本地与服务器环境。
- 在核心闭环稳定后部署到阿里云服务器。

## 系统架构

```mermaid
flowchart LR
    U["Browser"] --> F["HTML / CSS / JavaScript"]
    F --> A["FastAPI API"]

    A --> P[("PostgreSQL")]
    A --> Q["Redis queue"]
    A --> S["Storage adapter"]
    Q --> W["Background worker"]
    W --> L["LLM adapter"]
    W --> S
    L --> O["Ollama / model service"]

    S --> FS["Local filesystem"]
    S -. "production" .-> OSS["Alibaba Cloud OSS"]

    subgraph APP["Docker Compose application"]
        F
        A
        P
        Q
        W
    end

    subgraph MODEL["Model runtime"]
        O
    end
```

### 技术选型

| 层级 | 技术 | 职责 |
| --- | --- | --- |
| 前端 | HTML / CSS / JavaScript | 资料上传、任务状态、Wiki 浏览与问答 |
| API | FastAPI | 认证、权限、工作区、查询和任务编排 |
| 业务数据库 | PostgreSQL | 用户、空间、来源、任务、页面元数据和审计记录 |
| 任务队列 | Redis + Worker | 执行耗时的摄取、查询和 Lint 任务 |
| 模型服务 | Ollama / 可替换模型接口 | 本地或服务器端模型推理 |
| 知识载体 | Markdown | 保存可阅读、可导出和可版本化的 Wiki 内容 |
| 文件存储 | 本地文件系统 → OSS | 保存不可变原始资料、附件和导出文件 |
| 运行环境 | Docker Compose | 统一管理本地与服务器服务 |

> [!NOTE]
> 在 macOS 上，Ollama 原生运行可以直接使用 Metal。应用容器通过 `host.docker.internal:11434` 访问 Ollama。部署到阿里云后，可通过环境变量将模型切换为同机 Ollama 或独立推理服务。

## 数据隔离

即使第一版只有一个用户，也使用完整的隔离关系：

```text
User
└── Workspace
    ├── Sources
    ├── Ingest Jobs
    ├── Wiki Pages
    ├── Citations
    └── Audit Logs
```

计划中的核心数据表：

```text
users
workspaces
memberships
sources
ingest_jobs
wiki_pages
wiki_revisions
citations
audit_logs
```

本地文件也必须按空间隔离：

```text
storage/workspaces/<workspace_id>/raw/
storage/workspaces/<workspace_id>/wiki/
storage/workspaces/<workspace_id>/exports/
```

禁止使用全局 `workspace/raw`、全局当前用户或不带 `workspace_id` 的资料查询。

## 核心工作流程

### Ingest — 摄取

1. 用户将资料上传到指定知识空间。
2. 系统计算哈希，通过存储接口保存不可变原文件。
3. PostgreSQL 记录来源和任务，Worker 异步处理任务。
4. 模型提取关键信息，生成或更新空间内的 Wiki 页面。
5. 更新空间的 `index.md`，并追加摄取审计记录。

### Query — 查询

1. 校验用户是否有权访问指定知识空间。
2. 读取空间内的 Wiki 索引，定位相关页面。
3. 基于已积累的知识回答，必要时回溯原始资料。
4. 返回页面级和来源级引用；未知信息必须明确拒答。

### Lint — 维护

定期检查：

- 相互矛盾或已被新资料取代的结论；
- 没有入链的孤立页面；
- 被频繁提及但尚无独立页面的概念；
- 缺失来源或交叉引用的陈述；
- 断开的 Wiki 链接；
- 长期未更新、需要重新核验的内容。

## 分阶段 MVP

每个阶段都必须形成“输入 → 处理 → 输出 → 自动验证”的完整闭环。前一阶段未通过验收，不进入下一阶段。

### MVP 0：单用户工程基础

目标：应用可以完整启动，但暂时没有登录界面。

启动时自动创建：

```text
default-user
└── default-workspace
```

交付内容：

- FastAPI、PostgreSQL、Redis、Worker 和静态前端；
- `GET /api/health`；
- Alembic 数据库迁移；
- 默认用户与默认空间初始化；
- 本地存储适配器；
- Ollama 连接检查；
- Docker Compose 持久化卷。

闭环测试：

```text
docker compose up
→ 自动创建默认用户和空间
→ 页面显示 API、数据库、队列和 Ollama 状态
→ 重启容器
→ 默认空间和测试数据仍然存在
```

验收标准：

- 所有服务可以一条命令启动；
- Ollama 不可用时应用仍可启动，并明确展示错误状态；
- 数据库迁移可以从空库执行；
- 重复初始化不会产生多个默认用户或空间。

### MVP 1：单用户文档摄取

目标：验证最核心的“资料变成 Wiki”。

```text
上传 TXT/Markdown
→ 保存不可变原文件
→ Worker 调用 Ollama
→ 生成 Wiki 页面
→ 更新 index.md 和审计记录
→ 用户在网页中浏览页面
```

验收标准：

- 原始文件哈希保持不变；
- 重复上传相同文件不会生成重复来源；
- Wiki 页面包含可回溯的来源引用；
- 任务状态依次经过 `queued`、`running`、`completed`；
- 页面、来源和任务均属于默认 `workspace_id`；
- 修改 URL 中的 `workspace_id` 不能访问其他或不存在的空间；
- 重启应用后仍可浏览 Wiki。

### MVP 2：问答、增量更新与 Lint

目标：在单用户环境完成 LLM Wiki 的全部核心价值验证。

查询闭环：

```text
输入问题
→ 搜索当前空间 Wiki
→ 生成答案
→ 返回并打开引用
```

增量闭环：

```text
上传第二份相关资料
→ 找到已有主题页
→ 更新而不是复制页面
→ 保留两份来源
→ 标记新旧资料冲突
```

Lint 闭环：

```text
执行 Lint
→ 发现断链、孤立页面和缺失来源
→ 用户打开具体问题
```

验收标准：

- 已知问题返回正确答案和有效引用；
- 未知问题明确说明当前资料无法确定；
- 相关新资料更新既有主题页，不制造重复主题；
- 冲突信息不会被静默覆盖；
- Lint 至少能报告断链、孤立页面和缺失来源；
- Query、Ingest 和 Lint 都留下审计记录。

### MVP 3：真正的多用户

目标：在不修改 Wiki 核心引擎的前提下增加身份与数据隔离。

交付内容：

- 注册、登录和退出；
- 安全的会话 Cookie；
- 一个用户可以创建多个知识空间；
- API、搜索、下载和任务均进行权限校验；
- 上传和后台任务支持多个用户并发提交。

关键隔离测试：

```text
Alice 创建 Workspace A
Bob 创建 Workspace B
Alice 上传私有资料
Bob 请求 Alice 的资料、页面、任务和文件
→ 全部返回 403 或 404
```

验收标准：

- Alice 与 Bob 可以同时上传，任务和结果不会串数据；
- Query 不能检索到其他空间的页面；
- 原始文件和导出文件不能绕过 API 权限访问；
- 删除一个用户的测试空间不会影响其他空间。

### MVP 4：团队协作

目标：允许多个用户共同维护一个知识空间。

计划角色：

| 角色 | 浏览/查询 | 上传/维护 | 管理成员/空间 |
| --- | --- | --- | --- |
| Owner | ✅ | ✅ | ✅ |
| Editor | ✅ | ✅ | ❌ |
| Viewer | ✅ | ❌ | ❌ |

闭环测试：

```text
Owner 创建空间并邀请 Editor、Viewer
→ Editor 上传并更新 Wiki
→ Viewer 可以浏览和查询
→ Viewer 尝试上传时被拒绝
→ Owner 可以查看完整审计记录
```

验收标准：

- 邀请、接受、退出空间形成完整闭环；
- 每个 API 都通过角色权限矩阵测试；
- Wiki 更新保留版本；
- 并发修改使用版本号检测冲突，不允许静默覆盖。

### MVP 5：阿里云部署

目标：将本地验证过的相同应用部署到老师的阿里云服务器。

迁移关系：

```text
localhost                  Alibaba Cloud
──────────────────────     ──────────────────────
Local filesystem       →   Data disk or OSS
localhost URL          →   Domain + HTTPS
Native Ollama          →   Server Ollama or model service
Docker Compose         →   Docker Compose on ECS
Local backup           →   Scheduled off-host backup
```

验收闭环：

```text
全新服务器执行部署
→ 完成数据库迁移
→ 通过 HTTPS 注册两个测试用户
→ 上传、摄取、查询和 Lint
→ 执行备份
→ 清空测试环境并恢复
→ Wiki、来源和引用仍然完整
```

生产环境最低要求：

- 只公开 Web 所需的 80/443 端口；
- PostgreSQL、Redis、对象存储和 Ollama 不直接暴露到公网；
- SSH 只允许可信 IP；
- 使用 HTTPS、安全 Cookie、上传大小限制和请求限流；
- 数据库、原始资料和 Wiki 定期异机备份；
- 使用环境变量或 Secret 管理密码和密钥；
- 上线前确认服务器 CPU、内存、GPU、显存、磁盘和操作系统。

模型是否与应用部署在同一台服务器，取决于老师服务器的硬件。业务代码只依赖统一的 `LLM_BASE_URL`，因此无需绑定具体部署方式。

阿里云相关参考：

- [ECS 安全组规则](https://help.aliyun.com/zh/ecs/user-guide/security-group-rules/)
- [为 Web 服务配置 HTTPS](https://help.aliyun.com/zh/ecs/user-guide/ssl)
- [阿里云 GPU 实例规格](https://help.aliyun.com/zh/ecs/user-guide/gpu-accelerated-compute-optimized-and-vgpu-accelerated-instance-families-1)
- [通过 HTTPS 访问 OSS](https://help.aliyun.com/zh/oss/user-guide/access-oss-by-https-protocol)

## 四人分工

成员不与固定账号绑定，按 A、B、C、D 四个角色协作；团队可以根据实际专长交换角色。

| 角色 | 主要职责 | 主要目录 |
| --- | --- | --- |
| A：架构与集成 | 架构、Docker、CI、接口契约、版本验收和云端部署 | `docker-compose.yml`、`.github/`、集成测试 |
| B：后端与数据 | FastAPI、PostgreSQL、数据模型、认证和权限 | `backend/api/`、`backend/models/`、`migrations/` |
| C：LLM 与 Wiki | Ollama、Worker、Ingest、Query、增量更新和 Lint | `backend/services/`、`backend/worker/`、Schema |
| D：前端与测试 | 页面交互、任务状态、Wiki 浏览、测试资料和 E2E | `frontend/`、`tests/e2e/`、用户文档 |

### 各阶段任务

| 阶段 | A | B | C | D |
| --- | --- | --- | --- | --- |
| MVP 0 | Compose、CI、集成验收 | 数据模型、Health API | Ollama 与 Worker 骨架 | 状态页、E2E 骨架 |
| MVP 1 | 摄取接口契约 | 上传、哈希、任务记录 | Wiki 生成与索引 | 上传与 Wiki 浏览页 |
| MVP 2 | 验收数据集 | Query API、检索 | 引用、增量更新、Lint | 问答与 Lint 页面 |
| MVP 3 | 安全验收 | 注册、会话、空间隔离 | 任务空间隔离 | 登录和空间管理页 |
| MVP 4 | 权限矩阵验收 | 成员和角色 API | Wiki 版本与冲突 | 邀请、成员和版本 UI |
| MVP 5 | 部署、HTTPS、备份 | 数据迁移与恢复 | 模型部署与质量验证 | 生产 E2E 和使用文档 |

### 协作原则

- 每个 MVP 建立一个 GitHub Milestone；
- 每个阶段拆成 A、B、C、D 四个主 Issue；
- `main` 始终保持可启动和测试通过；
- 使用短生命周期分支和 Pull Request；
- API 与数据结构先确定，前端使用 Mock API 并行开发；
- 跨角色修改使用独立提交，避免多人同时重构相同文件。

## 计划中的目录结构

```text
local-llm-wiki/
├── backend/
│   ├── api/                 # FastAPI 路由
│   ├── core/                # 配置、认证和权限
│   ├── models/              # PostgreSQL 数据模型
│   ├── services/            # Ingest、Query、Lint 和存储接口
│   └── worker/              # 后台任务
├── frontend/                # 原生 Web 界面
├── migrations/              # Alembic 数据库迁移
├── storage/                 # 本地开发数据，不提交到 Git
├── tests/
│   ├── fixtures/            # 固定验收资料
│   ├── integration/
│   └── e2e/
├── .env.example
├── Dockerfile
└── docker-compose.yml
```

## 计划中的 API

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `GET` | `/api/health` | 检查应用依赖状态 |
| `POST` | `/api/auth/register` | 注册用户，MVP 3 启用 |
| `POST` | `/api/auth/login` | 登录，MVP 3 启用 |
| `GET` | `/api/workspaces` | 获取有权访问的知识空间 |
| `POST` | `/api/workspaces` | 创建知识空间 |
| `POST` | `/api/workspaces/{id}/sources` | 上传原始资料 |
| `GET` | `/api/workspaces/{id}/jobs/{job_id}` | 获取任务状态 |
| `POST` | `/api/workspaces/{id}/query` | 查询 Wiki |
| `POST` | `/api/workspaces/{id}/lint` | 检查 Wiki 健康状态 |
| `GET` | `/api/workspaces/{id}/wiki` | 获取 Wiki 页面列表 |
| `GET` | `/api/workspaces/{id}/wiki/{path}` | 读取指定 Wiki 页面 |

## 预期启动方式

以下命令代表完成 MVP 0 后的目标体验，目前尚不可用。

### 环境要求

- macOS、Linux 或 Windows + WSL2；
- Docker 与 Docker Compose；
- 本地模型模式需要 [Ollama](https://ollama.com/)；
- 足够运行所选模型的内存、显存和磁盘空间。

### 启动

```bash
git clone https://github.com/Archangel-he/local-llm-wiki.git
cd local-llm-wiki

cp .env.example .env
# 在 .env 中配置已安装的模型

docker compose up --build
```

启动后计划访问：

- Web：<http://localhost:8000>
- API 文档：<http://localhost:8000/docs>
- 健康检查：<http://localhost:8000/api/health>

计划中的关键环境变量：

```dotenv
DATABASE_URL=postgresql+psycopg://wiki:wiki@postgres:5432/wiki
REDIS_URL=redis://redis:6379/0
STORAGE_BACKEND=local
LOCAL_STORAGE_PATH=/app/storage
LLM_PROVIDER=ollama
LLM_BASE_URL=http://host.docker.internal:11434
LLM_MODEL=<your-local-model>
```

## 测试策略

LLM 输出具有随机性，因此测试分为两层：

1. **确定性自动测试**：使用 Mock Ollama 验证 API、权限、存储、任务和引用结构。
2. **真实模型冒烟测试**：在 Mac Studio 或模型服务器上验证结构约束和事实要求，不逐字比较生成文本。

计划为每个阶段提供统一验收命令：

```bash
make verify-mvp0
make verify-mvp1
make verify-mvp2
make verify-mvp3
make verify-mvp4
make verify-mvp5

make test-ollama
```

固定验收资料应覆盖：

- 一个可以准确回答的事实；
- 一个资料中不存在的问题；
- 两份存在更新或冲突的来源；
- 一个断开的 Wiki 链接；
- 两个相互隔离的用户和知识空间。

## 设计原则

- **Core first**：先验证资料摄取、Wiki、问答和维护闭环。
- **Multi-tenant ready**：界面可以先单用户，数据结构不能是全局单用户。
- **Source first**：原始资料不可变，生成内容必须能回溯来源。
- **Markdown first**：Wiki 内容可阅读、导出、迁移和版本化。
- **Incremental**：新增资料应更新既有知识结构，而不是制造重复页面。
- **Local first, cloud ready**：本地验证和云端部署使用相同接口与配置方式。
- **Inspectable**：模型写入、引用、权限和维护动作都留下记录。
- **Simple first**：在规模确实需要之前，不引入向量数据库和复杂编排平台。

## 致谢

本项目源于 Andrej Karpathy 提出的 [LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) 模式。原始构想强调三层结构：不可变的原始资料、由 LLM 维护的 Markdown Wiki，以及约束维护流程的 Schema。

## License

暂未指定开源许可证。在许可证提交前，仓库内容默认保留全部权利。
