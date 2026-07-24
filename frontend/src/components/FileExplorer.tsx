import {
  ChevronDown,
  ChevronRight,
  FileText,
  FolderClosed,
  FolderOpen,
  PackageOpen,
  Search,
  TriangleAlert,
  Upload,
} from "lucide-react";
import { useMemo, useRef, useState } from "react";
import { defaultWorkspace, treeSections } from "../fixtures/workspace";
import { useI18n } from "../i18n";
import type { IngestJob } from "../mvp1/contracts";
import type { TreeSection } from "../types";
import { JobStatusPanel } from "./JobStatusPanel";

interface FileExplorerProps {
  selectedPageId: string;
  onSelectPage: (pageId: string) => void;
  sections?: TreeSection[];
  jobs?: IngestJob[];
  uploadMessage?: string | null;
  uploadError?: string | null;
  uploading?: boolean;
  onUploadSource?: (file: File) => void;
  onExportPreview?: () => void;
  onRetryJob?: (jobId: string) => void;
  onCancelJob?: (jobId: string) => void;
}

function uniqueSectionLabels(section: TreeSection): TreeSection {
  const counts = new Map<string, number>();
  for (const item of section.children) {
    counts.set(item.label, (counts.get(item.label) ?? 0) + 1);
  }
  return {
    ...section,
    children: section.children.map((item) => ({
      ...item,
      label:
        (counts.get(item.label) ?? 0) > 1
          ? `${item.label} · ${item.id.slice(-8)}`
          : item.label,
    })),
  };
}

export function FileExplorer({
  selectedPageId,
  onSelectPage,
  sections: suppliedSections = treeSections,
  jobs = [],
  uploadMessage = null,
  uploadError = null,
  uploading = false,
  onUploadSource,
  onExportPreview,
  onRetryJob,
  onCancelJob,
}: FileExplorerProps) {
  const { t } = useI18n();
  const uploadInputRef = useRef<HTMLInputElement>(null);
  const [expanded, setExpanded] = useState(() => new Set(["wiki"]));
  const [query, setQuery] = useState("");

  const sections = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase();
    return suppliedSections
      .filter((section) => section.id !== "recent" && section.children.length > 0)
      .map(uniqueSectionLabels)
      .map((section) =>
        normalized
          ? {
              ...section,
              children: section.children.filter((item) =>
                item.label.toLocaleLowerCase().includes(normalized),
              ),
            }
          : section,
      )
      .filter((section) => section.children.length > 0);
  }, [query, suppliedSections]);

  const sectionLabel = (section: TreeSection) => {
    if (section.id === "raw") return t("rawSources");
    if (section.id === "wiki") return t("wiki");
    if (section.id === "lint") return t("issues");
    return section.label;
  };

  const toggle = (sectionId: string) => {
    setExpanded((current) => {
      const next = new Set(current);
      if (next.has(sectionId)) next.delete(sectionId);
      else next.add(sectionId);
      return next;
    });
  };

  return (
    <aside className="left-sidebar" data-testid="file-tree">
      <div className="vault-switcher">
        <FolderOpen aria-hidden="true" />
        <strong>{defaultWorkspace.name}</strong>
      </div>

      <div className="file-toolbar">
        <span>{t("files")}</span>
        <div>
          <button
            className="file-action"
            type="button"
            title={t("uploadTitle")}
            disabled={uploading}
            onClick={() => uploadInputRef.current?.click()}
          >
            <Upload />
            <span>{t("upload")}</span>
          </button>
          <input
            ref={uploadInputRef}
            className="sr-only"
            type="file"
            accept=".md,.txt,text/markdown,text/plain"
            data-testid="source-upload-input"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) onUploadSource?.(file);
              event.target.value = "";
            }}
          />
          <button
            className="file-action"
            type="button"
            title={t("exportTitle")}
            onClick={onExportPreview}
          >
            <PackageOpen />
            <span>{t("export")}</span>
          </button>
        </div>
      </div>

      <label className="file-search">
        <Search aria-hidden="true" />
        <span className="sr-only">{t("filterFiles")}</span>
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder={t("filterFiles")}
          aria-label={t("filterFiles")}
        />
      </label>

      <JobStatusPanel
        jobs={jobs}
        message={uploadMessage}
        error={uploadError}
        onRetry={onRetryJob}
        onCancel={onCancelJob}
      />

      <nav className="file-tree" aria-label={t("files")}>
        {sections.map((section) => {
          const isExpanded = query ? true : expanded.has(section.id);
          return (
            <section className="tree-group" key={section.id}>
              <button
                className="tree-folder"
                type="button"
                aria-expanded={isExpanded}
                onClick={() => toggle(section.id)}
                data-testid={`tree-section-${section.id}`}
              >
                {isExpanded ? <ChevronDown /> : <ChevronRight />}
                {section.icon === "warning" ? (
                  <TriangleAlert className="tree-warning" />
                ) : isExpanded ? (
                  <FolderOpen />
                ) : (
                  <FolderClosed />
                )}
                <span>{sectionLabel(section)}</span>
                <span className="tree-count">{section.children.length}</span>
              </button>

              {isExpanded && (
                <ul>
                  {section.children.map((item) => {
                    const isSelected = item.pageId === selectedPageId;
                    const content = (
                      <>
                        {item.kind === "folder" ? (
                          <FolderClosed />
                        ) : (
                          <FileText />
                        )}
                        <span>{item.label}</span>
                        {item.count !== undefined && (
                          <span className="tree-count">{item.count}</span>
                        )}
                      </>
                    );

                    return (
                      <li key={item.id}>
                        {item.pageId ? (
                          <button
                            className={`tree-item${isSelected ? " is-selected" : ""}`}
                            type="button"
                            aria-current={isSelected ? "page" : undefined}
                            onClick={() => onSelectPage(item.pageId!)}
                            data-testid={`tree-item-${item.id}`}
                          >
                            {content}
                          </button>
                        ) : (
                          <div
                            className="tree-item is-static"
                            data-testid={`tree-item-${item.id}`}
                          >
                            {content}
                          </div>
                        )}
                      </li>
                    );
                  })}
                </ul>
              )}
            </section>
          );
        })}
      </nav>
    </aside>
  );
}
