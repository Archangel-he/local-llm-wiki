import { mockHealth } from "../fixtures/workspace";
import type {
  HealthComponent,
  HealthLevel,
  HealthSnapshot,
} from "../types";

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "";

interface ApiHealthPayload {
  status: string;
  components: Record<string, string>;
}

const componentLabels: Record<string, string> = {
  api: "API",
  postgres: "PostgreSQL",
  redis: "Redis",
  worker: "Worker",
  storage: "Storage",
  llm: "LLM",
};

function toHealthLevel(name: string, status: string): HealthLevel {
  if (status === "ok") return "ok";
  if (status === "degraded" || (name === "llm" && status === "unavailable")) {
    return "degraded";
  }
  return "error";
}

function normalizeHealth(payload: ApiHealthPayload): HealthSnapshot {
  const components: HealthComponent[] = Object.entries(componentLabels).map(
    ([name, label]) => {
      const backendStatus = payload.components[name] ?? "unavailable";
      return {
        name,
        label,
        status: toHealthLevel(name, backendStatus),
        detail:
          backendStatus === "ok"
            ? "Available"
            : backendStatus === "unavailable"
              ? "Unavailable"
              : backendStatus,
      };
    },
  );

  return {
    overall:
      payload.status === "ok"
        ? "ok"
        : payload.status === "degraded"
          ? "degraded"
          : "error",
    source: "api",
    components,
  };
}

export async function getHealthSnapshot(
  signal?: AbortSignal,
): Promise<HealthSnapshot> {
  if (import.meta.env.VITE_USE_MOCK_HEALTH === "true") {
    return mockHealth;
  }
  try {
    const response = await fetch(`${apiBaseUrl}/api/health`, {
      headers: { Accept: "application/json" },
      signal,
    });
    if (!response.ok) {
      throw new Error(`Health request failed with ${response.status}`);
    }
    const payload = (await response.json()) as ApiHealthPayload;
    return normalizeHealth(payload);
  } catch {
    return mockHealth;
  }
}
