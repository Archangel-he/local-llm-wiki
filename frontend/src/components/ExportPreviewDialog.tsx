import { Archive, Download, FileText, Folder, LoaderCircle, X } from "lucide-react";
import { useI18n } from "../i18n";
import type { ExportJob, ExportPreview } from "../mvp1/contracts";

export function ExportPreviewDialog({
  preview,
  job,
  error,
  downloadUrl,
  onStartExport,
  onClose,
}: {
  preview: ExportPreview | null;
  job: ExportJob | null;
  error: string | null;
  downloadUrl: string | null;
  onStartExport: () => void;
  onClose: () => void;
}) {
  const { t } = useI18n();
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
              <strong id="export-preview-title">{t("exportPreview")}</strong>
              <small>{t("exportPreviewHelp")}</small>
            </span>
          </div>
          <button type="button" aria-label={t("closeExport")} onClick={onClose}>
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
        <footer className="export-actions">
          <span data-testid="export-status">
            {error ??
              (job
                ? `${job.status} · ${job.stage}${job.sizeBytes ? ` · ${Math.ceil(job.sizeBytes / 1024)} KiB` : ""}`
                : t("exportReady"))}
          </span>
          {downloadUrl && job?.status === "completed" ? (
            <a
              className="export-primary-action"
              href={downloadUrl}
              download={job.filename ?? "local-llm-wiki.zip"}
              data-testid="export-download"
            >
              <Download />
              {t("downloadVaultZip")}
            </a>
          ) : (
            <button
              className="export-primary-action"
              type="button"
              onClick={onStartExport}
              disabled={job?.status === "queued" || job?.status === "running" || job?.status === "retrying"}
            >
              {job?.status === "queued" || job?.status === "running" || job?.status === "retrying" ? (
                <LoaderCircle className="is-spinning" />
              ) : (
                <Archive />
              )}
              {job?.status === "failed" || job?.status === "cancelled"
                ? t("createAgain")
                : t("createVaultZip")}
            </button>
          )}
        </footer>
      </section>
    </div>
  );
}
