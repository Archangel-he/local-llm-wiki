import { Archive, FileText, Folder, X } from "lucide-react";
import type { ExportPreview } from "../mvp1/contracts";

export function ExportPreviewDialog({
  preview,
  onClose,
}: {
  preview: ExportPreview | null;
  onClose: () => void;
}) {
  if (!preview) return null;

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <section
        className="export-preview-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="export-preview-title"
        data-testid="export-preview"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header>
          <div>
            <Archive />
            <span>
              <strong id="export-preview-title">Obsidian Vault export preview</strong>
              <small>Frontmatter, aliases, type directories and system views</small>
            </span>
          </div>
          <button type="button" aria-label="Close export preview" onClick={onClose}>
            <X />
          </button>
        </header>
        <div className="export-preview-body">
          <aside>
            {preview.directories.map((directory) => (
              <span key={directory}>
                <Folder />
                {directory}
              </span>
            ))}
          </aside>
          <div>
            {preview.files.map((file) => (
              <article key={file.path}>
                <h3>
                  <FileText />
                  {file.path}
                </h3>
                <pre>{file.preview}</pre>
              </article>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
