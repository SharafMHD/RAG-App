import { expect, test } from "@playwright/test";

const API_BASE_URL = "http://127.0.0.1:8000";

test.beforeEach(async ({ page }) => {
  await page.route(`${API_BASE_URL}/**`, async (route) => {
    await route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ detail: `Unmocked backend request: ${route.request().url()}` }),
    });
  });
  await page.route(`${API_BASE_URL}/api/v1/welcome`, async (route) => {
    await route.fulfill({
      json: {
        message: "ready",
        app_name: "RAG Chat",
        version: "test",
        environment: "browser-test",
        generation_model: "mock-model",
      },
    });
  });
});

test("renders a cited answer when backend responses are mocked", async ({ page }) => {
  // Given
  await page.route(`${API_BASE_URL}/api/v1/data/knowledge-bases`, async (route) => {
    await route.fulfill({
      json: {
        status: true,
        knowledge_bases: [
          {
            knowledge_base_id: "kb-smoke",
            knowledge_base_name: "Smoke Test Knowledge Base",
            description: "Local browser fixture",
            owner: "qa",
          },
        ],
        page: 1,
        page_size: 1,
        total_pages: 1,
        total_count: 1,
        message: "ok",
      },
    });
  });
  await page.route(`${API_BASE_URL}/api/v1/nlp/index/answer/kb-smoke/stream`, async (route) => {
    const response = {
      status: true,
      knowledge_base_id: "kb-smoke",
      answer: "The mocked browser flow returned a cited answer.",
      citations: [
        {
          source_id: "source-1",
          rank: 1,
          score: 0.98,
          document_name: "fixture.pdf",
          page_number: 2,
          chunk_id: "chunk-1",
        },
      ],
      source_chunks: [],
      confidence: 0.98,
      retrieval_metadata: {
        strategy: "hybrid",
        requested_top_k: 5,
        returned_count: 1,
        vector_top_k: 5,
        bm25_top_k: 5,
        rerank_top_n: null,
        min_relevance_score: null,
      },
      trace_id: "trace-smoke",
      message: "ok",
    } as const;
    await route.fulfill({
      contentType: "text/event-stream",
      body: `event: final\ndata: ${JSON.stringify({ response })}\n\nevent: done\ndata: {}\n\n`,
    });
  });

  // When
  await page.goto("/");
  await page.getByRole("combobox").selectOption("kb-smoke");
  await page.getByPlaceholder("Ask anything...").fill("Which source supports this answer?");
  await page.getByPlaceholder("Ask anything...").press("Enter");

  // Then
  await expect(page.locator("article.message.assistant")).toContainText("The mocked browser flow returned a cited answer.");
  await expect(page.getByText("fixture.pdf")).toBeVisible();
});

test("surfaces a handled error when the knowledge-base mock is malformed", async ({ page }) => {
  // Given
  await page.route(`${API_BASE_URL}/api/v1/data/knowledge-bases`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: "{",
    });
  });

  // When
  await page.goto("/");

  // Then
  await expect(page.getByText(/Could not load KB list:/)).toBeVisible();
  await expect(page.getByPlaceholder("Knowledge base ID")).toBeVisible();
});
