import { CheckCircle2, CircleAlert, LoaderCircle } from "lucide-react";
import type { IngestJob } from "../mvp1/contracts";

export function JobStatusPanel({
  jobs,
  message,
  error,
}: {
  jobs: IngestJob[];
  message: string | null;
  error: string | null;
}) {
  const job = jobs[0];
  if (!job && !message && !error) return null;

  return (
    <section className="job-status-panel" aria-label="Ingest jobs" data-testid="job-status">
      {error && (
        <p className="job-notice is-error" role="alert">
          <CircleAlert />
          {error}
        </p>
      )}
      {message && !job && <p className="job-notice">{message}</p>}
      {job && (
        <>
          <div className="job-status-heading">
            {job.status === "completed" ? (
              <CheckCircle2 />
            ) : (
              <LoaderCircle className={job.status === "running" ? "is-spinning" : ""} />
            )}
            <span>
              <strong>{job.filename}</strong>
              <small>
                {job.progress.stage.replace("_", " ")} · attempt {job.attempt}/{job.maxAttempts}
              </small>
            </span>
            <em>{job.status}</em>
          </div>
          <div
            className="job-progress"
            role="progressbar"
            aria-label={`${job.filename} progress`}
            aria-valuemin={0}
            aria-valuemax={job.progress.total}
            aria-valuenow={job.progress.current}
          >
            <i
              style={{
                width: `${(job.progress.current / job.progress.total) * 100}%`,
              }}
            />
          </div>
          {message && <p className="job-message" role="status">{message}</p>}
        </>
      )}
    </section>
  );
}
