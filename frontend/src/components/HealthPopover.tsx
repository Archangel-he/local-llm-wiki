import { Activity, CheckCircle2, CircleAlert } from "lucide-react";
import { useEffect, useState } from "react";
import { getHealthSnapshot } from "../api/health";
import { mockHealth } from "../fixtures/workspace";
import type { HealthSnapshot } from "../types";

interface HealthPopoverProps {
  open: boolean;
}

export function HealthPopover({ open }: HealthPopoverProps) {
  const [health, setHealth] = useState<HealthSnapshot>(mockHealth);

  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 800);
    getHealthSnapshot(controller.signal).then(setHealth);
    return () => {
      window.clearTimeout(timeout);
      controller.abort();
    };
  }, [open]);

  if (!open) return null;

  return (
    <section className="health-popover" data-testid="health-panel" aria-label="系统健康状态">
      <header>
        <Activity aria-hidden="true" />
        <div>
          <strong>System health</strong>
          <span>{health.source === "api" ? "Live API" : "Mock fallback"}</span>
        </div>
      </header>
      <ul>
        {health.components.map((component) => (
          <li key={component.name} data-testid={`health-${component.name}`}>
            {component.status === "ok" ? (
              <CheckCircle2 className="health-ok" />
            ) : (
              <CircleAlert className="health-warning" />
            )}
            <span>
              <strong>{component.label}</strong>
              <small>{component.detail}</small>
            </span>
            <em>{component.status}</em>
          </li>
        ))}
      </ul>
      <p>LLM degradation does not block browsing existing Wiki content.</p>
    </section>
  );
}
