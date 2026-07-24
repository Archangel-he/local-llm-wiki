import type { GraphEdge, GraphNode, WikiPage } from "../types";

export type SourceStatus = "active" | "archived";
export type JobStatus =
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "cancel_requested"
  | "cancelled";
export type JobStage =
  | "queued"
  | "parsing"
  | "generating_wiki"
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
    provider: "ollama" | "openai_compatible";
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
  provider: "ollama" | "openai_compatible";
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
  provider: ModelProfile["provider"];
  baseUrl: string;
  modelName: string;
  apiKey?: string;
  externalTransferConfirmed: boolean;
}

export interface ExportPreview {
  directories: string[];
  files: Array<{ path: string; preview: string }>;
}

export interface Mvp1Client {
  loadWorkspace(): Promise<WorkspaceData>;
  uploadSource(file: File): Promise<UploadResult>;
  subscribeJob(jobId: string, onEvent: (event: JobEvent) => void): () => void;
  createModelProfile(input: ModelProfileInput): Promise<ModelProfile>;
  testModelProfile(profileId: string): Promise<ModelProfile>;
  setDefaultModelProfile(profileId: string): Promise<void>;
  getModelProfiles(): Promise<{
    profiles: ModelProfile[];
    defaultProfileId: string;
  }>;
  getExportPreview(): Promise<ExportPreview>;
}

export class Mvp1ClientError extends Error {
  constructor(
    public readonly code:
      | "UNSUPPORTED_FILE_TYPE"
      | "FILE_TOO_LARGE"
      | "VALIDATION_ERROR"
      | "MODEL_ENDPOINT_BLOCKED",
    message: string,
  ) {
    super(message);
  }
}
