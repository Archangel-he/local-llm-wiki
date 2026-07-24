import {
  graphEdges as initialGraphEdges,
  graphNodes as initialGraphNodes,
  modelProfileFixture,
  wikiPages as initialWikiPages,
} from "../fixtures/workspace";
import type { GraphEdge, GraphNode, WikiPage } from "../types";
import type {
  ActivityEntry,
  ExportPreview,
  IngestJob,
  JobEvent,
  ModelProfile,
  ModelProfileInput,
  Mvp1Client,
  SourceRecord,
  UploadResult,
  WorkspaceData,
} from "./contracts";
import { Mvp1ClientError } from "./contracts";

const MAX_SOURCE_BYTES = 10 * 1024 * 1024;

function clone<T>(value: T): T {
  return structuredClone(value);
}

function slugFromFilename(filename: string) {
  return filename
    .replace(/\.(md|txt)$/i, "")
    .trim()
    .toLocaleLowerCase()
    .replace(/[^a-z0-9\u3400-\u9fff]+/g, "-")
    .replace(/^-|-$/g, "");
}

function titleFromFilename(filename: string) {
  return filename
    .replace(/\.(md|txt)$/i, "")
    .split(/[-_]+/)
    .filter(Boolean)
    .map((part) => part[0]?.toLocaleUpperCase() + part.slice(1))
    .join(" ");
}

async function sha256(file: File) {
  const digest = await crypto.subtle.digest("SHA-256", await file.arrayBuffer());
  return [...new Uint8Array(digest)]
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

function systemPages(pages: WikiPage[], activity: ActivityEntry[]): WikiPage[] {
  const contentPages = pages.filter((page) => !page.systemView);
  return [
    {
      id: "system-index",
      title: "Index",
      type: "concept",
      status: "current",
      aliases: [],
      tags: ["system", "index"],
      summary: "当前 Workspace 的确定性 Wiki 索引。",
      body: contentPages.map((page) => `- [[${page.title}]] · ${page.type}`),
      sources: [],
      backlinks: [],
      revision: 1,
      systemView: "index",
    },
    {
      id: "system-activity",
      title: "Activity",
      type: "concept",
      status: "current",
      aliases: [],
      tags: ["system", "activity"],
      summary: "摄取任务与 Wiki 变更的只读活动记录。",
      body: activity.map(
        (entry) => `- ${entry.at.slice(0, 16).replace("T", " ")} · ${entry.label}`,
      ),
      sources: [],
      backlinks: [],
      revision: 1,
      systemView: "activity",
    },
  ];
}

export class MockMvp1Client implements Mvp1Client {
  private sources: SourceRecord[] = [
    {
      id: "source-aurora-a",
      filename: "aurora-a.md",
      sha256: "fixture-aurora-a",
      status: "active",
      content: "# Project Aurora\n\nProject Aurora 于 2025-03-01 启动，项目负责人是 Lin。",
      uploadedAt: "2026-07-23T08:00:00Z",
      pageId: "page-a",
    },
    {
      id: "source-product-notes",
      filename: "product-notes.md",
      sha256: "fixture-product-notes",
      status: "active",
      content: "# Knowledge Graph\n\n展示 Wiki 页面之间的关系。",
      uploadedAt: "2026-07-23T08:05:00Z",
      pageId: "page-c",
    },
  ];
  private jobs: IngestJob[] = [];
  private pages = clone(initialWikiPages);
  private graphNodes = clone(initialGraphNodes);
  private graphEdges = clone(initialGraphEdges);
  private activity: ActivityEntry[] = [
    {
      id: "activity-seed",
      at: "2026-07-23T08:05:00Z",
      label: "Initial Wiki fixture ready",
      detail: "4 pages and 2 wikilinks",
      pageId: "page-a",
    },
  ];
  private pending = new Map<
    string,
    {
      source: SourceRecord;
      page: WikiPage;
      node: GraphNode;
      edge: GraphEdge;
    }
  >();
  private profiles: ModelProfile[] = [
    {
      id: modelProfileFixture.id,
      displayName: modelProfileFixture.name,
      provider: "ollama",
      endpointOrigin: "server preset",
      modelName: modelProfileFixture.modelId,
      hasCredential: false,
      status: "unavailable",
      lastTestedAt: null,
      latencyMs: null,
      capabilities: { streaming: true, structuredOutput: true },
    },
  ];
  private defaultProfileId = modelProfileFixture.id;

  async loadWorkspace(): Promise<WorkspaceData> {
    return clone({
      sources: this.sources,
      jobs: this.jobs,
      pages: [...this.pages, ...systemPages(this.pages, this.activity)],
      graphNodes: this.graphNodes,
      graphEdges: this.graphEdges,
      activity: this.activity,
    });
  }

  async uploadSource(file: File): Promise<UploadResult> {
    if (!/\.(md|txt)$/i.test(file.name)) {
      throw new Mvp1ClientError(
        "UNSUPPORTED_FILE_TYPE",
        "Only UTF-8 Markdown and TXT files are supported.",
      );
    }
    if (file.size > MAX_SOURCE_BYTES) {
      throw new Mvp1ClientError(
        "FILE_TOO_LARGE",
        "The source exceeds the 10 MiB MVP 1 limit.",
      );
    }

    const content = await file.text();
    if (content.includes("\uFFFD")) {
      throw new Mvp1ClientError(
        "VALIDATION_ERROR",
        "The source must be valid UTF-8 text.",
      );
    }
    const digest = await sha256(file);
    const duplicate = this.sources.find((source) => source.sha256 === digest);
    if (duplicate) {
      return { source: clone(duplicate), job: null, duplicate: true };
    }

    const suffix = digest.slice(0, 8);
    const slug = slugFromFilename(file.name) || `page-${suffix}`;
    const title = titleFromFilename(file.name) || file.name;
    const source: SourceRecord = {
      id: `source-${suffix}`,
      filename: file.name,
      sha256: digest,
      status: "active",
      content,
      uploadedAt: new Date().toISOString(),
    };
    const page: WikiPage = {
      id: `page-${suffix}`,
      title,
      type: "source",
      status: "current",
      aliases: [slug],
      tags: ["source", "ingested"],
      summary: `由 ${file.name} 生成的 Source Summary。`,
      body: content
        .split(/\r?\n\r?\n/)
        .map((part) => part.trim())
        .filter(Boolean),
      sources: [`${file.name} · full source`],
      backlinks: ["Project Aurora"],
      revision: 1,
    };
    source.pageId = page.id;
    const node: GraphNode = {
      id: `node-${suffix}`,
      label: title,
      pageId: page.id,
      type: "source",
      x: 0.35,
      y: -1.15,
      size: 7,
    };
    const edge: GraphEdge = {
      id: `edge-${suffix}-aurora`,
      source: node.id,
      target: "node-a",
      type: "derived_from",
      evidence: `${file.name} was ingested into the Wiki.`,
    };
    const job: IngestJob = {
      id: `job-${suffix}`,
      type: "ingest",
      sourceId: source.id,
      filename: file.name,
      status: "queued",
      modelProfileId: this.defaultProfileId,
      model: {
        provider:
          this.profiles.find((profile) => profile.id === this.defaultProfileId)
            ?.provider ?? "ollama",
        name:
          this.profiles.find((profile) => profile.id === this.defaultProfileId)
            ?.modelName ?? "mock",
      },
      attempt: 1,
      maxAttempts: 3,
      progress: { stage: "queued", current: 0, total: 4 },
      error: null,
    };

    this.sources = [...this.sources, source];
    this.jobs = [job, ...this.jobs];
    this.pending.set(job.id, { source, page, node, edge });
    return { source: clone(source), job: clone(job), duplicate: false };
  }

  subscribeJob(jobId: string, onEvent: (event: JobEvent) => void) {
    const timers: number[] = [];
    const updates: Array<{
      delay: number;
      status: IngestJob["status"];
      stage: IngestJob["progress"]["stage"];
      current: number;
      type: JobEvent["type"];
    }> = [
      { delay: 80, status: "running", stage: "parsing", current: 1, type: "progress" },
      {
        delay: 240,
        status: "running",
        stage: "generating_wiki",
        current: 2,
        type: "progress",
      },
      {
        delay: 420,
        status: "running",
        stage: "committing",
        current: 3,
        type: "progress",
      },
      {
        delay: 620,
        status: "completed",
        stage: "completed",
        current: 4,
        type: "completed",
      },
    ];

    for (const update of updates) {
      timers.push(
        window.setTimeout(() => {
          const index = this.jobs.findIndex((job) => job.id === jobId);
          if (index < 0) return;
          const job = {
            ...this.jobs[index],
            status: update.status,
            progress: {
              ...this.jobs[index].progress,
              stage: update.stage,
              current: update.current,
            },
          };
          this.jobs[index] = job;

          let affectedPageIds: string[] | undefined;
          if (update.type === "completed") {
            const result = this.pending.get(jobId);
            if (result) {
              affectedPageIds = [result.page.id];
              this.pages = [...this.pages, result.page];
              this.graphNodes = [...this.graphNodes, result.node];
              this.graphEdges = [...this.graphEdges, result.edge];
              this.activity = [
                {
                  id: `activity-${jobId}`,
                  at: new Date().toISOString(),
                  label: `${result.source.filename} ingested`,
                  detail: `Created [[${result.page.title}]]`,
                  pageId: result.page.id,
                },
                ...this.activity,
              ];
              this.pending.delete(jobId);
            }
          }

          onEvent({
            type: update.type,
            job: clone(job),
            affectedPageIds,
          });
        }, update.delay),
      );
    }

    return () => timers.forEach((timer) => window.clearTimeout(timer));
  }

  async retryJob(jobId: string) {
    const job = this.jobs.find((item) => item.id === jobId);
    if (!job || job.status !== "failed" || job.attempt >= job.maxAttempts) {
      throw new Mvp1ClientError(
        "JOB_ALREADY_EXISTS",
        "The job cannot be retried.",
      );
    }
    job.status = "queued";
    job.error = null;
    job.progress = { stage: "queued", current: 0, total: 4 };
    return clone(job);
  }

  async cancelJob(jobId: string) {
    const job = this.jobs.find((item) => item.id === jobId);
    if (!job || !["queued", "running", "retrying"].includes(job.status)) {
      throw new Mvp1ClientError(
        "JOB_NOT_CANCELLABLE",
        "The job cannot be cancelled.",
      );
    }
    job.status = job.status === "queued" ? "cancelled" : "cancel_requested";
    return clone(job);
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
    if (
      input.provider === "openai_compatible" &&
      !input.baseUrl.startsWith("https://")
    ) {
      throw new Mvp1ClientError(
        "MODEL_ENDPOINT_BLOCKED",
        "Custom endpoints must use HTTPS.",
      );
    }
    const profile: ModelProfile = {
      id: `profile-${crypto.randomUUID()}`,
      displayName: input.displayName,
      provider: input.provider,
      endpointOrigin:
        input.provider === "ollama"
          ? "server preset"
          : new URL(input.baseUrl).origin,
      modelName: input.modelName,
      hasCredential: Boolean(input.apiKey),
      status: "untested",
      lastTestedAt: null,
      latencyMs: null,
      capabilities: { streaming: false, structuredOutput: false },
    };
    this.profiles = [...this.profiles, profile];
    return clone(profile);
  }

  async testModelProfile(profileId: string) {
    const index = this.profiles.findIndex((profile) => profile.id === profileId);
    const current = this.profiles[index];
    if (!current) throw new Error("Profile not found");
    const available = current.provider === "openai_compatible";
    const profile: ModelProfile = {
      ...current,
      status: available ? "active" : "unavailable",
      lastTestedAt: new Date().toISOString(),
      latencyMs: available ? 42 : null,
      capabilities: {
        streaming: available,
        structuredOutput: available,
      },
    };
    this.profiles[index] = profile;
    return clone(profile);
  }

  async setDefaultModelProfile(profileId: string) {
    const profile = this.profiles.find((item) => item.id === profileId);
    if (!profile || profile.status !== "active") {
      throw new Mvp1ClientError(
        "VALIDATION_ERROR",
        "Test the profile successfully before setting it as default.",
      );
    }
    this.defaultProfileId = profileId;
  }

  async getModelProfiles() {
    return clone({
      profiles: this.profiles,
      defaultProfileId: this.defaultProfileId,
    });
  }

  async getExportPreview(): Promise<ExportPreview> {
    const directoryByType: Record<WikiPage["type"], string> = {
      source: "Sources",
      entity: "Entities",
      concept: "Concepts",
      question: "Questions",
    };
    const views = systemPages(this.pages, this.activity);
    return {
      directories: ["Sources/", "Entities/", "Concepts/", "Questions/", "System/"],
      files: [
        ...this.pages.map((page) => ({
          path: `${directoryByType[page.type]}/${page.title.replaceAll(" ", "-")}.md`,
          preview: [
            "---",
            `type: ${page.type}`,
            `aliases: [${page.aliases.join(", ")}]`,
            "---",
            "",
            `# ${page.title}`,
            "",
            page.summary,
          ].join("\n"),
        })),
        ...views.map((page) => ({
          path: `System/${page.systemView === "activity" ? "log" : "index"}.md`,
          preview: [`# ${page.title}`, "", page.summary, "", ...page.body].join(
            "\n",
          ),
        })),
      ],
    };
  }
}
