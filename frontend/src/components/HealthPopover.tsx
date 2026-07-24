import { Activity, CheckCircle2, CircleAlert } from "lucide-react";
import { useEffect, useState } from "react";
import { getHealthSnapshot } from "../api/health";
import { mockHealth } from "../fixtures/workspace";
import { useI18n } from "../i18n";
import type { HealthSnapshot } from "../types";

interface HealthPopoverProps {
  open: boolean;
}

export function HealthPopover({ open }: HealthPopoverProps) {
  const { t } = useI18n();
  const [health, setHealth] = useState<HealthSnapshot>(mockHealth);

  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 4_500);
    getHealthSnapshot(controller.signal).then(setHealth);
    return () => {
      window.clearTimeout(timeout);
      controller.abort();
    };
  }, [open]);

  if (!open) return null;

  return (
    <section className="health-popover" data-testid="health-panel" aria-label={t("systemHealth")}>
      <header>
        <Activity aria-hidden="true" />
        <div>
          <strong>{t("systemHealth")}</strong>
          <span>{health.source === "api" ? t("liveApi") : t("mockFallback")}</span>
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
      <p>{t("healthNote")}</p>
    </section>
  );
}
