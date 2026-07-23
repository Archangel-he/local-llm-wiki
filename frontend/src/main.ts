/// <reference lib="dom" />

/* ============================================
   local-llm-wiki — MVP 0 Mock Frontend
   ============================================ */

interface HealthResponse {
  status: string;
  components: Record<string, string>;
}

async function checkHealth(): Promise<HealthResponse | null> {
  try {
    const resp = await fetch("/api/health");
    if (!resp.ok) return null;
    return (await resp.json()) as HealthResponse;
  } catch {
    return null;
  }
}

function getReadyCount(health: HealthResponse): number {
  return Object.values(health.components).filter((v) => v === "ok").length;
}

function getTotalCount(health: HealthResponse): number {
  return Object.keys(health.components).length;
}

function updateHealthUI(health: HealthResponse) {
  const badge = document.getElementById("health-badge");
  const detail = document.getElementById("health-detail");

  if (!badge) return;

  badge.textContent = health.status;
  badge.className = `badge ${health.status}`;

  if (detail) {
    const ready = getReadyCount(health);
    const total = getTotalCount(health);
    const parts: string[] = [];
    for (const [name, status] of Object.entries(health.components)) {
      parts.push(`${name}: ${status}`);
    }
    detail.textContent = `${ready}/${total} ready — ${parts.join(" | ")}`;
  }
}

function showError(msg: string) {
  const badge = document.getElementById("health-badge");
  if (badge) {
    badge.textContent = "offline";
    badge.className = "badge unhealthy";
  }
  const detail = document.getElementById("health-detail");
  if (detail) {
    detail.textContent = msg;
  }
}

async function main() {
  // Poll health every 10 seconds
  async function poll() {
    const health = await checkHealth();
    if (health) {
      updateHealthUI(health);
    } else {
      showError("Cannot reach API — is the backend running?");
    }
  }

  await poll();
  setInterval(poll, 10_000);
}

main().catch(console.error);
export {};
