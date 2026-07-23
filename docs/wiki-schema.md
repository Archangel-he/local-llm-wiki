# Wiki Schema 与模型写入协议

## 原则

- 模型不直接写数据库或文件；
- 模型只返回符合 JSON Schema 的变更计划；
- 后端验证页面、链接、引用和版本后再提交；
- 每个事实尽量有 Source 级引用；
- 新来源不能静默覆盖旧结论；
- 模型生成内容默认可追溯、可回滚、可 Lint。

## 页面类型

| 类型 | 用途 |
| --- | --- |
| `topic` | 主题综述与持续综合 |
| `entity` | 人物、组织、项目、地点等实体 |
| `source` | 单份来源的结构化摘要 |
| `analysis` | 经用户确认保存的比较或分析 |
| `question` | 未解决问题和知识缺口 |

为兼容 Obsidian 导出，`topic` 可使用 `concept` 标签并导出到 `concepts/`；不为目录新增一套重复的在线类型系统。

## 在线页面表示

PostgreSQL 保存：

- `wiki_pages`：稳定 ID、slug、标题、类型和状态；
- `wiki_revisions`：Markdown 正文、结构化 Frontmatter 和版本信息；
- `wiki_links`：页面关系；
- `citations`：Revision 到 Raw Source 的证据关系。

Markdown 正文不依赖数据库专用语法。导出时生成 YAML Frontmatter：

```yaml
---
id: 8c7729bb-1a96-4b64-8535-7eb0b4046bcc
title: Project Aurora
slug: project-aurora
type: topic
status: active
aliases:
  - Aurora Project
  - 极光项目
tags:
  - project
source_ids:
  - 0bbd8ab7-a755-4210-ae2a-914f41f14462
schema_version: 1
updated_at: 2026-07-23T08:00:00Z
---
```

## 页面正文约定

推荐结构：

```markdown
# Project Aurora

## Overview

Project Aurora 当前计划于 2025-04-15 启动。[source:SOURCE_ID#section]

## Key facts

- 负责人：[[lin]]。[source:SOURCE_ID#paragraph-3]
- 原计划日期：2025-03-01。[source:OLD_SOURCE_ID#paragraph-1]

## Relationships

- 负责人：[[lin]]

## Conflicts and open questions

- 较早来源记录 2025-03-01，新来源说明已延期到 2025-04-15。

## Sources

- [SOURCE_ID] Aurora project note
```

约定：

- 一级标题等于页面标题；
- entity/topic 页面应提供有意义的 alias；没有自然别名时允许暂缺并由 Lint 提醒，不得为了满足数量制造同义词；
- Wiki Link 使用 `[[slug]]`；
- Source 引用使用后端可解析的稳定 Source ID；
- 引用 locator 使用页码、标题、段落或时间码；
- 不允许使用不存在的 Source ID；
- 不允许将未验证的模型常识伪装成来源事实。

## 页面模板

### Source Summary

每个成功摄取的 Source 对应一个 `source` 页面：

```markdown
# Aurora Project Note

## Summary

带引用的一段摘要。

## Extracted pages

- [[project-aurora]]
- [[lin]]

## Ingest metadata

- Source ID
- Parser/Schema/Prompt/Model version
- Ingest Job ID
```

### Entity / Topic

实体和主题页至少包含 Overview、Key facts、Relationships、Conflicts/Open questions、Sources；空章节可以省略，不能生成没有内容的占位页。

### 系统视图

- Index：按 source/entity/concept/analysis/question 分类，展示 alias、一句话摘要和来源数，确定性生成；
- Overview：基于已有引用页面生成整体综述，属于版本化 Wiki 内容；
- Activity：由 Job/AuditLog 确定性生成，不接受模型直接修改。

## Schema 版本

Schema、Prompt 和解析器均独立版本化：

```text
schema_version
prompt_version
parser_version
```

任何版本变化都进入 Ingest 幂等键。升级 Schema 不自动重写全部 Wiki，必须运行显式迁移或重新摄取任务。

Schema 可以由用户直接编辑，也可以由 Lint 生成结构化 Suggestion。Suggestion 必须展示 Diff、影响范围和迁移要求；MVP 0～2 由默认用户确认，MVP 3 起只有 Owner 可以激活新 `schema_version`。模型不能自行激活。

项目中的 Schema 模板计划放置于：

```text
backend/wiki/schema/
├── AGENTS.md
├── ingest.schema.json
├── query.schema.json
└── lint.schema.json
```

## Ingest 输入

Worker 向模型提供：

```text
Workspace Schema
Source 元数据
解析后的来源文本
相关现有 Wiki 页面及 revision_no
允许执行的操作列表
引用与链接规则
```

模型不获得数据库密码、Storage 凭据或任意文件写权限。

### 长文档分批

当解析文本超过模型输入或任务配置阈值时：

1. 按标题、段落和页码切成可定位批次；
2. 每批只提取候选事实、实体、主题、alias 和引用 locator；
3. 后端确定性合并候选并与现有标题/alias 匹配；
4. 模型对合并结果生成最终页面操作；
5. 所有操作完整验证后再进入一次 Wiki 提交事务。

中间批次结果是临时数据，不可被 Query 当作已发布 Wiki。

## Ingest 输出

简化示例：

```json
{
  "schema_version": 1,
  "source_id": "SOURCE_ID",
  "operations": [
    {
      "action": "update_page",
      "page_id": "PAGE_ID",
      "expected_revision_no": 3,
      "title": "Project Aurora",
      "slug": "project-aurora",
      "page_type": "topic",
      "aliases": ["Aurora Project", "极光项目"],
      "markdown": "# Project Aurora\n...",
      "change_summary": "Add postponed launch date",
      "links": [
        {
          "target_slug": "lin",
          "type": "wikilink"
        }
      ],
      "citations": [
        {
          "source_id": "SOURCE_ID",
          "locator": "paragraph-2",
          "excerpt": "..."
        }
      ],
      "conflicts": [
        {
          "claim": "Launch date",
          "existing_value": "2025-03-01",
          "new_value": "2025-04-15",
          "resolution": "newer_source_supersedes"
        }
      ]
    }
  ]
}
```

允许操作：

```text
create_page
update_page
mark_page_for_review
create_open_question
```

不允许模型直接删除 Page、Source 或历史 Revision。

## 后端验证顺序

1. JSON 可以解析且通过 Schema；
2. `schema_version` 与 Workspace 一致；
3. Source 属于当前 Workspace；
4. Page ID、slug 和 expected revision 合法；
5. 引用 Source ID 全部存在；
6. Markdown 中引用与结构化 citations 一致；
7. 推断关系具有 evidence；
8. aliases 规范化后不与其他页面冲突；
9. 新建页已经过 title/slug/alias 重复候选检查；
10. 单任务修改数量不超过配置上限；
11. 通过后在一个数据库事务中应用。

验证失败：

- 不应用任何 Wiki 修改；
- Job 记录 `SCHEMA_VALIDATION_FAILED`；
- 可使用纠错 Prompt 重试，最多计入总重试次数；
- 最终失败时保留 Raw 和错误摘要供用户重试。

## 冲突处理

新来源与旧页面冲突时，不得直接删除旧事实。必须记录：

- 旧值和支持来源；
- 新值和支持来源；
- 来源时间或可信度；
- 当前采用的解释；
- 是否需要用户复核。

无法自动判断时：

```text
page.status = needs_review
```

并创建 `contradicts` 关系或 `question` 页面。

## Query 约束

查询范围：

```text
current_page
local_graph
workspace
```

MVP 2 检索流程：

1. PostgreSQL FTS 检索适合分词的文本，`pg_trgm` 为中文等多语言文本、短语和模糊匹配提供回退；
2. 标题、slug 和 aliases 提供低成本精确/模糊召回；
3. `local_graph` 范围可扩展一至三层显式邻居；
4. 对候选页面按文本相关性、更新时间和链接关系排序；
5. 将候选 Markdown 和 Source 元数据发送给模型；
6. 模型返回回答片段和结构化引用；
7. 后端只接受本次候选集合中的引用 ID。

具体排序权重必须由固定中文/英文 Fixtures 评测，不在实现前假设某一种分词配置足够。

如果证据不足，回答必须明确包含“当前资料无法确定”，不能补充未引用的具体事实。

Query 回答不会自动写入 Wiki。用户点击“保存到 Wiki”后，创建独立 Job，并再次通过结构化写入协议。

## Lint 规则

确定性规则优先于 LLM：

- `broken_link`：目标 slug 不存在；
- `orphan_page`：无入链且不是 index/source 页面；
- `missing_citation`：事实段落无 Source 引用；
- `invalid_citation`：Source 不存在或跨 Workspace；
- `duplicate_slug`：slug 冲突；
- `missing_alias`：需要别名的页面没有有效 alias；
- `duplicate_page`：标题、alias、内容和引用显示页面可能重复；
- `empty_page`：页面只有标题或模板占位；
- `stale_page`：超过配置时间未更新且相关 Source 有新版本。

LLM 辅助规则：

- `semantic_conflict`：不同页面陈述可能冲突；
- `missing_concept`：高频概念没有独立页面；
- `weak_synthesis`：页面只是来源堆叠，没有形成综合。

LLM Lint 结果只创建 Issue，不直接修改 Wiki。

用户选择批量修复时按 `alias → duplicate → broken link → orphan → empty/missing citation → semantic conflict` 执行，每个阶段重新扫描并产生独立 Revision。

## 导出到 Obsidian

- Page 类型到目录的固定映射为 `source → sources/`、`entity → entities/`、`topic → concepts/`、`analysis → analyses/`、`question → questions/`；
- 稳定 ID 写入 YAML Frontmatter；
- aliases 写入 YAML Frontmatter；
- 内部链接导出为 `[[slug]]` 或 `[[slug|label]]`；
- `index.md`、`overview.md` 和 `log.md` 在导出时生成；
- Source 默认只导出元数据，用户可选择包含原始文件；
- 导出包含 Manifest 和文件哈希。

## 验收示例

来源 A：

```text
Project Aurora 于 2025-03-01 启动，负责人是 Lin。
```

来源 B：

```text
Project Aurora 原计划于 2025-03-01 启动，之后推迟到 2025-04-15。
```

通过标准：

- 只保留一个 Aurora 主题页；
- 页面记录新旧日期和两份来源；
- `[[lin]]` 生成稳定 Wiki Link；
- Aurora/Lin 的 aliases 可用于检索且不会制造重复页面；
- 页面状态与冲突信息一致；
- 查询预算时拒绝编造；
- 导出的 Markdown 可被 Obsidian 打开。
