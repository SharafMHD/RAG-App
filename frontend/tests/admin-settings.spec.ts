import { expect, test } from "@playwright/test";

const API_BASE_URL = "http://127.0.0.1:8000";

test.beforeEach(async ({ page }) => {
  await page.route(`${API_BASE_URL}/**`, async (route) => {
    await route.fulfill({
      json: { status: "ok", checks: { database: "ok" } },
    });
  });
});

test("renders configured HTTP service URLs as safe external links", async ({ page }) => {
  // Given
  const linkedServices = [
    ["FastAPI", "https://api.qa.invalid/"],
    ["Flower", "https://flower.qa.invalid/"],
    ["Prometheus", "https://prometheus.qa.invalid/"],
    ["Grafana", "https://grafana.qa.invalid/"],
    ["Langfuse", "https://langfuse.qa.invalid/"],
  ] as const;

  // When
  await page.goto("/admin/settings");

  // Then
  for (const [service, href] of linkedServices) {
    const row = page.locator(".settings-list > div").filter({ hasText: service });
    const link = row.getByRole("link", { name: href });
    await expect(link).toHaveAttribute("href", href);
    await expect(link).toHaveAttribute("target", "_blank");
    await expect(link).toHaveAttribute("rel", "noopener noreferrer");
  }
});

test("renders non-HTTP and missing service config without invalid hrefs", async ({ page }) => {
  // Given
  const textServices = ["PostgreSQL", "RabbitMQ", "Celery worker", "Qdrant"] as const;

  // When
  await page.goto("/admin/settings");

  // Then
  const serviceCard = page.getByRole("heading", { name: "Required services" }).locator("..");
  await expect(serviceCard.locator(".settings-list > div")).toHaveCount(10);

  for (const service of textServices) {
    await expect(serviceCard.locator(".settings-list > div").filter({ hasText: service }).getByRole("link")).toHaveCount(0);
  }

  const missingRedis = serviceCard.locator(".settings-list > div").filter({ hasText: "Redis" });
  await expect(missingRedis.getByText("Not configured", { exact: true })).toBeVisible();
  await expect(missingRedis.getByRole("link")).toHaveCount(0);
});
