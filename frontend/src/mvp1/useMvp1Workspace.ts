import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  graphEdges,
  graphNodes,
  treeSections as initialTreeSections,
  wikiPages,
} from "../fixtures/workspace";
import type { TreeSection } from "../types";
import { getMvp1Client } from "./client";
import type {
  ExportPreview,
  ExportJob,
  ModelProfile,
  ModelDiscoveryInput,
  ModelProfileInput,
  WorkspaceData,
} from "./contracts";
import { Mvp1ClientError } from "./contracts";

const initialData: WorkspaceData = {
  sources: [],
  jobs: [],
  pages: wikiPages,
  graphNodes,
  graphEdges,
  activity: [],
};

function buildTreeSections(data: WorkspaceData): TreeSection[] {
  const contentPages = data.pages.filter(
    (page) => !page.systemView && !page.tags.includes("raw-source"),
  );
  const systemPages = data.pages.filter((page) => page.systemView);
  const initialWiki = initialTreeSections.find((section) => section.id === "wiki")!;
  const initialPageIds = new Set(wikiPages.map((page) => page.id));
  const usingFixtures = contentPages.some((page) => page.id === "page-a");
  return [
    {
      id: "raw",
      label: "Raw Sources",
      icon: "folder",
      children: data.sources.map((source) => ({
        id:
          source.filename === "aurora-a.md"
            ? "raw-a"
            : source.filename === "product-notes.md"
              ? "raw-notes"
              : `raw-${source.id}`,
        label: source.filename,
        pageId: source.pageId,
        kind: "file" as const,
      })),
    },
    {
      id: "wiki",
      label: "Wiki",
      icon: "folder",
      children: [
        ...(usingFixtures ? initialWiki.children : []),
        ...contentPages
          .filter((page) => !usingFixtures || !initialPageIds.has(page.id))
          .map((page) => ({
          id: `wiki-${page.id}`,
          label: page.title,
          pageId: page.id,
          kind: "file" as const,
          })),
        ...systemPages.map((page) => ({
          id: `wiki-${page.id}`,
          label: page.title,
          pageId: page.id,
          kind: "file" as const,
        })),
      ],
    },
    usingFixtures
      ? initialTreeSections.find((section) => section.id === "lint")!
      : {
          id: "lint",
          label: "Lint Issues",
          icon: "warning",
          children: [],
        },
  ];
}

export function useMvp1Workspace() {
  const client = useMemo(() => getMvp1Client(), []);
  const subscriptions = useRef(new Map<string, () => void>());
  const sourceLoads = useRef(new Map<string, "loading" | "loaded" | "failed">());
  const [data, setData] = useState<WorkspaceData>(initialData);
  const [profiles, setProfiles] = useState<ModelProfile[]>([]);
  const [defaultProfileId, setDefaultProfileId] = useState("");
  const [uploadMessage, setUploadMessage] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [completedPageId, setCompletedPageId] = useState<string | null>(null);
  const [exportPreview, setExportPreview] = useState<ExportPreview | null>(null);
  const [exportJob, setExportJob] = useState<ExportJob | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);
  const exportSubscription = useRef<(() => void) | null>(null);

  const refresh = useCallback(async () => {
    sourceLoads.current.clear();
    setData(await client.loadWorkspace());
  }, [client]);

  const loadSourcePage = useCallback(
    async (pageId: string) => {
      const source = data.sources.find((item) => item.pageId === pageId);
      if (!source || source.content || sourceLoads.current.has(source.id)) return;

      sourceLoads.current.set(source.id, "loading");
      try {
        const content = await client.loadSourceContent(source.id);
        sourceLoads.current.set(source.id, "loaded");
        setData((current) => ({
          ...current,
          sources: current.sources.map((item) =>
            item.id === source.id ? { ...item, content } : item,
          ),
          pages: current.pages.map((page) =>
            page.id === pageId ? { ...page, body: [content] } : page,
          ),
        }));
      } catch (error) {
        sourceLoads.current.set(source.id, "failed");
        const message =
          error instanceof Error
            ? error.message
            : "The source content is unavailable.";
        setData((current) => ({
          ...current,
          pages: current.pages.map((page) =>
            page.id === pageId
              ? { ...page, body: [`Source content unavailable: ${message}`] }
              : page,
          ),
        }));
      }
    },
    [client, data.sources],
  );

  const refreshProfiles = useCallback(async () => {
    const result = await client.getModelProfiles();
    setProfiles(result.profiles);
    setDefaultProfileId(result.defaultProfileId);
  }, [client]);

  useEffect(() => {
    let active = true;
    void Promise.all([client.loadWorkspace(), client.getModelProfiles()])
      .then(([workspace, profileData]) => {
        if (!active) return;
        setData(workspace);
        setProfiles(profileData.profiles);
        setDefaultProfileId(profileData.defaultProfileId);
      })
      .catch((error: unknown) => {
        if (!active) return;
        setUploadError(
          error instanceof Error
            ? error.message
            : "The Workspace could not be loaded.",
        );
      });
    const activeSubscriptions = subscriptions.current;
    return () => {
      active = false;
      activeSubscriptions.forEach((unsubscribe) => unsubscribe());
      activeSubscriptions.clear();
      exportSubscription.current?.();
    };
  }, [client]);

  const watchJob = useCallback(
    (jobId: string, filename: string) => {
      subscriptions.current.get(jobId)?.();
      const unsubscribe = client.subscribeJob(jobId, (event) => {
        setData((current) => ({
          ...current,
          jobs: current.jobs.map((job) =>
            job.id === event.job.id
              ? { ...event.job, filename: job.filename }
              : job,
          ),
        }));
        if (
          event.type === "completed" ||
          event.type === "failed" ||
          event.type === "cancelled"
        ) {
          subscriptions.current.get(event.job.id)?.();
          subscriptions.current.delete(event.job.id);
        }
        if (event.type === "completed") {
          setCompletedPageId(event.affectedPageIds?.[0] ?? null);
          setUploadMessage(`${filename} completed and the Wiki was refreshed.`);
          void refresh();
        } else if (event.type === "failed") {
          setUploadError(event.job.error ?? `${filename} failed.`);
        }
      });
      subscriptions.current.set(jobId, unsubscribe);
    },
    [client, refresh],
  );

  const uploadSource = useCallback(
    async (file: File) => {
      setUploading(true);
      setUploadMessage(null);
      setUploadError(null);
      setCompletedPageId(null);
      try {
        const result = await client.uploadSource(file);
        await refresh();
        if (result.duplicate) {
          setUploadMessage(`${file.name} already exists; no duplicate Job was created.`);
          return;
        }
        if (!result.job) return;
        setUploadMessage(`${file.name} queued as ${result.job.id}.`);
        watchJob(result.job.id, file.name);
      } catch (error) {
        setUploadError(
          error instanceof Mvp1ClientError
            ? error.message
            : "The source could not be uploaded.",
        );
      } finally {
        setUploading(false);
      }
    },
    [client, refresh, watchJob],
  );

  const retryJob = useCallback(
    async (jobId: string) => {
      setUploadError(null);
      try {
        const job = await client.retryJob(jobId);
        await refresh();
        watchJob(jobId, job.filename);
      } catch (error) {
        setUploadError(error instanceof Error ? error.message : "Retry failed.");
      }
    },
    [client, refresh, watchJob],
  );

  const cancelJob = useCallback(
    async (jobId: string) => {
      setUploadError(null);
      try {
        await client.cancelJob(jobId);
        await refresh();
      } catch (error) {
        setUploadError(error instanceof Error ? error.message : "Cancel failed.");
      }
    },
    [client, refresh],
  );

  const createProfile = useCallback(
    async (input: ModelProfileInput) => {
      const profile = await client.createModelProfile(input);
      await refreshProfiles();
      return profile;
    },
    [client, refreshProfiles],
  );

  const updateProfile = useCallback(
    async (profileId: string, input: ModelProfileInput) => {
      const profile = await client.updateModelProfile(profileId, input);
      await refreshProfiles();
      return profile;
    },
    [client, refreshProfiles],
  );

  const deleteProfile = useCallback(
    async (profileId: string) => {
      await client.deleteModelProfile(profileId);
      await refreshProfiles();
    },
    [client, refreshProfiles],
  );

  const discoverModels = useCallback(
    (input: ModelDiscoveryInput) => client.discoverModels(input),
    [client],
  );

  const testProfile = useCallback(
    async (profileId: string) => {
      const profile = await client.testModelProfile(profileId);
      await refreshProfiles();
      return profile;
    },
    [client, refreshProfiles],
  );

  const setDefaultProfile = useCallback(
    async (profileId: string) => {
      await client.setDefaultModelProfile(profileId);
      await refreshProfiles();
    },
    [client, refreshProfiles],
  );

  const loadExportPreview = useCallback(async () => {
    const preview = await client.getExportPreview();
    setExportPreview(preview);
    setExportError(null);
    const savedId = window.localStorage.getItem("mvp1-export-id");
    if (!savedId) return;
    try {
      const job = await client.createExport();
      setExportJob(job);
      window.localStorage.setItem("mvp1-export-id", job.id);
      if (!["completed", "failed", "cancelled"].includes(job.status)) {
        exportSubscription.current?.();
        exportSubscription.current = client.subscribeExport(savedId, setExportJob);
      }
    } catch {
      window.localStorage.removeItem("mvp1-export-id");
      setExportJob(null);
    }
  }, [client]);

  const startExport = useCallback(async () => {
    setExportError(null);
    exportSubscription.current?.();
    try {
      const job = await client.createExport();
      setExportJob(job);
      window.localStorage.setItem("mvp1-export-id", job.id);
      if (!["completed", "failed", "cancelled"].includes(job.status)) {
        exportSubscription.current = client.subscribeExport(job.id, (updated) => {
          setExportJob(updated);
          if (["completed", "failed", "cancelled"].includes(updated.status)) {
            exportSubscription.current?.();
            exportSubscription.current = null;
          }
        });
      }
    } catch (error) {
      setExportError(
        error instanceof Error ? error.message : "The Vault export could not be created.",
      );
    }
  }, [client]);

  return {
    data,
    treeSections: buildTreeSections(data),
    profiles,
    defaultProfileId,
    uploadMessage,
    uploadError,
    uploading,
    completedPageId,
    exportPreview,
    exportJob,
    exportError,
    exportDownloadUrl:
      exportJob?.status === "completed"
        ? client.getExportDownloadUrl(exportJob.id)
        : null,
    uploadSource,
    loadSourcePage,
    retryJob,
    cancelJob,
    createProfile,
    updateProfile,
    deleteProfile,
    discoverModels,
    testProfile,
    setDefaultProfile,
    loadExportPreview,
    startExport,
    closeExportPreview: () => setExportPreview(null),
  };
}
