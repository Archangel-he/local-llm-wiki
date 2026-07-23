# ADR-004：PostgreSQL 保存图关系，Sigma.js 渲染

- 状态：Accepted for MVP
- 日期：2026-07-23

## 背景

前端需要类似 Obsidian 的全局图和局部图。早期图主要来自 Wiki Link、Citation 和 Derived-from，不需要复杂图查询语言。

## 决策

- PostgreSQL `wiki_links` 保存稳定节点关系；
- Page ID 是节点 ID，Link ID 是边 ID；
- FastAPI 返回 Graph JSON；
- Sigma.js + Graphology 渲染和处理前端交互；
- ForceAtlas2 在 Web Worker 中计算布局；
- 模型推断边必须有 evidence。

## 后果

优点：

- 图关系与 Wiki Revision、权限和事务保持一致；
- 无需引入 Neo4j 运维成本；
- 可直接按 `workspace_id` 隔离。

代价：

- 极复杂多跳查询不如专用图数据库；
- 大图需要分页、局部图或服务端裁剪。

## 替换条件

只有当固定基准证明 PostgreSQL 无法满足目标图规模或查询延迟时，才评估专用图数据库。前端渲染接口保持不变。
