# 测试与验收设计

## 原则

- 每个 MVP 都有独立、可重复的退出命令；
- LLM 随机输出不做全文快照；
- 业务规则使用 Mock LLM 确定性验证；
- 真实模型只验证结构、事实、引用和拒答；
- 权限隔离、数据一致性和恢复优先于 UI 美观；
- 失败必须留下可诊断的 request/job ID。

## 测试层级

### Unit

- 文件类型、大小、哈希和路径规范化；
- Wiki Link 与 Citation 解析；
- aliases 规范化、冲突和实体解析；
- 长文档 batch 合并与上限；
- Index/Activity 确定性投影；
- JSON Schema 验证；
- 权限矩阵；
- Job 状态转换；
- Lint 规则；
- Graph 节点和边转换。

### Integration

- FastAPI + PostgreSQL；
- RQ enqueue + Worker；
- Local Storage adapter；
- Wiki 变更事务；
- FTS + `pg_trgm` 中文/英文检索；
- title/slug/alias 多语言召回；
- SSE 事件顺序；
- Alembic 从空库升级。

### E2E

- 浏览器上传、任务进度、图谱、Wiki、问答和引用；
- 注册、登录、Workspace 切换；
- Owner/Editor/Viewer；
- 备份恢复后的完整闭环。

### Real-model smoke

- Ollama 健康；
- Ingest 输出通过 Schema；
- 已知问题带正确引用；
- 未知问题拒答；
- 冲突来源不被静默覆盖。

## 固定测试数据集

### Aurora A

```text
Project Aurora 于 2025-03-01 启动，项目负责人是 Lin。
```

### Aurora B

```text
Project Aurora 原计划于 2025-03-01 启动，之后推迟到 2025-04-15。
```

### 已知问题

```text
Aurora 当前计划什么时候启动？
```

期望包含 `2025-04-15` 和有效引用。

### 未知问题

```text
Aurora 的预算是多少？
```

期望说明当前资料无法确定，不出现具体预算。

### Graph fixture

```text
A [[B]]
B [[C]]
D 没有链接
```

期望：4 节点、2 条 wikilink 边、D 为 orphan。

### Tenant fixture

```text
Alice / Workspace A / private-a.md
Bob   / Workspace B / private-b.md
```

双方互相访问 Source、Page、Graph、Job、Export 均返回 403/404。

### Alias/duplicate fixture

```text
Large Language Model
aliases: LLM, 大语言模型

第二份来源只使用“LLM”
```

期望更新同一页面，不创建第二个实体；alias 冲突时只生成候选或 Lint Issue，不自动误合并。

### Long document fixture

生成超过单批阈值的固定 Markdown，关键事实分别位于开头、中部和结尾。期望分批提取后都进入同一事务；任一批无效时 Wiki 不出现中间结果。

## MVP 验收命令

计划提供：

```bash
make verify-mvp0
make verify-mvp1
make verify-mvp2
make verify-mvp3
make verify-mvp4
make verify-mvp5

make test-unit
make test-integration
make test-e2e
make test-ollama
```

CI 默认不要求真实 Ollama；`test-ollama` 在指定 Mac Studio/模型服务器运行。

## MVP 0 Gate

- `docker compose up --build` 成功；
- Health 除 LLM 外全部 ok，LLM 不可用时为 degraded；
- 空库迁移成功且可重复；
- 默认用户/空间只创建一次；
- 重启后数据存在；
- Mock 三栏 UI 和四节点图可交互。

## MVP 1 Gate

- Markdown/TXT 上传返回 202；
- 原始 SHA-256 与下载内容一致；
- 同文件重复上传不重复保存；
- Job 状态和 SSE 完整；
- 模型失败最多执行 3 次（首次 + 2 次重试）；
- Wiki 事务要么全部提交，要么完全回滚；
- Source Summary、aliases、Index 和 Activity 正确；
- 文件树、图谱和 Wiki 联动通过；
- 导出的类型目录、Frontmatter、aliases、Index/Log 可被 Obsidian 打开。

## MVP 2 Gate

- 文本型 PDF 可摄取；
- Aurora A+B 更新同一页面；
- 使用 “Aurora Project/极光项目” alias 仍定位同一页面；
- 长文档分批不会漏掉首尾固定事实；
- Batch 中单文件失败不回滚其他 Source；
- 已知问题正确并带有效引用；
- 未知问题拒答；
- FTS、当前页和局部图三种范围可用；
- Lint 检出 broken link、orphan、missing citation；
- Query 引用可跳转 Wiki/Raw；
- 保存回答会创建独立 Job，不自动写回；
- Schema Suggestion 未经确认不会改变 active schema；
- 完整 Vault 的 Overview 有引用且可由 Obsidian 打开。

## MVP 3 Gate

- 注册、登录、退出和 Session 过期；
- 跨空间所有读取和写入均被拒绝；
- 两用户并发上传不串任务；
- 切换 Workspace 清空前端缓存；
- 登录失败和上传限流生效；
- 密码库中不存在明文密码。

## MVP 4 Gate

- 邀请、接受、退出闭环；
- Owner/Editor/Viewer 权限矩阵完整；
- 最后一名 Owner 不能直接退出；
- 两个 Editor 同时更新触发 409，不静默覆盖；
- Revision 浏览与恢复产生新 Revision；
- 审计日志包含成员和页面操作。

## MVP 5 Gate

- 全新 ECS 可按照文档部署；
- 只有 80/443 公网开放，22 限制可信 IP；
- HTTPS 和安全 Cookie 生效；
- 执行备份、清空测试环境、恢复后 E2E 通过；
- 容器重启和 Worker 中断后任务可恢复；
- 日志可按 request_id/job_id 查询；
- 模型不可用时 Wiki 仍可浏览。

## 性能门槛

以项目指定 Mac Studio 和测试浏览器为参考：

- Health/普通元数据 API：本地 p95 < 200ms；
- 上传接口在文件保存后 1s 内返回 Job（不包含模型时间）；
- 1000 节点/3000 边图首次可交互目标 < 3s；
- 图谱拖动和问答输入无持续主线程阻塞；
- 20 个并发非 LLM 用户请求错误率 < 1%；
- 连续提交 10 个 Ingest Job 不丢失、不重复提交 Wiki；
- 模型吞吐和首 Token 时间只记录基线，不在未知硬件上预设硬指标。

若目标未达到，测试输出硬件、模型、数据量和具体阶段，避免无上下文性能数字。

## 故障注入

至少覆盖：

- Ollama 请求超时；
- Worker 在模型返回前退出；
- Worker 在数据库提交前退出；
- Redis 重启；
- PostgreSQL 暂时不可用；
- Storage 写入失败；
- SSE 中途断线；
- LLM 返回非法 JSON、无效引用或跨 Workspace ID。

通过标准：Raw 不损坏、Wiki 不出现半提交、Job 可诊断且可重试。

## 安全测试

- IDOR/跨 Workspace 资源访问；
- Cookie 属性和 CSRF；
- 文件名路径穿越；
- MIME 欺骗和超大上传；
- Markdown XSS；
- SSE 权限复用；
- 导出下载权限；
- Prompt 中的 Source 内容不能覆盖系统 Schema 指令。

## 测试数据管理

- Fixtures 进入 `tests/fixtures/`；
- 不提交真实私人资料；
- E2E 每次创建独立 Workspace 并清理；
- 测试哈希和预期结构固定；
- Real-model 结果保存摘要指标，不保存敏感 Prompt 内容。
