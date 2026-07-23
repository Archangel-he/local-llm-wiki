# Karpathy / Obsidian 参考与兼容边界

## 参考对象

本项目参考两类一手资料：

- [Andrej Karpathy 的 LLM Wiki Gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)：定义 Raw、Wiki、Schema 三层，以及 Ingest、Query、Lint、Index、Log 等核心模式；
- [green-dalii/obsidian-llm-wiki](https://github.com/green-dalii/obsidian-llm-wiki)：展示这一模式在 Obsidian 中的产品化实践，包括来源摘要、实体/概念页、别名、增量更新、批量摄取、查询写回和维护工具。

它们是设计参考，不是运行时依赖。`local-llm-wiki` 的目标是多用户 Web 服务，因此不会复制 Obsidian 插件 API 或单机 Vault 的并发模型。

## 总体映射

| 参考模式 | 本项目实现 | 处理方式 |
| --- | --- | --- |
| Raw sources | Storage/OSS 中不可变 Source | 直接沿用 |
| Wiki Markdown | PostgreSQL 中版本化 Markdown | 保留内容形式，改变权威存储 |
| Schema/Agent instructions | 版本化 Schema、Prompt、JSON Schema | 沿用并加强校验 |
| `wiki/sources/` | `source` 类型 Wiki 页面 | 沿用 |
| `wiki/entities/` | `entity` 类型 Wiki 页面 | 沿用 |
| `wiki/concepts/` | `topic` 页面及概念标签 | 适配现有页面类型 |
| `index.md` | 由数据库投影生成的 Index View | 沿用语义 |
| `overview.md` | 由已引用页面生成的 Overview View | 沿用但禁止无来源扩写 |
| `log.md` | `audit_logs` 的只读 Markdown 投影 | 沿用语义 |
| Obsidian Graph View | Sigma.js + Graphology | Web 化替代 |
| 文件历史/Git | `wiki_revisions` + AuditLog | 多用户化替代 |
| Agent 直接写文件 | LLM 变更计划 + 后端事务 | 不照搬 |
| 多模型供应商设置 | Ollama/OpenAI-compatible Model Profile | Web 化并加强密钥隔离 |

## 纳入设计的补充

### 1. 页面别名和实体解析

每个实体/主题页面可以有：

```yaml
aliases:
  - LLM
  - Large Language Model
  - 大语言模型
```

别名参与：

- 标题搜索和 Query 召回；
- 新页面创建前的重复候选检测；
- 跨语言、简称和旧名称解析；
- Obsidian Frontmatter aliases 和 `[[slug|label]]` 导出；
- Lint 的 `missing_alias` 与 `duplicate_page`。

别名不能单独决定自动合并。合并必须比较页面类型、引用、正文和关系，并保留所有历史 Revision。

### 2. Source Summary

每次成功摄取都生成或更新一个 `source` 页面，至少记录：

- 来源标题、类型、上传时间和 Source ID；
- 一段有引用的摘要；
- 提取出的实体、主题和关键事实；
- 本次影响的 Wiki 页面；
- 解析器、Schema、Prompt 和模型版本。

Source Summary 是 Raw 与综合 Wiki 之间的可读桥梁，不替代不可变原文件。

### 3. 系统视图

系统提供三个特殊只读视图：

| 视图 | 内容 | 数据来源 |
| --- | --- | --- |
| Index | 分类页面目录、别名、一句话摘要、来源数 | Wiki Page/Revision/Alias/Citation |
| Overview | 当前空间的有引用总体综述 | 已验证 Wiki 页面 |
| Activity | Ingest、Query、Lint、Schema 和人工编辑时间线 | AuditLog/Job |

在线环境中的 Index/Activity 由 PostgreSQL 投影生成；Overview 是带引用和 Revision 的特殊 Wiki 页面。三者都不会形成另一套需要同步的权威文件。导出 Vault 时分别生成 `index.md`、`overview.md`、`log.md`。

Overview 的更新属于受约束的 Wiki 更新：必须有引用、产生 Revision，并允许用户复核；Index 和 Activity 则完全确定性生成。

### 4. 长文档与批量摄取

长文档不一次塞入模型：

```text
解析并按结构切分
→ 分批提取候选实体/主题/事实
→ 确定性合并候选
→ 与现有标题和 aliases 做实体解析
→ 分页生成结构化操作
→ 全部校验
→ 单次短事务提交
```

批量上传由 Batch 统一跟踪，但每个 Source 有独立 Job、重试和结果。取消在文件或提取批次边界生效；一个文件失败不回滚已经完成的其他文件。

### 5. Query 写回

Query 输出保留 `[[wikilink]]` 风格的页面跳转和 Source 引用。用户选择保存时：

- 先做标题/alias 去重；
- 默认保存为 `analysis` 页面或更新指定页面；
- 重新验证引用；
- 产生独立 Job 和 Revision；
- 不把聊天文本原样当作可信事实。

### 6. Schema 协同演化

Lint 可以提出 Schema Suggestion，例如新增页面模板、标签词表、必填字段或别名规则。建议流程：

```text
检测重复问题
→ 生成结构化 Suggestion 和示例 Diff
→ 用户审阅
→ 接受后创建新 schema_version
→ 只影响后续任务
→ 需要时显式迁移旧页面
```

模型不能自行激活 Schema；MVP 0～2 由默认用户确认，启用多用户后由 Owner 激活，并进入审计日志。Editor 可以提出或审阅建议，但不能单独改变整个 Workspace 的规则。

### 7. 维护顺序

批量维护按因果顺序执行：

```text
补齐 aliases
→ 检测/合并重复页
→ 修复断链
→ 连接孤立页
→ 检查空页和缺引用
→ 检查语义冲突
→ 重建 Index
```

早期 MVP 默认只创建 Issue。自动修复必须由用户选择，并且每个阶段创建可回滚 Revision。

## 明确不照搬

- 不让模型直接写服务器 Wiki 文件；
- 不以文件夹路径承担认证和 Workspace 隔离；
- 不依赖 Obsidian Watcher 触发生产任务；
- 不以 Git 代替数据库并发控制和审计；
- 不自动把 LLM 建议写入 Schema；
- 不因参考项目使用图算法就提前引入 Neo4j 或向量数据库；
- 不把 Obsidian 插件设置、Secret 或缓存格式作为服务端协议；
- 不照搬参考插件的右侧 Query 面板；本项目保留用户已确定的“中间上方图谱、中间下方问答、右侧 Wiki”布局。

## Obsidian 兼容契约

MVP 2 起，完整导出的 Vault 至少满足：

```text
vault/
├── sources/
├── entities/
├── concepts/
├── analyses/
├── questions/
├── assets/
├── index.md
├── overview.md
├── log.md
└── export-manifest.json
```

- 页面使用标准 Markdown；
- Frontmatter 至少包含稳定 ID、title、slug、type、aliases、tags、source IDs、schema version 和更新时间；
- 内部链接使用 `[[slug]]`，显示名不同时使用 `[[slug|label]]`；
- 所有导出文件哈希进入 Manifest；
- 导出结果可直接作为 Obsidian Vault 打开；
- 导出文件修改不会自动回写在线系统。

MVP 1 先交付相同目录、Frontmatter、aliases、`index.md` 和 `log.md`；`overview.md` 在 MVP 2 的增量综合与引用验收完成后加入。

## MVP 放置

| 能力 | 阶段 |
| --- | --- |
| Source Summary、别名、Index、Activity、兼容导出 | MVP 1 |
| 长文档分批、Batch、跨语言去重、Overview、摄取历史 | MVP 2 |
| Schema Suggestion、维护顺序和人工确认 | MVP 2 |
| 多用户 Schema 权限和审计 | MVP 3～4 |
| Obsidian Import/双向同步 | 不在当前 MVP |
