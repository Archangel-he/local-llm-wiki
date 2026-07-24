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
  ModelProfile,
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
  const contentPages = data.pages.filter((page) => !page.systemView);
  const systemPages = data.pages.filter((page) => page.systemView);
  const initialWiki = initialTreeSections.find((section) => section.id === "wiki")!;
  const initialPageIds = new Set(wikiPages.map((page) => page.id));
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
        ...initialWiki.children,
        ...contentPages
          .filter((page) => !initialPageIds.has(page.id))
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
    initialTreeSections.find((section) => section.id === "lint")!,
    {
      id: "recent",
      label: "Recent",
      icon: "folder",
      children: data.activity.map((entry) => ({
        id: `recent-${entry.id}`,
        label: entry.label,
        pageId: entry.pageId,
        kind: "file" as const,
      })),
    },
  ];
}

export function useMvp1Workspace() {
  const client = useMemo(() => getMvp1Client(), []);
  const subscriptions = useRef(new Map<string, () => void>());
  const [data, setData] = useState<WorkspaceData>(initialData);
  const [profiles, setProfiles] = useState<ModelProfile[]>([]);
  const [defaultProfileId, setDefaultProfileId] = useState("");
  const [uploadMessage, setUploadMessage] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [completedPageId, setCompletedPageId] = useState<string | null>(null);
  const [exportPreview, setExportPreview] = useState<ExportPreview | null>(null);

  const refresh = useCallback(async () => {
    setData(await client.loadWorkspace());
  }, [client]);

  const refreshProfiles = useCallback(async () => {
    const result = await client.getModelProfiles();
    setProfiles(result.profiles);
    setDefaultProfileId(result.defaultProfileId);
  }, [client]);

  useEffect(() => {
    let active = true;
    void Promise.all([client.loadWorkspace(), client.getModelProfiles()]).then(
      ([workspace, profileData]) => {
        if (!active) return;
        setData(workspace);
        setProfiles(profileData.profiles);
        setDefaultProfileId(profileData.defaultProfileId);
      },
    );
    const activeSubscriptions = subscriptions.current;
    return () => {
      active = false;
      activeSubscriptions.forEach((unsubscribe) => unsubscribe());
      activeSubscriptions.clear();
    };
  }, [client]);

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
        const unsubscribe = client.subscribeJob(result.job.id, (event) => {
          setData((current) => ({
            ...current,
            jobs: current.jobs.map((job) =>
              job.id === event.job.id ? event.job : job,
            ),
          }));
          if (event.type === "completed") {
            subscriptions.current.get(event.job.id)?.();
            subscriptions.current.delete(event.job.id);
            setCompletedPageId(event.affectedPageIds?.[0] ?? null);
            setUploadMessage(`${file.name} completed and the Wiki was refreshed.`);
            void refresh();
          }
        });
        subscriptions.current.set(result.job.id, unsubscribe);
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
    uploadSource,
    createProfile,
    testProfile,
    setDefaultProfile,
    loadExportPreview,
    closeExportPreview: () => setExportPreview(null),
  };
}
