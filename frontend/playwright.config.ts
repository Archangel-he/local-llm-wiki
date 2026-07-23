import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: "html",
  use: {
    baseURL: "http://127.0.0.1:4173",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: {
    command:
      "pnpm dev --host 127.0.0.1 --port 4173 --mode e2e",
    url: "http://127.0.0.1:4173",
    reuseExistingServer: !process.env.CI,
    env: {
      VITE_USE_MOCK_HEALTH: "true",
    },
  },
});
