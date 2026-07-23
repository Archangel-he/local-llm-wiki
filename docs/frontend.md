# 前端产品与交互设计

## 设计目标

- 保留 Obsidian 的文件浏览、双向链接和关系图探索体验；
- 将问答、引用和 Wiki 阅读放在同一个工作区；
- 先验证信息流，后统一视觉精修；
- 桌面优先，移动端不属于早期 MVP；
- 所有数据按当前 Workspace 切换和隔离。

## 主布局

顶部区域预留，MVP 0 不锁定最终内容。

参考 Obsidian Command Palette 后，顶部的候选职责为 Workspace 切换、全局搜索/命令入口、当前 Job 状态、当前模型和用户菜单；这只是功能预留，不在 MVP 0 锁定视觉布局。文件、图谱、问答和 Wiki 的主工作区位置不变。

```text
┌──────────────────────────────────────────────────────────────────────┐
│                              顶部区域（待定）                         │
├──────────────┬─────────────────────────────┬─────────────────────────┤
│ 文件管理      │ 关系图谱                     │ Wiki 条目                │
│              │                             │                         │
│ ▾ Raw        │ [全局图] [局部图] [筛选]     │ 页面标题                  │
│ ▾ Wiki       │                             │ Markdown 正文             │
│ ▾ Lint       │                             │ 来源与引用                 │
│ ▾ Recent     ├─────────────────────────────┤ 双向链接                   │
│              │ 问答区                       │ 版本记录                   │
│              │ [当前条目][局部图][全空间]   │                         │
└──────────────┴─────────────────────────────┴─────────────────────────┘
```

默认尺寸：

- 左侧 240～280px；
- 中间/右侧约 60% / 40%；
- 图谱/问答约 65% / 35%；
- 分隔线可拖动；
- 图谱、问答、Wiki 均可最大化；
- MVP 3 起按用户保存布局偏好。

## 左侧文件管理

展示逻辑资源，不暴露服务器物理路径：

```text
Raw Sources
Wiki
  Sources
  Entities
  Concepts
  Analyses
  Questions
  Index
  Overview
Lint Issues
Recent
Favorites
Trash
```

行为：

- Raw 默认只读；
- Wiki 按目录、类型或标签查看；
- Lint Issue 可定位页面和图谱节点；
- Trash 表示归档，不代表立即物理删除；
- 上传显示校验、排队、处理和失败状态；
- Batch 展示每个文件的 queued/running/skipped/completed/failed/cancelled；
- Recent 展示由 Job/AuditLog 生成的摄取、查询、Lint 和编辑历史。

## 中间关系图谱

技术：

```text
Sigma.js + Graphology + ForceAtlas2 + Web Worker
```

第一版交互：

- 平移、缩放、拖动；
- Hover 突出邻居；
- 点击节点打开右侧 Wiki；
- 点击边显示关系类型与证据；
- 全局图/局部图切换；
- 搜索并聚焦节点；
- 标题、slug 和 aliases 都能定位同一节点；
- 按页面类型、关系类型和状态筛选。

视觉语义：

| 属性 | 表示 |
| --- | --- |
| 节点颜色 | topic/entity/source/question 等类型 |
| 节点大小 | degree 或可配置重要度 |
| 节点描边 | needs_review、Lint、最近更新 |
| 边样式 | wikilink/citation/derived_from/contradicts |
| 虚线边 | 模型推断且有证据的关系 |

图布局初始化后保持稳定；折叠问答或调整面板尺寸不能重新随机化节点。

## 中间问答区

范围选择：

```text
当前条目
局部图谱（depth 1～3）
整个知识空间
```

交互：

- SSE 显示流式回答；
- 引用以稳定 ID 返回，不解析模型随意生成的 URL；
- 点击引用打开右侧 Wiki/Raw，并在图谱定位；
- 证据不足时显示明确警告；
- “保存到 Wiki”是显式按钮，并创建独立 Job；
- 用户可停止前端显示，但服务端取消需调用 Job Cancel API；
- Query 输入区提供 Model Profile 选择器，默认显示个人默认或 Workspace 默认；
- personal Profile 只对本人显示，“保存到 Wiki”时明确提示将改用 Workspace 写入 Profile。

## 模型设置

设置页提供两种首批选项：

```text
Mac / Server Ollama
Custom OpenAI-compatible API
```

Ollama 表单：

- 使用服务端提供的本机 Ollama 预设；
- 输入或选择 Model ID；
- 显示连接状态、最近测试时间和延迟；
- Local 环境允许高级用户填写受策略允许的 Ollama 地址；
- 云端页面明确说明“你的 Mac localhost 不可被服务器直接访问”，不展示会误导用户的本机自动发现按钮。

自定义 API 表单：

- Profile 名称；
- Base URL；
- Model ID；
- API Key（仅写入，保存后显示“已配置”，不显示原值）；
- “测试连接”按钮；
- 外部数据传输提示和确认。

连接测试至少显示：

```text
可连接 / 认证失败 / Model 不存在 / Endpoint 被策略阻止 / 超时
streaming 能力
structured output 适配状态
脱敏后的响应耗时
```

MVP 0～2 的默认用户可以把任一已测试 Profile 设为 Workspace 写入默认值。MVP 3 起：

- 每个用户可以管理自己的 personal Query Profile；
- Owner 可以管理 Workspace Profile 和默认写入模型；
- Editor/Viewer 只能查看 Workspace Profile 的名称、Provider、Model 和状态；
- 任何角色都无法读取已保存 API Key。

## 右侧 Wiki 条目

顺序：

```text
标题 / 类型 / 状态
Aliases / 标签 / 一句话摘要
Markdown 正文
来源与引用
双向链接
版本记录
```

动作：

- 在图谱定位；
- 打开原始来源；
- 复制 Wiki Link；
- 查看/恢复历史版本；
- 进入全屏阅读或编辑；
- Editor 保存时提交 `expected_revision_no`；
- Source Summary 展示本次影响页面和 Ingest 版本信息；
- Index/Overview/Activity 使用只读系统视图样式。

Viewer 不显示编辑和维护操作。

## 面板联动

### Raw → Graph/Wiki

点击 Raw：

- 右侧显示只读预览；
- 图谱突出由该 Source 支持的 Wiki 页面；
- 可以发起或重试 Ingest。

### Wiki → Graph

点击 Wiki：

- 右侧打开条目；
- 图谱聚焦节点；
- 局部图默认显示一层邻居；
- 问答范围自动切换为当前条目，但不自动发送请求。

### Graph → Wiki

点击节点打开页面；点击边展示 evidence。断链边打开对应 Lint Issue。

### Query → Wiki/Graph

点击引用：

- 打开对应 Revision 或 Raw locator；
- 图谱定位相关 Page；
- 返回问答时保留滚动位置和回答状态。

## 前端状态

建议按领域拆分：

```text
session
workspace
tree
jobs
wiki
graph
query
layout
notifications
schema
modelProfiles
```

URL 保存可分享的非敏感视图状态：

```text
/w/{workspace_id}/wiki/{page_id}
/w/{workspace_id}/graph?center={page_id}&depth=1
```

权限变化或 Workspace 切换时，必须清空上一空间的 tree、graph、wiki 和 query cache，防止界面短暂泄漏旧数据。

## 空状态与错误状态

必须设计：

- 无资料：引导上传第一个文件；
- Ollama 不可用：仍可浏览现有 Wiki；
- Model Profile 未配置、认证失败、配额不足或 Endpoint 被阻止；
- Job 失败：展示安全错误摘要与重试；
- 无引用回答：标记为未充分支撑；
- 无权限：不展示资源细节；
- 图谱过大：提示筛选或切换局部图；
- SSE 断线：重新读取 Job/Query 最终状态。

## 开发节奏

### MVP 0

- Vite + TypeScript；
- 三栏与上下分割；
- Mock 文件树、四节点图、问答和 Wiki；
- 健康状态；
- Model Profile 设置 Mock 和当前模型状态；
- 基础可访问性和 E2E selector。

不做主题和动画。

### MVP 1

- 上传 Markdown/TXT；
- 实际文件树和 Job 状态；
- Markdown 渲染；
- wikilink/citation/derived_from 图谱；
- 点击节点打开 Wiki；
- Source Summary、aliases、Index 和 Activity；
- Obsidian 兼容导出预览；
- 实际 Ollama/OpenAI-compatible Profile 创建、连接测试和默认选择。

### MVP 2

- PDF 状态；
- 流式问答和引用；
- 全局/局部图、筛选、搜索；
- Lint 与图谱联动；
- Wiki 版本浏览；
- 多文件 Batch 队列和摄取历史；
- alias/跨语言去重提示；
- Schema Suggestion Diff 与确认；
- Index、Overview 和 Activity 导航；
- Query 按 Profile 选择并展示本次回答使用的 Provider/Model。

### MVP 3

- 登录和退出；
- Workspace 创建与切换；
- 认证过期、无权限和隔离状态；
- 保存布局偏好；
- personal/workspace Profile 权限和切换。

### MVP 4

- 邀请、成员和角色；
- Editor 编辑与 revision conflict；
- Owner 成员管理；
- Viewer 只读视图；
- Owner 的 Workspace 模型策略和凭据替换 UI。

### MVP 5

- 统一视觉、主题和错误体验；
- 生产环境 E2E；
- 基础响应式适配；
- 性能和可访问性修复。

## 可以延后的内容

- 移动端完整三栏重构；
- 插件系统；
- Obsidian Canvas；
- 高级社区聚类和时间动画；
- 自定义快捷键；
- 多套布局预设；
- 实时多人协同编辑。

## 前端验收

- 文件、图谱、问答和 Wiki 可以完成完整跳转闭环；
- 浏览器刷新后 URL 对应页面可恢复；
- 切换 Workspace 后不残留上一空间数据；
- 500～1000 节点固定图可交互；
- ForceAtlas2 不阻塞输入；
- 键盘可以访问主要操作；
- Viewer 无法通过隐藏按钮之外的 API 绕过权限。
