export type PageStatus = "current" | "needs_review";

export interface WikiPage {
  id: string;
  title: string;
  type: "source" | "entity" | "concept" | "question";
  status: PageStatus;
  aliases: string[];
  tags: string[];
  summary: string;
  body: string[];
  sources: string[];
  backlinks: string[];
  revision: number;
  systemView?: "index" | "activity";
}

export interface GraphNode {
  id: string;
  label: string;
  pageId: string;
  type: WikiPage["type"];
  x: number;
  y: number;
  size: number;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: "wikilink" | "citation" | "derived_from";
  evidence: string;
}

export interface TreeSection {
  id: string;
  label: string;
  icon?: "folder" | "warning";
  children: Array<{
    id: string;
    label: string;
    pageId?: string;
    count?: number;
    kind?: "folder" | "file";
  }>;
}

export type HealthLevel = "ok" | "degraded" | "error";

export interface HealthComponent {
  name: string;
  label: string;
  status: HealthLevel;
  detail: string;
}

export interface HealthSnapshot {
  overall: HealthLevel;
  source: "api" | "mock";
  components: HealthComponent[];
}
