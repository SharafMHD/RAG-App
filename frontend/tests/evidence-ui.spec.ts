import { expect, test, type Page } from "@playwright/test";
import type { ChatAnswerResponse } from "@/lib/api/types";

const API_BASE_URL = "http://127.0.0.1:8000";
const KNOWLEDGE_BASE_ID = "kb-evidence";
const LONG_TOKEN = "source_".repeat(70);
const RTL_FILENAME = "دليل-السياسات.pdf";

const evidenceResponse = {
  status: true,
  knowledge_base_id: KNOWLEDGE_BASE_ID,
  answer: "The evidence is grouped by citation and retrieved source.",
  citations: [
    {
      source_id: "source-policy",
      rank: 1,
      score: 0.982,
      document_name: "policy-handbook.pdf",
      page_number: 12,
      chunk_id: "chunk-policy-12",
    },
    {
      source_id: "source-operations",
      rank: 2,
      score: 0.913,
      document_name: "operations-guide.pdf",
      page_number: 7,
      chunk_id: "chunk-operations-7",
    },
    {
      source_id: LONG_TOKEN,
      rank: 3,
      score: 0.877,
      document_name: `${LONG_TOKEN}.pdf`,
      page_number: null,
      chunk_id: `chunk_${LONG_TOKEN}`,
    },
  ],
  source_chunks: [
    {
      source_id: "source-policy",
      rank: 1,
      text: "A concise source excerpt that supports the answer.",
      score: 0.982,
      metadata: {},
    },
    {
      source_id: LONG_TOKEN,
      rank: 2,
      text: `Untrusted text ${LONG_TOKEN} must wrap without widening the conversation.`,
      score: 0.877,
      metadata: {},
    },
  ],
  confidence: 0.941,
  retrieval_metadata: {
    strategy: "hybrid",
    requested_top_k: 5,
    returned_count: 3,
    vector_top_k: 5,
    bm25_top_k: 5,
    rerank_top_n: null,
    min_relevance_score: null,
  },
  trace_id: `trace_${LONG_TOKEN}`,
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
        knowledge_bases: [
          {
            knowledge_base_id: KNOWLEDGE_BASE_ID,
            knowledge_base_name: "Evidence Knowledge Base",
            description: "Evidence UI fixture",
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
  await expect(page.locator(".answer-details")).toBeVisible();
}

for (const width of [375, 768, 1280] as const) {
  test(`keeps three citations and long source evidence readable at ${width}px`, async ({ page }) => {
    // Given
    await page.setViewportSize({ width, height: 900 });

    // When
    await renderAnswer(page, evidenceResponse);

    // Then
    await expect(page.locator(".evidence-chip")).toHaveCount(4);
    await expect(page.locator(".citation-card")).toHaveCount(3);
    const sourceDisclosure = page.locator(".evidence-disclosure").filter({ hasText: "Retrieved source chunks" });
    await expect(sourceDisclosure).not.toHaveAttribute("open", "");
    await sourceDisclosure.click();
    await expect(page.locator(".source-card")).toHaveCount(2);
    await expect(sourceDisclosure.locator("ol.source-list > li")).toHaveCount(2);
    const overflow = await page.evaluate(() => ({
      document: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      evidence: Array.from(document.querySelectorAll<HTMLElement>(".answer-details"))
        .some((element) => element.scrollWidth > element.clientWidth),
    }));
    expect(overflow.document).toBe(0);
    expect(overflow.evidence).toBe(false);
    if (width === 375) {
      const traceValue = page.locator(".trace-chip dd");
      const traceDimensions = await traceValue.evaluate((element) => ({
        clientHeight: element.clientHeight,
        scrollHeight: element.scrollHeight,
      }));
      expect(traceDimensions.clientHeight).toBeLessThan(80);
      expect(traceDimensions.scrollHeight).toBeGreaterThan(traceDimensions.clientHeight);
      await expect(traceValue).toHaveAttribute("tabindex", "0");
    }
  });
}

test("shows a composed no-answer and no-citation state", async ({ page }) => {
  // Given
  const emptyResponse = {
    ...evidenceResponse,
    answer: "",
    citations: [],
    source_chunks: [],
    confidence: null,
    retrieval_metadata: { ...evidenceResponse.retrieval_metadata, returned_count: 0 },
  } satisfies ChatAnswerResponse;

  // When
  await renderAnswer(page, emptyResponse);

  // Then
  await expect(page.locator(".answer-evidence-empty")).toBeVisible();
  await expect(page.locator(".citation-card, .source-card")).toHaveCount(0);
  await expect(page.locator(".answer-details summary")).toHaveCount(0);
});

test("keeps retrieved chunks discoverable when an answer has no citations", async ({ page }) => {
  // Given
  const noCitationResponse = {
    ...evidenceResponse,
    citations: [],
    source_chunks: evidenceResponse.source_chunks.slice(0, 1),
    retrieval_metadata: { ...evidenceResponse.retrieval_metadata, returned_count: 1 },
  } satisfies ChatAnswerResponse;

  // When
  await renderAnswer(page, noCitationResponse);
  const sourceDisclosure = page.locator(".evidence-disclosure");
  await sourceDisclosure.click();

  // Then
  await expect(page.locator(".answer-evidence-empty")).toBeVisible();
  await expect(page.locator(".citation-card")).toHaveCount(0);
  await expect(page.locator(".source-card")).toHaveCount(1);
});

test("inherits RTL reading direction and supports keyboard traversal of disclosures", async ({ page }) => {
  // Given
  await page.setViewportSize({ width: 768, height: 900 });
  const rtlResponse = {
    ...evidenceResponse,
    answer: "توضح الإجابة الأدلة والمصادر المرتبطة بها بوضوح.",
    citations: evidenceResponse.citations.map((citation, index) => ({
      ...citation,
      document_name: index === 0 ? RTL_FILENAME : citation.document_name,
    })),
  } satisfies ChatAnswerResponse;

  // When
  await renderAnswer(page, rtlResponse);
  const citationSummary = page.locator(".evidence-disclosure > summary").first();
  const sourceSummary = page.locator(".evidence-disclosure > summary").last();
  await citationSummary.focus();

  // Then
  await expect(page.locator("article.message.assistant")).toHaveAttribute("dir", "rtl");
  await expect(page.locator(".answer-details")).toHaveCSS("direction", "rtl");
  await expect(page.locator(".evidence-chip").first()).toHaveCSS("direction", "ltr");
  await expect(page.locator(".citation-metadata > div").first()).toHaveCSS("direction", "ltr");
  const filename = page.locator(".citation-card header strong").first();
  await expect(filename).toHaveText(RTL_FILENAME);
  const filenameReadsStemBeforeExtension = await filename.evaluate((element) => {
    const textNode = document.createTreeWalker(element, NodeFilter.SHOW_TEXT).nextNode();
    if (!(textNode instanceof Text)) return false;
    const extensionStart = textNode.data.lastIndexOf(".");
    if (extensionStart < 1) return false;

    const stemRange = document.createRange();
    stemRange.setStart(textNode, 0);
    stemRange.setEnd(textNode, extensionStart);
    const extensionRange = document.createRange();
    extensionRange.setStart(textNode, extensionStart);
    extensionRange.setEnd(textNode, textNode.length);
    return extensionRange.getBoundingClientRect().left > stemRange.getBoundingClientRect().left;
  });
  expect(filenameReadsStemBeforeExtension).toBe(true);
  await expect(citationSummary).toHaveCSS("direction", "ltr");
  await expect(citationSummary).toBeFocused();
  await expect(citationSummary).toHaveCSS("outline-style", "solid");
  await page.keyboard.press("Tab");
  await expect(sourceSummary).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(sourceSummary.locator("..")).toHaveAttribute("open", "");
});
