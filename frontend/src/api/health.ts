import { mockHealth } from "../fixtures/workspace";
import type { HealthSnapshot } from "../types";

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "";

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
    const payload = (await response.json()) as Omit<HealthSnapshot, "source">;
    return { ...payload, source: "api" };
  } catch {
    return mockHealth;
  }
}
