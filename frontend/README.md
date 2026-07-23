# Frontend

MVP 0 的桌面优先 Mock 工作区，界面采用 Obsidian 浅色桌面布局，使用
React、Vite、TypeScript、Sigma.js 和 Graphology。

## 本地开发

```bash
corepack pnpm install
corepack pnpm dev
```

默认地址为 `http://localhost:5173`。开发服务器将 `/api` 代理到
`VITE_API_PROXY_TARGET`，未设置时使用 `http://localhost:8000`。

若 API 尚未实现，Health 会安全回退到 Mock degraded 状态；其他 MVP 0
业务数据始终来自 `src/fixtures/workspace.ts`。

## 环境变量

```text
VITE_API_BASE_URL=
VITE_API_PROXY_TARGET=http://localhost:8000
VITE_USE_MOCK_HEALTH=false
```

- `VITE_API_BASE_URL`：浏览器请求使用的 API 前缀，默认同源。
- `VITE_API_PROXY_TARGET`：Vite 开发代理目标。
- `VITE_USE_MOCK_HEALTH=true`：跳过真实 Health 请求，供 E2E 使用。

任何数据库、Ollama 或外部模型凭据都不得放入 `VITE_*` 变量。

## 验证

```bash
corepack pnpm lint
corepack pnpm test
corepack pnpm build
corepack pnpm exec playwright install chromium
corepack pnpm test:e2e
```

生产构建输出到 `frontend/dist/`，供 Caddy 或其他静态服务器托管。

## MVP 0 边界

- 文件树、Wiki、问答、Model Profile 和图数据均为确定性 fixtures。
- Health 具有独立数据层，可接入 `GET /api/health`。
- API Key 仅写入；保存后立即清空输入值，界面只显示已配置状态。
- MVP 0 不实现上传、SSE、真实问答、认证、Workspace 切换或 Wiki 编辑。

## 图谱交互

- 图谱由 Sigma.js 的 WebGL 画布渲染。
- 入场、Hover、节点拖动回弹和选中脉冲共用一个
  `requestAnimationFrame` 弹簧调度器；动画帧不触发 React 重渲染。
- 缩放、平移、节点拖动、邻居高亮、选中聚焦、全局/局部视图和布局重播
  均可操作。
- 系统开启“减少动态效果”时，图谱会直接落到目标状态。

## 与其他角色的联调依赖

- A：将 `pnpm build` 和 `frontend/dist/` 接入 Docker Compose、Caddy、CI、
  `make test-e2e` 与 `make verify-mvp0`。
- B：实现并稳定 `GET /api/health` 响应契约；前端已经通过独立数据层调用该接口。
- C：确认默认 Ollama Profile、Provider 状态和 degraded 语义；MVP 0 页面不调用真实模型。
