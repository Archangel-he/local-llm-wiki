import type {
  GraphEdge,
  GraphNode,
  HealthSnapshot,
  TreeSection,
  WikiPage,
} from "../types";

export const defaultWorkspace = {
  id: "default-workspace",
  name: "Local LLM Wiki",
};

export const defaultUser = {
  id: "default-user",
  displayName: "Default User",
};

export const wikiPages: WikiPage[] = [
  {
    id: "page-a",
    title: "Project Aurora",
    type: "source",
    status: "current",
    aliases: ["Aurora A"],
    tags: ["project", "source"],
    summary: "Project Aurora 的第一份来源记录。",
    body: [
      "Project Aurora 于 2025-03-01 启动，项目负责人是 Lin。",
      "这是 MVP 0 使用的固定 Mock 内容，用于验证工作区、图谱与 Wiki 页面之间的联动。",
    ],
    sources: ["aurora-a.md · lines 1–3"],
    backlinks: ["Lin"],
    revision: 1,
  },
  {
    id: "page-b",
    title: "Lin",
    type: "entity",
    status: "current",
    aliases: ["Project Lead"],
    tags: ["person", "entity"],
    summary: "Project Aurora 的项目负责人。",
    body: [
      "Lin 负责 Project Aurora。",
      "该页面由 Aurora A 来源中的实体关系派生。",
    ],
    sources: ["aurora-a.md · lines 1–3"],
    backlinks: ["Project Aurora", "Knowledge Graph"],
    revision: 1,
  },
  {
    id: "page-c",
    title: "Knowledge Graph",
    type: "concept",
    status: "needs_review",
    aliases: ["Graph"],
    tags: ["concept", "graph"],
    summary: "用于连接 Wiki 页面与证据的关系视图。",
    body: [
      "知识图谱展示页面之间的 wikilink、citation 与 derived_from 关系。",
      "MVP 0 使用四个固定节点验证基本交互与渲染性能。",
    ],
    sources: ["product-notes.md · lines 8–12"],
    backlinks: ["Lin"],
    revision: 2,
  },
  {
    id: "page-d",
    title: "Orphan Note",
    type: "question",
    status: "needs_review",
    aliases: [],
    tags: ["orphan", "lint"],
    summary: "尚未与其他页面建立链接的孤立条目。",
    body: [
      "该页面没有入边或出边。",
      "它用于验证图谱能否清晰呈现孤立节点。",
    ],
    sources: ["manual-note.md · lines 1–4"],
    backlinks: [],
    revision: 1,
  },
];

export const graphNodes: GraphNode[] = [
  {
    id: "node-a",
    label: "Project Aurora",
    pageId: "page-a",
    type: "source",
    x: -1.05,
    y: 0.28,
    size: 10,
  },
  {
    id: "node-b",
    label: "Lin",
    pageId: "page-b",
    type: "entity",
    x: -0.05,
    y: 0.72,
    size: 8,
  },
  {
    id: "node-c",
    label: "Knowledge Graph",
    pageId: "page-c",
    type: "concept",
    x: 0.92,
    y: -0.08,
    size: 9,
  },
  {
    id: "node-d",
    label: "Orphan Note",
    pageId: "page-d",
    type: "question",
    x: -0.64,
    y: -0.92,
    size: 6,
  },
];

export const graphEdges: GraphEdge[] = [
  {
    id: "edge-a-b",
    source: "node-a",
    target: "node-b",
    type: "wikilink",
    evidence: "Project Aurora 的负责人是 Lin。",
  },
  {
    id: "edge-b-c",
    source: "node-b",
    target: "node-c",
    type: "wikilink",
    evidence: "Lin 页面链接到 Knowledge Graph 概念。",
  },
];

export const treeSections: TreeSection[] = [
  {
    id: "raw",
    label: "Raw Sources",
    icon: "folder",
    children: [
      {
        id: "raw-a",
        label: "aurora-a.md",
        pageId: "page-a",
        kind: "file",
      },
      {
        id: "raw-notes",
        label: "product-notes.md",
        pageId: "page-c",
        kind: "file",
      },
    ],
  },
  {
    id: "wiki",
    label: "Wiki",
    icon: "folder",
    children: [
      { id: "wiki-sources", label: "Sources", count: 1, kind: "folder" },
      {
        id: "wiki-entities",
        label: "Entities",
        pageId: "page-b",
        count: 1,
        kind: "folder",
      },
      {
        id: "wiki-concepts",
        label: "Concepts",
        pageId: "page-c",
        count: 1,
        kind: "folder",
      },
      {
        id: "wiki-questions",
        label: "Questions",
        pageId: "page-d",
        count: 1,
        kind: "folder",
      },
    ],
  },
  {
    id: "lint",
    label: "Lint Issues",
    icon: "warning",
    children: [
      {
        id: "lint-orphan",
        label: "1 orphan page",
        pageId: "page-d",
        count: 1,
        kind: "file",
      },
    ],
  },
  {
    id: "recent",
    label: "Recent",
    icon: "folder",
    children: [
      {
        id: "recent-a",
        label: "Project Aurora",
        pageId: "page-a",
        kind: "file",
      },
      {
        id: "recent-c",
        label: "Knowledge Graph",
        pageId: "page-c",
        kind: "file",
      },
    ],
  },
];

export const mockHealth: HealthSnapshot = {
  overall: "degraded",
  source: "mock",
  components: [
    { name: "api", label: "API", status: "ok", detail: "Mock ready" },
    {
      name: "postgres",
      label: "PostgreSQL",
      status: "ok",
      detail: "Mock connected",
    },
    { name: "redis", label: "Redis", status: "ok", detail: "Mock connected" },
    { name: "worker", label: "Worker", status: "ok", detail: "Mock idle" },
    {
      name: "storage",
      label: "Storage",
      status: "ok",
      detail: "Local adapter",
    },
    {
      name: "llm",
      label: "LLM",
      status: "degraded",
      detail: "Ollama offline",
    },
  ],
};

export const modelProfileFixture = {
  id: "profile-default-ollama",
  name: "Local Ollama",
  provider: "ollama",
  modelId: "qwen3:8b",
  status: "degraded" as const,
};
