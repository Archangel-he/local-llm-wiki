import {
  Bookmark,
  ChevronDown,
  ChevronRight,
  ChevronsUpDown,
  FilePlus2,
  FileText,
  FolderClosed,
  FolderOpen,
  FolderPlus,
  PackageOpen,
  Search,
  SortAsc,
  TriangleAlert,
  Upload,
} from "lucide-react";
import { useMemo, useRef, useState } from "react";
import { defaultWorkspace, treeSections } from "../fixtures/workspace";
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
}: FileExplorerProps) {
  const uploadInputRef = useRef<HTMLInputElement>(null);
  const [expanded, setExpanded] = useState(
    () => new Set(suppliedSections.map((section) => section.id)),
  );
  const [searching, setSearching] = useState(false);
  const [query, setQuery] = useState("");

  const sections = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase();
    if (!normalized) return suppliedSections;
    return suppliedSections
      .map((section) => ({
        ...section,
        children: section.children.filter((item) =>
          item.label.toLocaleLowerCase().includes(normalized),
        ),
      }))
      .filter((section) => section.children.length > 0);
  }, [query, suppliedSections]);

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
      <button className="vault-switcher" type="button">
        <strong>{defaultWorkspace.name}</strong>
        <ChevronsUpDown aria-hidden="true" />
      </button>

      <div className="sidebar-tabs" role="tablist" aria-label="左侧栏">
        <button className="is-active" type="button" role="tab" aria-selected>
          <FolderOpen aria-hidden="true" />
          <span className="sr-only">文件</span>
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={false}
          onClick={() => setSearching((value) => !value)}
        >
          <Search aria-hidden="true" />
          <span className="sr-only">搜索</span>
        </button>
        <button type="button" role="tab" aria-selected={false}>
          <Bookmark aria-hidden="true" />
          <span className="sr-only">书签</span>
        </button>
      </div>

      <div className="file-toolbar">
        <span>Files</span>
        <div>
          <button type="button" aria-label="新建笔记" title="新建笔记">
            <FilePlus2 />
          </button>
          <button
            type="button"
            aria-label="Upload Markdown or TXT"
            title="Upload source"
            disabled={uploading}
            onClick={() => uploadInputRef.current?.click()}
          >
            <Upload />
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
            type="button"
            aria-label="Preview Obsidian export"
            title="Export preview"
            onClick={onExportPreview}
          >
            <PackageOpen />
          </button>
          <button type="button" aria-label="新建文件夹" title="新建文件夹">
            <FolderPlus />
          </button>
          <button type="button" aria-label="排序" title="排序">
            <SortAsc />
          </button>
        </div>
      </div>

      <JobStatusPanel jobs={jobs} message={uploadMessage} error={uploadError} />

      {searching && (
        <div className="file-search">
          <Search aria-hidden="true" />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Filter files..."
            aria-label="筛选文件"
            autoFocus
          />
        </div>
      )}

      <nav className="file-tree" aria-label="知识库文件">
        {sections.map((section) => {
          const isExpanded = expanded.has(section.id);
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
                <span>{section.label}</span>
              </button>

              {isExpanded && (
                <ul>
                  {section.children.map((item) => {
                    const isSelected = item.pageId === selectedPageId;
                    return (
                      <li key={item.id}>
                        <button
                          className={`tree-item${isSelected ? " is-selected" : ""}`}
                          type="button"
                          disabled={!item.pageId}
                          aria-current={isSelected ? "page" : undefined}
                          onClick={() =>
                            item.pageId && onSelectPage(item.pageId)
                          }
                          data-testid={`tree-item-${item.id}`}
                        >
                          {item.kind === "folder" ? (
                            <FolderClosed />
                          ) : (
                            <FileText />
                          )}
                          <span>{item.label}</span>
                          {item.count !== undefined && (
                            <span className="tree-count">{item.count}</span>
                          )}
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </section>
          );
        })}
      </nav>

      <div className="sidebar-collapse-hint">
        <ChevronRight aria-hidden="true" />
        <span>Local vault</span>
      </div>
    </aside>
  );
}
