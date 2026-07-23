# ADR-005：Obsidian 兼容而非 Obsidian 依赖

## 状态

Accepted

## 背景

Karpathy 的原始模式和多个实践项目使用 Markdown Vault 与 Obsidian。当前项目需要保留这种可阅读、可链接、可导出的体验，同时支持 Web、多用户权限、后台任务、并发版本和阿里云部署。

## 决策

- 在线权威数据仍为 PostgreSQL 中的 Markdown Revision；
- 实现明确的 Obsidian Markdown/Frontmatter/`[[wikilink]]` 导出契约；
- Index、Overview、Activity 在线表现为数据库投影或版本化页面；
- 前端自行实现文件树、图谱、问答和 Wiki 阅读；
- 不依赖 Obsidian 插件 API、Vault Watcher 或 Git 作为运行时组件；
- 当前 MVP 只支持单向导出，不支持双向同步。

## 结果

优点：

- 保留 Karpathy 模式的可移植性；
- 用户可用 Obsidian 检查和浏览导出结果；
- 不牺牲多用户事务、权限和审计；
- 未来可在稳定契约上实现显式 Import。

代价：

- 需要维护导出兼容测试；
- 在线数据和导出文件不能双向实时同步；
- Obsidian 社区插件功能不能直接复用。

## 替换条件

只有用户验证证明双向编辑是核心需求，并且冲突、权限、附件和删除语义已经设计清楚后，才评估 Import 或同步协议。
