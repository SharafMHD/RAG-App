import { expect, test, type Page } from "@playwright/test";
import type { ChatAnswerResponse } from "@/lib/api/types";

const API_BASE_URL = "http://127.0.0.1:8000";
const KNOWLEDGE_BASE_ID = "kb-evidence";

const evidenceResponse = {
  status: true,
  knowledge_base_id: KNOWLEDGE_BASE_ID,
  answer: `**Policy details** [source_1], **operations** [source_2], and unresolved [source_404].

| Period | Qualified service | Retirement age |
|---|---:|---:|
| 1 Dec 2023 - 30 Nov 2024 | 25 years [source_1] | 45 years |
| 1 Dec 2042 - 30 Nov 2043 | 25 years | 54.5 years [source_2] |`,
  citations: [
    {
      source_id: "source_1",
      rank: 1,
      score: 0.982,
      document_name: "policy-handbook.pdf",
      page_number: 12,
      chunk_id: "chunk-policy-12",
    },
    {
      source_id: "source_2",
      rank: 2,
      score: 0.913,
      document_name: "دليل-العمليات.pdf",
      page_number: null,
      chunk_id: "chunk-operations",
    },
  ],
  source_chunks: [
    {
      source_id: "source_1",
      rank: 1,
      text: "A concise policy excerpt that supports the answer.",
      score: 0.982,
      metadata: { internal_label: "must remain hidden" },
    },
    {
      source_id: "source_2",
      rank: 2,
      text: "مقتطف موجز يدعم الإجابة.",
      score: 0.913,
      metadata: {},
    },
  ],
  confidence: 0.941,
  retrieval_metadata: {
    strategy: "hybrid",
    requested_top_k: 5,
    returned_count: 2,
    vector_top_k: 5,
    bm25_top_k: 5,
    rerank_top_n: null,
    min_relevance_score: null,
  },
  trace_id: "trace-evidence",
  message: "ok",
} satisfies ChatAnswerResponse;

async function installAnswerFixture(page: Page, response: ChatAnswerResponse): Promise<void> {
  await page.route(`${API_BASE_URL}/**`, async (route) => {
    await route.fulfill({ status: 503, json: { detail: "Unmocked backend request" } });
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
  await page.route(`${API_BASE_URL}/api/v1/data/knowledge-bases`, async (route) => {
    await route.fulfill({
      json: {
        status: true,
        knowledge_bases: [{
          knowledge_base_id: KNOWLEDGE_BASE_ID,
          knowledge_base_name: "Evidence Knowledge Base",
          description: "Evidence UI fixture",
          owner: "qa",
        }],
        page: 1,
        page_size: 1,
        total_pages: 1,
        total_count: 1,
        message: "ok",
      },
    });
  });
  await page.route(`${API_BASE_URL}/api/v1/nlp/index/answer/${KNOWLEDGE_BASE_ID}/stream`, async (route) => {
    await route.fulfill({
      contentType: "text/event-stream",
      body: `event: final\ndata: ${JSON.stringify({ response })}\n\nevent: done\ndata: {}\n\n`,
    });
  });
}

async function renderAnswer(page: Page, response: ChatAnswerResponse): Promise<void> {
  await installAnswerFixture(page, response);
  await page.goto("/");
  await page.getByRole("combobox").selectOption(KNOWLEDGE_BASE_ID);
  await page.getByPlaceholder("Ask anything...").fill("Show the supporting evidence");
  await page.getByPlaceholder("Ask anything...").press("Enter");
  await expect(page.locator(".cited-answer")).toBeVisible();
}

test("renders only resolved markers as inline citation controls", async ({ page }) => {
  // Given
  await renderAnswer(page, evidenceResponse);
  const answer = page.locator(".cited-answer-text");

  // When
  const resolvedMarkers = answer.locator(".citation-marker");

  // Then
  await expect(answer).toContainText("Policy details [source_1], operations [source_2], and unresolved [source_404].");
  await expect(answer).not.toContainText("**");
  await expect(answer.locator("strong")).toHaveText(["Policy details", "operations"]);
  await expect(resolvedMarkers).toHaveCount(4);
  await expect(answer).toContainText("[source_404]");
  await expect(answer.getByRole("table")).toBeVisible();
  await expect(answer.locator("th")).toHaveText(["Period", "Qualified service", "Retirement age"]);
  await expect(answer.locator("tbody tr")).toHaveCount(2);
  await expect(answer.locator("tbody tr").first()).toContainText("25 years [source_1]");
  await expect(page.locator(".citation-disclosure")).toBeHidden();
  await expect(page.locator(".answer-details, .meta-grid, .citation-list, .source-list")).toHaveCount(0);
});

test("reveals useful source details and keeps retrieval diagnostics hidden", async ({ page }) => {
  // Given
  await renderAnswer(page, evidenceResponse);
  const marker = page.getByRole("button", { name: "View source_1: policy-handbook.pdf" }).first();

  // When
  await marker.click();

  // Then
  await expect(marker).toHaveAttribute("aria-expanded", "true");
  const disclosure = page.locator(".citation-disclosure");
  await expect(disclosure).toContainText("policy-handbook.pdf");
  await expect(disclosure).toContainText("Page 12");
  await expect(disclosure).toContainText("A concise policy excerpt that supports the answer.");
  await expect(disclosure).not.toContainText(/0\.982|trace-evidence|hybrid|chunk-policy|must remain hidden/i);
});

test("keeps one citation open and supports keyboard activation", async ({ page }) => {
  // Given
  await renderAnswer(page, evidenceResponse);
  const first = page.getByRole("button", { name: "View source_1: policy-handbook.pdf" }).first();
  const second = page.getByRole("button", { name: "View source_2: دليل-العمليات.pdf" }).first();
  await first.focus();
  await page.keyboard.press("Enter");

  // When
  await second.focus();
  await page.keyboard.press("Space");

  // Then
  await expect(first).toHaveAttribute("aria-expanded", "false");
  await expect(second).toHaveAttribute("aria-expanded", "true");
  await expect(second).toBeFocused();
  await expect(page.locator(".citation-disclosure")).toContainText("دليل-العمليات.pdf");
});

test("preserves RTL direction and wraps citation content on mobile", async ({ page }) => {
  // Given
  await page.setViewportSize({ width: 375, height: 900 });
  const rtlResponse = {
    ...evidenceResponse,
    answer: "توضح **السياسة** التفاصيل [source_2] دون تغيير **اتجاه النص.",
  } satisfies ChatAnswerResponse;

  // When
  await renderAnswer(page, rtlResponse);
  await page.getByRole("button", { name: "View source_2: دليل-العمليات.pdf" }).click();

  // Then
  const assistantMessage = page.locator("article.message.assistant");
  await expect(assistantMessage).toHaveAttribute("dir", "rtl");
  await expect(assistantMessage.locator(".cited-answer-text strong")).toHaveText("السياسة");
  await expect(assistantMessage).toContainText("دون تغيير **اتجاه النص.");
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBe(0);
});
