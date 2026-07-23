# ADR-001：Wiki 在线权威数据

- 状态：Accepted
- 日期：2026-07-23

## 背景

Karpathy 的构想以 Markdown 文件为 Wiki，但本项目目标是多用户网站，需要权限、版本、并发更新、事务和云端部署。README 早期同时提到 PostgreSQL Wiki 表和 `workspace/wiki/`，存在双重事实来源歧义。

## 决策

- PostgreSQL 保存 Wiki Markdown 正文、结构化元数据和历史版本，是在线权威数据；
- Storage 保存不可变 Raw、附件和导出文件；
- 系统按需导出 Obsidian-compatible Markdown Vault；
- 导出文件不是双向同步目录；未来 Import 必须是显式、可审计流程。

## 后果

优点：

- Wiki 更新可以和链接、引用、审计一起事务提交；
- 易于实现版本、权限、并发冲突和多实例部署；
- Markdown 仍保持可读、可导出和工具无关。

代价：

- 不能直接在服务器目录用 Obsidian 修改在线 Wiki；
- 需要实现 Export；
- 若未来需要双向同步，必须设计冲突协议。

## 备选

Markdown 文件权威、PostgreSQL 仅索引。更接近本地 Vault，但多人并发、云端共享磁盘和原子更新更复杂，因此不选。
