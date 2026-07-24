import { defineConfig, devices } from "@playwright/test";

const externalBaseUrl = process.env.PLAYWRIGHT_BASE_URL;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: "html",
  use: {
    baseURL: externalBaseUrl ?? "http://127.0.0.1:4174",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "edge",
      use: { ...devices["Desktop Edge"], channel: "msedge" },
    },
  ],
  webServer: externalBaseUrl
    ? undefined
    : {
        command:
          "node ./node_modules/vite/bin/vite.js --host 127.0.0.1 --port 4174 --mode e2e",
        url: "http://127.0.0.1:4174",
        reuseExistingServer: !process.env.CI,
        env: {
          VITE_USE_MOCK_HEALTH: "true",
          VITE_USE_MOCK_MVP1: "true",
        },
      },
});
