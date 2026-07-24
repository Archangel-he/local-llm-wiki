import type { GraphEdge, GraphNode, WikiPage } from "../types";

export type SourceStatus = "active" | "archived";
export type JobStatus =
  | "queued"
  | "running"
  | "retrying"
  | "completed"
  | "failed"
  | "cancel_requested"
  | "cancelled";
export type JobStage =
  | "queued"
  | "starting"
  | "parsing"
  | "loading_context"
  | "calling_model"
  | "generating_wiki"
  | "validating"
  | "committing"
  | "completed";

export interface SourceRecord {
  id: string;
  filename: string;
  sha256: string;
  status: SourceStatus;
  content: string;
  uploadedAt: string;
  pageId?: string;
}

export interface JobProgress {
  stage: JobStage;
  current: number;
  total: number;
}

export interface IngestJob {
  id: string;
  type: "ingest";
  sourceId: string;
  filename: string;
  status: JobStatus;
  modelProfileId: string;
  model: {
    provider: "mock" | "ollama" | "openai_compatible";
    name: string;
  };
  attempt: number;
  maxAttempts: number;
  progress: JobProgress;
  error: string | null;
}

export interface ActivityEntry {
  id: string;
  at: string;
  label: string;
  detail: string;
  pageId?: string;
}

export interface WorkspaceData {
  sources: SourceRecord[];
  jobs: IngestJob[];
  pages: WikiPage[];
  graphNodes: GraphNode[];
  graphEdges: GraphEdge[];
  activity: ActivityEntry[];
}

export interface UploadResult {
  source: SourceRecord;
  job: IngestJob | null;
  duplicate: boolean;
}

export interface JobEvent {
  type: "snapshot" | "progress" | "completed" | "failed" | "cancelled";
  job: IngestJob;
  affectedPageIds?: string[];
}

export interface ModelProfile {
  id: string;
  displayName: string;
  provider: "mock" | "ollama" | "openai_compatible";
  endpointOrigin: string;
  modelName: string;
  hasCredential: boolean;
  status: "untested" | "active" | "invalid" | "unavailable";
  lastTestedAt: string | null;
  latencyMs: number | null;
  capabilities: {
    streaming: boolean;
    structuredOutput: boolean;
  };
}

export interface ModelProfileInput {
  displayName: string;
  provider: "ollama" | "openai_compatible";
  baseUrl: string;
  modelName: string;
  apiKey?: string;
  externalTransferConfirmed: boolean;
}

export interface ExportPreview {
  directories: string[];
  files: Array<{ path: string; preview: string }>;
}

export interface ExportJob {
  id: string;
  status: JobStatus;
  stage: string;
  filename: string | null;
  sha256: string | null;
  sizeBytes: number | null;
  error: string | null;
}

export interface Mvp1Client {
  loadWorkspace(): Promise<WorkspaceData>;
  uploadSource(file: File): Promise<UploadResult>;
  subscribeJob(jobId: string, onEvent: (event: JobEvent) => void): () => void;
  retryJob(jobId: string): Promise<IngestJob>;
  cancelJob(jobId: string): Promise<IngestJob>;
  createModelProfile(input: ModelProfileInput): Promise<ModelProfile>;
  testModelProfile(profileId: string): Promise<ModelProfile>;
  setDefaultModelProfile(profileId: string): Promise<void>;
  getModelProfiles(): Promise<{
    profiles: ModelProfile[];
    defaultProfileId: string;
  }>;
  getExportPreview(): Promise<ExportPreview>;
  createExport(): Promise<ExportJob>;
  getExport(exportId: string): Promise<ExportJob>;
  subscribeExport(
    exportId: string,
    onUpdate: (job: ExportJob) => void,
  ): () => void;
  getExportDownloadUrl(exportId: string): string;
}

export class Mvp1ClientError extends Error {
  constructor(
    public readonly code: string,
    message: string,
  ) {
    super(message);
  }
}
