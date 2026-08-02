import { defineConfig, devices } from "@playwright/test";

const APP_HOST = "127.0.0.1";
const APP_PORT = 3100;
const APP_BASE_URL = `http://${APP_HOST}:${APP_PORT}`;

export default defineConfig({
  testDir: "./tests",
  outputDir: "./test-results",
  fullyParallel: false,
  forbidOnly: true,
  retries: 0,
  workers: 1,
  reporter: [
    ["line"],
    ["json", { outputFile: "playwright-report/results.json" }],
  ],
  timeout: 30_000,
  expect: {
    timeout: 5_000,
  },
  use: {
    baseURL: APP_BASE_URL,
    serviceWorkers: "block",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: {
    command: `pnpm exec next dev --hostname ${APP_HOST} --port ${APP_PORT}`,
    env: {
      NEXT_PUBLIC_API_BASE_URL: "http://127.0.0.1:8000",
      NEXT_PUBLIC_FASTAPI_URL: "https://api.qa.invalid",
      NEXT_PUBLIC_FLOWER_URL: "https://flower.qa.invalid",
      NEXT_PUBLIC_PROMETHEUS_URL: "https://prometheus.qa.invalid",
      NEXT_PUBLIC_GRAFANA_URL: "https://grafana.qa.invalid",
      NEXT_PUBLIC_LANGFUSE_URL: "https://langfuse.qa.invalid",
      NEXT_PUBLIC_POSTGRESQL_URL: "postgresql://postgres.internal:5432/rag_app",
      NEXT_PUBLIC_RABBITMQ_URL: "amqp://rabbitmq.internal:5672",
      NEXT_PUBLIC_CELERY_WORKER_URL: "celery@worker-qa",
      NEXT_PUBLIC_QDRANT_URL: "javascript:alert(1)",
      NEXT_TELEMETRY_DISABLED: "1",
    },
    url: APP_BASE_URL,
    reuseExistingServer: false,
    timeout: 120_000,
    stdout: "pipe",
    stderr: "pipe",
  },
});
