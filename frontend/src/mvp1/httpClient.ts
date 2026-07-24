import type { GraphEdge, GraphNode, WikiPage } from "../types";
import type {
  ActivityEntry,
  ExportJob,
  ExportPreview,
  IngestJob,
  JobEvent,
  JobStage,
  ModelDiscoveryInput,
  ModelProfile,
  ModelProfileInput,
  Mvp1Client,
  SourceRecord,
  UploadResult,
  WorkspaceData,
} from "./contracts";
import { Mvp1ClientError } from "./contracts";

interface ApiErrorBody {
  error?: { code?: string; message?: string };
}

interface ApiSource {
  id: string;
  filename: string;
  sha256: string;
  status: "active" | "archived";
  created_at: string;
}

interface ApiJob {
  id: string;
  source_id: string | null;
  type: string;
  status: IngestJob["status"];
  model_profile_id: string | null;
  model: { provider: IngestJob["model"]["provider"]; name: string | null } | null;
  attempt: number;
  max_attempts: number;
  progress: {
    stage?: JobStage;
    current?: number;
    total?: number;
    percent?: number;
  };
  error: { code: string; message: string } | null;
}

interface ApiWikiSummary {
  id: string;
  slug: string;
  title: string;
  page_type: string;
  summary: string | null;
  status: string;
  revision_no: number | null;
}

interface ApiWikiPage extends ApiWikiSummary {
  markdown: string;
  aliases: string[];
  links: Array<{
    target_page_id: string | null;
    target_slug: string;
    type: string;
  }>;
  citations: Array<{
    source_id: string;
    locator: string;
    excerpt: string | null;
  }>;
}

interface ApiGraph {
  nodes: Array<{
    id: string;
    label: string;
    type: string;
    degree: number;
  }>;
  edges: Array<{
    id: string;
    source: string;
    target: string | null;
    target_slug: string;
    type: GraphEdge["type"];
  }>;
}

interface ApiActivity {
  id: string;
  action: string;
  resource_type: string;
  resource_id: string;
  created_at: string;
  metadata: Record<string, unknown>;
}

interface ApiProfile {
  id: string;
  provider: ModelProfile["provider"];
  display_name: string;
  endpoint_origin: string | null;
  model_name: string | null;
  has_credential: boolean;
  capabilities: {
    streaming?: boolean;
    structured_output?: boolean;
  };
  status: string;
  last_tested_at: string | null;
}

interface ApiExport {
  id: string;
  status: ExportJob["status"];
  progress: { stage?: string };
  error: { code: string; message: string } | null;
  filename: string | null;
  sha256: string | null;
  size_bytes: number | null;
}

const pageTypeMap: Record<string, WikiPage["type"]> = {
  topic: "concept",
  analysis: "concept",
  concept: "concept",
  entity: "entity",
  source: "source",
  question: "question",
};

function pageType(value: string): WikiPage["type"] {
  return pageTypeMap[value] ?? "concept";
}

function profileStatus(value: string): ModelProfile["status"] {
  if (value === "active" || value === "invalid" || value === "unavailable") {
    return value;
  }
  return "untested";
}

function jobFromApi(job: ApiJob, filename = "Source ingest"): IngestJob {
  return {
    id: job.id,
    type: "ingest",
    sourceId: job.source_id ?? "",
    filename,
    status: job.status,
    modelProfileId: job.model_profile_id ?? "",
    model: {
      provider: job.model?.provider ?? "mock",
      name: job.model?.name ?? "server-selected",
    },
    attempt: job.attempt,
    maxAttempts: job.max_attempts,
    progress: {
      stage: job.progress.stage ?? "queued",
      current: job.progress.current ?? job.progress.percent ?? 0,
      total:
        job.progress.total ??
        (job.progress.percent === undefined ? 1 : 100),
    },
    error: job.error?.message ?? null,
  };
}

function profileFromApi(
  profile: ApiProfile,
  latencyMs: number | null = null,
): ModelProfile {
  return {
    id: profile.id,
    displayName: profile.display_name,
    provider: profile.provider,
    endpointOrigin: profile.endpoint_origin ?? "server preset",
    modelName: profile.model_name ?? "server-selected",
    hasCredential: profile.has_credential,
    status: profileStatus(profile.status),
    lastTestedAt: profile.last_tested_at,
    latencyMs,
    capabilities: {
      streaming: Boolean(profile.capabilities.streaming),
      structuredOutput: Boolean(profile.capabilities.structured_output),
    },
  };
}

function exportFromApi(item: ApiExport): ExportJob {
  return {
    id: item.id,
    status: item.status,
    stage: item.progress.stage ?? "queued",
    filename: item.filename,
    sha256: item.sha256,
    sizeBytes: item.size_bytes,
    error: item.error?.message ?? null,
  };
}

function exportPreview(data: WorkspaceData): ExportPreview {
  const directoryByType: Record<WikiPage["type"], string> = {
    source: "Sources",
    entity: "Entities",
    concept: "Concepts",
    question: "Questions",
  };
  return {
    directories: ["Sources/", "Entities/", "Concepts/", "Questions/", "System/"],
    files: data.pages.map((page) => ({
      path: page.systemView
        ? `System/${page.systemView === "activity" ? "log" : "index"}.md`
        : `${directoryByType[page.type]}/${page.title.replaceAll(" ", "-")}.md`,
      preview: [
        ...(page.systemView
          ? []
          : ["---", `type: ${page.type}`, `aliases: [${page.aliases.join(", ")}]`, "---", ""]),
        `# ${page.title}`,
        "",
        page.summary,
        "",
        ...page.body,
      ].join("\n"),
    })),
  };
}

export class HttpMvp1Client implements Mvp1Client {
  private readonly root: string;
  private lastWorkspace: WorkspaceData | null = null;
  private readonly profileLatency = new Map<string, number | null>();

  constructor(
    apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "",
    workspaceId =
      import.meta.env.VITE_WORKSPACE_ID ??
      "00000000-0000-0000-0000-000000000002",
  ) {
    this.root = `${apiBaseUrl}/api/workspaces/${workspaceId}`;
  }

  private async request<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(`${this.root}${path}`, {
      credentials: "same-origin",
      ...init,
      headers: {
        Accept: "application/json",
        ...init?.headers,
      },
    });
    if (!response.ok) {
      const body = (await response.json().catch(() => ({}))) as ApiErrorBody;
      throw new Mvp1ClientError(
        body.error?.code ?? "API_ERROR",
        body.error?.message ?? `Request failed with status ${response.status}.`,
      );
    }
    if (response.status === 204) return undefined as T;
    return response.json() as Promise<T>;
  }

  async loadWorkspace(): Promise<WorkspaceData> {
    const [tree, jobsResponse, graph, activityResponse] = await Promise.all([
      this.request<{ sources: Array<{ id: string; filename: string; status: string }>; wiki: ApiWikiSummary[] }>("/tree"),
      this.request<{ items: ApiJob[] }>("/jobs"),
      this.request<ApiGraph>("/graph"),
      this.request<{ items: ApiActivity[] }>("/wiki-system/activity"),
    ]);

    const [sources, wikiDetails] = await Promise.all([
      Promise.all(
        tree.sources.map(async (item): Promise<SourceRecord> => {
          const metadata = await this.request<ApiSource>(`/sources/${item.id}`);
          return {
            id: metadata.id,
            filename: metadata.filename,
            sha256: metadata.sha256,
            status: metadata.status,
            content: "",
            uploadedAt: metadata.created_at,
            pageId: `raw-${metadata.id}`,
          };
        }),
      ),
      Promise.all(
        tree.wiki.map((page) =>
          this.request<ApiWikiPage>(`/wiki/${page.id}`),
        ),
      ),
    ]);

    const backlinks = new Map<string, string[]>();
    for (const page of wikiDetails) {
      for (const link of page.links) {
        if (!link.target_page_id) continue;
        backlinks.set(link.target_page_id, [
          ...(backlinks.get(link.target_page_id) ?? []),
          page.title,
        ]);
      }
    }

    const contentPages: WikiPage[] = wikiDetails.map((page) => ({
      id: page.id,
      title: page.title,
      type: pageType(page.page_type),
      status: page.status === "current" ? "current" : "needs_review",
      aliases: page.aliases,
      tags: [page.page_type],
      summary: page.summary ?? "",
      body: [page.markdown],
      sources: page.citations.map(
        (citation) =>
          `${citation.source_id} · ${citation.locator}${citation.excerpt ? ` · ${citation.excerpt}` : ""}`,
      ),
      backlinks: backlinks.get(page.id) ?? [],
      revision: page.revision_no ?? 0,
    }));
    const rawPages: WikiPage[] = sources.map((source) => ({
      id: source.pageId!,
      title: source.filename,
      type: "source",
      status: "current",
      aliases: [],
      tags: ["raw-source"],
      summary: `Immutable source · sha256:${source.sha256}`,
      body: [source.content],
      sources: [`${source.filename} · full source`],
      backlinks: [],
      revision: 1,
    }));
    const activity: ActivityEntry[] = activityResponse.items.map((item) => ({
      id: item.id,
      at: item.created_at,
      label: item.action,
      detail: `${item.resource_type} · ${JSON.stringify(item.metadata)}`,
      pageId:
        item.resource_type === "wiki_page" ? item.resource_id : undefined,
    }));
    const indexPage: WikiPage = {
      id: "system-index",
      title: "Index",
      type: "concept",
      status: "current",
      aliases: [],
      tags: ["system", "index"],
      summary: "Deterministic index of the current Workspace.",
      body: tree.wiki.map((page) => `- [[${page.title}]] · ${page.page_type}`),
      sources: [],
      backlinks: [],
      revision: 1,
      systemView: "index",
    };
    const activityPage: WikiPage = {
      id: "system-activity",
      title: "Activity",
      type: "concept",
      status: "current",
      aliases: [],
      tags: ["system", "activity"],
      summary: "Read-only audit activity for the current Workspace.",
      body: activity.map((item) => `- ${item.at} · ${item.label} · ${item.detail}`),
      sources: [],
      backlinks: [],
      revision: 1,
      systemView: "activity",
    };
    const graphNodes: GraphNode[] = graph.nodes.map((node, index) => {
      const angle = index * 2.399963;
      const radius = 0.55 + Math.sqrt(index + 1) * 0.28;
      return {
        id: node.id,
        label: node.label,
        pageId: node.id,
        type: pageType(node.type),
        x: Math.cos(angle) * radius,
        y: Math.sin(angle) * radius,
        size: Math.max(5, Math.min(12, 6 + node.degree)),
      };
    });
    const graphEdges: GraphEdge[] = graph.edges
      .filter((edge): edge is typeof edge & { target: string } => edge.target !== null)
      .map((edge) => ({
        id: edge.id,
        source: edge.source,
        target: edge.target,
        type:
          edge.type === "citation" || edge.type === "derived_from"
            ? edge.type
            : "wikilink",
        evidence: `${edge.type} · ${edge.target_slug}`,
      }));
    const filenameBySource = new Map(sources.map((source) => [source.id, source.filename]));
    const data: WorkspaceData = {
      sources,
      jobs: jobsResponse.items
        .filter((job) => job.type === "ingest")
        .map((job) =>
          jobFromApi(job, filenameBySource.get(job.source_id ?? "") ?? "Source ingest"),
        ),
      pages: [...contentPages, ...rawPages, indexPage, activityPage],
      graphNodes,
      graphEdges,
      activity,
    };
    this.lastWorkspace = data;
    return data;
  }

  async loadSourceContent(sourceId: string) {
    const response = await fetch(`${this.root}/sources/${sourceId}/content`, {
      credentials: "same-origin",
      headers: { Accept: "text/plain" },
    });
    if (!response.ok) {
      const body = (await response.json().catch(() => ({}))) as ApiErrorBody;
      throw new Mvp1ClientError(
        body.error?.code ?? "SOURCE_CONTENT_UNAVAILABLE",
        body.error?.message ?? "The source content is unavailable.",
      );
    }
    return response.text();
  }

  async uploadSource(file: File): Promise<UploadResult> {
    const form = new FormData();
    form.append("file", file);
    const result = await this.request<{
      source: ApiSource;
      job: ApiJob;
      deduplicated: boolean;
    }>("/sources", { method: "POST", body: form });
    return {
      source: {
        id: result.source.id,
        filename: result.source.filename,
        sha256: result.source.sha256,
        status: result.source.status,
        content: "",
        uploadedAt: result.source.created_at,
        pageId: `raw-${result.source.id}`,
      },
      job: result.deduplicated
        ? null
        : jobFromApi(result.job, result.source.filename),
      duplicate: result.deduplicated,
    };
  }

  subscribeJob(jobId: string, onEvent: (event: JobEvent) => void) {
    let stopped = false;
    let pollTimer: number | null = null;
    const eventSource = new EventSource(`${this.root}/jobs/${jobId}/events`);
    const terminal = new Set(["completed", "failed", "cancelled"]);

    const emit = (type: JobEvent["type"], payload: ApiJob) => {
      onEvent({ type, job: jobFromApi(payload) });
      if (terminal.has(type)) cleanup();
    };
    for (const type of ["snapshot", "progress", "completed", "failed", "cancelled"] as const) {
      eventSource.addEventListener(type, (event) => {
        emit(type, JSON.parse((event as MessageEvent).data) as ApiJob);
      });
    }
    const poll = async () => {
      if (stopped) return;
      try {
        const job = await this.request<ApiJob>(`/jobs/${jobId}`);
        const type = terminal.has(job.status)
          ? (job.status as JobEvent["type"])
          : "progress";
        emit(type, job);
        if (!terminal.has(job.status)) {
          pollTimer = window.setTimeout(poll, 1000);
        }
      } catch {
        pollTimer = window.setTimeout(poll, 1500);
      }
    };
    eventSource.onerror = () => {
      eventSource.close();
      void poll();
    };
    const cleanup = () => {
      stopped = true;
      eventSource.close();
      if (pollTimer !== null) window.clearTimeout(pollTimer);
    };
    return cleanup;
  }

  async retryJob(jobId: string) {
    return jobFromApi(
      await this.request<ApiJob>(`/jobs/${jobId}/retry`, { method: "POST" }),
    );
  }

  async cancelJob(jobId: string) {
    return jobFromApi(
      await this.request<ApiJob>(`/jobs/${jobId}/cancel`, { method: "POST" }),
    );
  }

  async createModelProfile(input: ModelProfileInput) {
    if (
      input.provider === "openai_compatible" &&
      !input.externalTransferConfirmed
    ) {
      throw new Mvp1ClientError(
        "VALIDATION_ERROR",
        "Confirm external data transfer before saving this profile.",
      );
    }
    const profile = await this.request<ApiProfile>("/model-profiles", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        display_name: input.displayName,
        provider: input.provider,
        base_url:
          input.provider === "ollama"
            ? input.baseUrl || "http://ollama:11434"
            : input.baseUrl,
        model_name: input.modelName,
        api_key: input.apiKey,
      }),
    });
    return profileFromApi(profile);
  }

  async updateModelProfile(profileId: string, input: ModelProfileInput) {
    const profile = await this.request<ApiProfile>(
      `/model-profiles/${profileId}`,
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          display_name: input.displayName,
          base_url:
            input.provider === "ollama"
              ? input.baseUrl || "http://host.docker.internal:11434"
              : input.baseUrl,
          model_name: input.modelName,
          ...(input.apiKey ? { api_key: input.apiKey } : {}),
        }),
      },
    );
    return profileFromApi(profile);
  }

  async deleteModelProfile(profileId: string) {
    await this.request<void>(`/model-profiles/${profileId}`, {
      method: "DELETE",
    });
  }

  async discoverModels(input: ModelDiscoveryInput) {
    const result = await this.request<{ items: string[] }>(
      "/model-profiles/discover",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          profile_id: input.profileId,
          provider: input.provider,
          base_url: input.baseUrl,
          api_key: input.apiKey,
        }),
      },
    );
    return result.items;
  }

  async testModelProfile(profileId: string) {
    const result = await this.request<{
      reachable: boolean;
      model_found: boolean;
      streaming_supported: boolean;
      structured_output_supported: boolean;
      latency_ms: number | null;
      safe_reason?: string;
    }>(`/model-profiles/${profileId}/test`, { method: "POST" });
    this.profileLatency.set(profileId, result.latency_ms);
    if (!result.reachable || !result.model_found) {
      throw new Mvp1ClientError(
        "MODEL_PROFILE_INVALID",
        result.safe_reason ?? "The model profile is unavailable.",
      );
    }
    const profile = await this.request<ApiProfile>(
      `/model-profiles/${profileId}`,
    );
    return profileFromApi(profile, result.latency_ms);
  }

  async setDefaultModelProfile(profileId: string) {
    await this.request<ApiProfile>("/model-profiles/policy/default", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ default_model_profile_id: profileId }),
    });
  }

  async getModelProfiles() {
    const [workspace, profileList] = await Promise.all([
      this.request<{ default_model_profile_id: string | null }>(""),
      this.request<{ items: ApiProfile[] }>("/model-profiles"),
    ]);
    return {
      profiles: profileList.items.map((profile) =>
        profileFromApi(profile, this.profileLatency.get(profile.id) ?? null),
      ),
      defaultProfileId: workspace.default_model_profile_id ?? "",
    };
  }

  async getExportPreview() {
    const data = this.lastWorkspace ?? (await this.loadWorkspace());
    return exportPreview(data);
  }

  async createExport() {
    return exportFromApi(
      await this.request<ApiExport>("/exports", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ include_raw: true }),
      }),
    );
  }

  async getExport(exportId: string) {
    return exportFromApi(
      await this.request<ApiExport>(`/exports/${exportId}`),
    );
  }

  subscribeExport(exportId: string, onUpdate: (job: ExportJob) => void) {
    let stopped = false;
    let timer: number | null = null;
    const terminal = new Set(["completed", "failed", "cancelled"]);
    const poll = async () => {
      if (stopped) return;
      try {
        const job = await this.getExport(exportId);
        onUpdate(job);
        if (!terminal.has(job.status)) {
          timer = window.setTimeout(poll, 750);
        }
      } catch {
        timer = window.setTimeout(poll, 1250);
      }
    };
    void poll();
    return () => {
      stopped = true;
      if (timer !== null) window.clearTimeout(timer);
    };
  }

  getExportDownloadUrl(exportId: string) {
    return `${this.root}/exports/${exportId}/download`;
  }
}
