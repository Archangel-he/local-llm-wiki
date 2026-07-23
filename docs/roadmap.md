# 完整路线图

## 执行原则

- 每个 MVP 都形成可演示、可测试、可回归的闭环；
- 前一 Gate 未通过，不进入下一阶段；
- 每个阶段至少拆为 A/B/C/D 四个主 Issue；
- 前端使用 Mock 契约并行开发，不等待全部后端完成；
- LLM 相关测试区分 Mock 和真实模型；
- `main` 始终可启动。

## 角色

| 角色 | 责任边界 |
| --- | --- |
| A：架构与集成 | Compose、CI、跨模块契约、Gate、部署和发布 |
| B：后端与数据 | FastAPI、PostgreSQL、Alembic、认证、权限和 Storage |
| C：LLM 与 Wiki | Ollama、RQ、Parser、Schema、Ingest、Query、Lint |
| D：前端与测试 | 工作区、图谱、问答、Wiki、Fixtures、E2E 和文档 |

角色可以交换，但每个阶段必须明确单一负责人和 Reviewer。

## MVP 0：工程基础

### 目标

从空仓库得到一条命令可启动、可迁移、可验证的系统骨架；前端是可操作线框，不追求视觉完成度。

### 范围

- Python/FastAPI 项目；
- PostgreSQL + Alembic；
- Redis + RQ Worker；
- Local Storage adapter；
- Ollama adapter 和 degraded health；
- Caddy + Vite + TypeScript；
- 三栏/上下分割 Mock 前端；
- 默认用户和默认 Workspace；
- Unit/Integration/E2E 基础设施；
- `.env.example`、Makefile、CI；
- 选择并提交开源许可证。

### 分工

| 角色 | 任务 |
| --- | --- |
| A | Compose、Caddy、CI、Makefile、Health Gate |
| B | FastAPI、基础表、Alembic、默认用户/空间、Storage interface |
| C | LLM adapter、RQ Worker 骨架、Mock LLM |
| D | Vite/TS、可拖动工作区、Mock 文件/图谱/问答/Wiki、E2E |

### 闭环

```text
clone
→ cp .env.example .env
→ docker compose up --build
→ 自动迁移和初始化
→ 打开三栏 Mock 工作区
→ 查看所有组件 Health
→ 重启
→ 数据仍存在
```

### Gate

- `make verify-mvp0` 全绿；
- 空库迁移可重复；
- 默认用户/空间不重复；
- Ollama 离线时只显示 degraded；
- 四节点 Mock 图可交互；
- 无 Secret 进入 Git。

### 预计

4 人并行约 3～4 个工作日。以 Gate 为准，不以日期强行结束。

## MVP 1：Markdown/TXT 摄取

### 目标

完成第一个真实产品闭环：来源上传后生成可浏览、可追溯的 Wiki 和图谱。

### 范围

- UTF-8 `.md`、`.txt`，默认最大 10 MiB；
- SHA-256、MIME 和安全文件名；
- Source、Job、Wiki Page/Revision/Link/Citation；
- RQ 超时、最多 3 次尝试（首次 + 2 次重试）、取消和幂等；
- 结构化 Ingest JSON Schema；
- `wikilink/citation/derived_from`；
- 文件树、Job SSE、Markdown 阅读和基础图谱；
- Obsidian Vault/ZIP 最小导出。

不包括 PDF、登录、角色和向量检索。

### 分工

| 角色 | 任务 |
| --- | --- |
| A | Source/Job/Wiki 契约、跨服务集成和 Gate |
| B | Upload API、Storage、表和 Wiki 提交事务 |
| C | Parser、Ingest Schema、RQ、Ollama 和引用验证 |
| D | 文件树、上传、Job 状态、基础图谱、Wiki 阅读、E2E |

### 闭环

```text
上传 aurora-a.md
→ Raw 哈希保存
→ queued/running/completed
→ 生成 Aurora 和 Lin 页面
→ 图谱出现节点与链接
→ 点击节点打开 Wiki
→ 导出 Vault
```

### Gate

- 重复上传不重复 Source/Job；
- Raw 字节不被修改；
- 非法 JSON 不产生半个 Wiki；
- Wiki 更新一次事务提交；
- 引用指向真实 Source；
- 导出可由 Obsidian 打开；
- `make verify-mvp1` 全绿。

### 预计

约 5 个工作日。

## MVP 2：增量知识、PDF、Query 与 Lint

### 目标

验证 LLM Wiki 与普通“文档摘要工具”的核心差异：知识会增量更新、问答有引用、冲突不会消失。

### 范围

- 文本型 PDF，默认最大 50 MiB；
- PostgreSQL FTS + `pg_trgm` 多语言回退；
- current page/local graph/workspace 三种范围；
- Query SSE 和引用验证；
- 用户显式保存回答到 Wiki；
- 增量更新、Revision conflict；
- 确定性 Lint + LLM 辅助 Issue；
- 全局/局部图、筛选、搜索和 Lint 联动；
- Revision 浏览与恢复。

不包括扫描 PDF/OCR、自动写回答、向量数据库。

### 分工

| 角色 | 任务 |
| --- | --- |
| A | Aurora 评测集、Query/Lint Gate、性能基线 |
| B | PDF API、FTS、Query/Lint API、Revision concurrency |
| C | PDF parser、Query Prompt、引用、冲突和 Lint |
| D | 流式问答、引用跳转、图谱筛选、Lint 和版本 UI |

### 闭环

```text
摄取 Aurora A
→ 摄取 Aurora B
→ 更新同一页面并记录延期冲突
→ 查询当前启动日期并获得引用
→ 查询未知预算并拒答
→ Lint 找到孤立页/断链/缺引用
→ 点击 Issue 返回图谱和 Wiki
```

### Gate

- Aurora 固定数据全部通过；
- 引用不可伪造；
- 未知问题拒答；
- Query 结果不自动写 Wiki；
- Graph 1000 节点目标可交互；
- `make verify-mvp2` 全绿。

### 预计

约 5～6 个工作日。

## MVP 3：多用户与空间隔离

### 目标

启用真实身份系统，同时保持 Wiki 引擎无需重写。

### 范围

- 注册、登录、退出、Session 过期；
- Argon2id；
- HttpOnly/Secure/SameSite Cookie 和 CSRF；
- 用户创建多个 Workspace；
- 所有 API、SSE、下载、Graph、Job 按 Workspace 授权；
- 登录和上传限流；
- 前端登录、空间创建/切换和缓存清理。

### 分工

| 角色 | 任务 |
| --- | --- |
| A | 威胁模型、隔离 Gate 和安全 Review |
| B | Auth、Session、Workspace、授权 dependency 和限流 |
| C | Worker 显式传递 workspace/user，不依赖请求全局状态 |
| D | Auth UI、Workspace switch、403/404/过期状态和 E2E |

### 闭环

```text
Alice/Bob 注册
→ 各自创建空间和上传文件
→ 同时摄取和查询
→ 互相请求 Source/Page/Graph/Job/Export
→ 全部 403/404
```

### Gate

- 跨租户矩阵全绿；
- 浏览器切空间无缓存泄漏；
- Session 不进入 localStorage；
- 两用户任务不串数据；
- `make verify-mvp3` 全绿。

### 预计

约 5 个工作日。

## MVP 4：团队协作

### 目标

多个用户按 Owner/Editor/Viewer 共同维护一个 Workspace。

### 范围

- 邀请、接受、过期和取消；
- 成员与角色管理；
- Owner/Editor/Viewer 权限矩阵；
- Wiki 人工编辑、版本、恢复和 409 冲突；
- 审计日志 UI；
- 最后一名 Owner 保护。

不包括实时协同编辑。

### 分工

| 角色 | 任务 |
| --- | --- |
| A | 权限矩阵、审计和 Gate |
| B | Invitation/Membership API、版本冲突和恢复 |
| C | 协作状态下的 Ingest 冲突策略和系统 actor |
| D | 成员、邀请、编辑、版本、冲突处理 UI |

### 闭环

```text
Owner 邀请 Editor/Viewer
→ Editor 摄取和编辑
→ Viewer 只读和查询
→ Viewer 写入被拒绝
→ 两 Editor 冲突返回 409
→ Owner 查看审计并恢复版本
```

### Gate

- 每个 API 权限矩阵通过；
- 最后 Owner 规则通过；
- 冲突不覆盖；
- 邀请 Token 安全且有期限；
- `make verify-mvp4` 全绿。

### 预计

约 4～5 个工作日。

## MVP 5：阿里云 Beta

### 目标

将相同应用部署到老师服务器，完成安全、恢复和运行验证。

### 前置输入

- ECS OS、vCPU、RAM、GPU/显存、磁盘；
- 域名、DNS、安全组权限；
- OSS 使用决策；
- 真实数据重要性与备份要求；
- 模型同机或独立服务决策。

### 范围

- Caddy HTTPS；
- 生产 Secret；
- ECS 数据盘或 OSS；
- 结构化日志和最低监控；
- 数据库/Storage 备份与恢复；
- Staging 部署演练；
- 生产性能、安全和故障注入；
- 视觉统一与必要响应式适配。

### 分工

| 角色 | 任务 |
| --- | --- |
| A | ECS、Caddy、HTTPS、发布、备份恢复、监控 |
| B | 生产迁移、OSS/Data disk、Secret 和恢复验证 |
| C | 云端模型、并发限制、质量/耗时基线 |
| D | 生产 E2E、错误体验、视觉修复和用户文档 |

### 闭环

```text
全新 Staging 服务器部署
→ HTTPS 注册两用户
→ 上传/摄取/图谱/问答/Lint
→ 备份
→ 清空隔离环境
→ 恢复
→ 重跑完整 E2E
→ 切换 Production
```

### Gate

- 只公开 80/443，SSH 限可信 IP；
- 内部数据库/Redis/Ollama 不公网暴露；
- 恢复后哈希、Wiki、引用和图谱一致；
- Worker/Redis/LLM 故障可诊断；
- `make verify-mvp5` 全绿。

### 预计

约 5～7 个工作日，不包含等待服务器和域名权限的时间。

## 里程碑总览

在无外部阻塞、四人有效并行的情况下，MVP 0～2 约 3 周，MVP 3～5 约 3 周。时间只是规划基线；质量 Gate、真实模型速度和服务器条件优先。

## Issue 模板

每个 Issue 至少包含：

```text
目标
非目标
接口/数据依赖
实现范围
验收步骤
自动测试
风险与回滚
负责人
Reviewer
```

## Definition of Done

- 代码、迁移、测试、Mock 和文档同步；
- 无未解释的失败测试；
- 新配置进入 `.env.example`；
- 新 API 进入 OpenAPI 和契约测试；
- 新用户流程有 E2E；
- 数据变更有迁移和回滚/向前修复说明；
- 安全边界经过另一名成员 Review；
- 相关 MVP Gate 仍全部通过。
