import { expect, test, type Page } from "@playwright/test";
import type { ChatAnswerResponse, FeedbackRating } from "@/lib/api/types";

const API_BASE_URL = "http://127.0.0.1:8000";
const KNOWLEDGE_BASE_ID = "kb-feedback";
const FEEDBACK_URL = `${API_BASE_URL}/api/v1/nlp/index/answer/${KNOWLEDGE_BASE_ID}/feedback`;

type Deferred = {
  readonly promise: Promise<void>;
  readonly resolve: () => void;
};

const answerResponse = {
  status: true,
  knowledge_base_id: KNOWLEDGE_BASE_ID,
  answer: "The final answer is ready for feedback.",
  citations: [
    {
      source_id: "source-feedback",
      rank: 1,
      score: 0.96,
      document_name: "feedback-fixture.pdf",
      page_number: 3,
      chunk_id: "chunk-feedback",
    },
  ],
  source_chunks: [
    {
      source_id: "source-feedback",
      rank: 1,
      text: "A source snapshot sent with the feedback.",
      score: 0.96,
      metadata: { page: 3 },
    },
  ],
  confidence: 0.96,
  retrieval_metadata: {
    strategy: "hybrid",
    requested_top_k: 5,
    returned_count: 1,
    vector_top_k: 5,
    bm25_top_k: 5,
    rerank_top_n: null,
    min_relevance_score: null,
  },
  trace_id: "trace-feedback",
  message: "ok",
} satisfies ChatAnswerResponse;

function deferred(): Deferred {
  let resolve = (): void => undefined;
  const promise = new Promise<void>((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
}

async function installBaseRoutes(page: Page): Promise<void> {
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
            knowledge_base_name: "Feedback Knowledge Base",
            description: "Feedback browser fixture",
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
}

async function renderCompleteAnswer(page: Page, question = "Was this answer useful?"): Promise<void> {
  await page.route(`${API_BASE_URL}/api/v1/nlp/index/answer/${KNOWLEDGE_BASE_ID}/stream`, async (route) => {
    await route.fulfill({
      contentType: "text/event-stream",
      body: `event: final\ndata: ${JSON.stringify({ response: answerResponse })}\n\nevent: done\ndata: {}\n\n`,
    });
  });
  await page.goto("/");
  await page.getByRole("combobox").selectOption(KNOWLEDGE_BASE_ID);
  await page.getByPlaceholder("Ask anything...").fill(question);
  await page.getByPlaceholder("Ask anything...").press("Enter");
  await expect(page.getByRole("group", { name: "Rate this answer" })).toBeVisible();
}

function feedbackResponse(rating: FeedbackRating, comment: string | null) {
  return {
    status: true,
    trace_id: answerResponse.trace_id,
    rating,
    comment,
    langfuse_status: "sent",
    message: "Feedback saved",
  } as const;
}

test.beforeEach(async ({ page }) => {
  await installBaseRoutes(page);
});

test("sends an optional comment and complete answer snapshots before showing saved feedback", async ({ page }) => {
  // Given
  const releaseResponse = deferred();
  let feedbackPayload: unknown;
  await page.route(FEEDBACK_URL, async (route) => {
    feedbackPayload = route.request().postDataJSON();
    await releaseResponse.promise;
    await route.fulfill({ json: feedbackResponse("thumbs_up", "The citation was useful.") });
  });
  await renderCompleteAnswer(page);
  await page.getByRole("button", { name: "Add a comment" }).click();
  await page.getByLabel("Feedback comment").fill("The citation was useful.");

  // When
  await page.getByRole("button", { name: "Helpful", exact: true }).click();

  // Then
  await expect(page.getByRole("status")).toContainText("Saving feedback");
  releaseResponse.resolve();
  await expect(page.getByRole("status")).toContainText("Feedback saved");
  expect(feedbackPayload).toEqual({
    trace_id: answerResponse.trace_id,
    knowledge_base_id: KNOWLEDGE_BASE_ID,
    rating: "thumbs_up",
    comment: "The citation was useful.",
    question: "Was this answer useful?",
    answer: answerResponse.answer,
    citations: answerResponse.citations,
    source_chunks: answerResponse.source_chunks,
  });
  await expect(page.getByRole("button", { name: "Helpful", exact: true })).toHaveAttribute("aria-pressed", "true");
});

test("keeps a failed vote unsaved and retries it successfully", async ({ page }) => {
  // Given
  let attempts = 0;
  await page.route(FEEDBACK_URL, async (route) => {
    attempts += 1;
    if (attempts === 1) {
      await route.fulfill({ status: 500, json: { detail: "Feedback storage unavailable" } });
      return;
    }
    await route.fulfill({ json: feedbackResponse("thumbs_down", null) });
  });
  await renderCompleteAnswer(page);

  // When
  await page.getByRole("button", { name: "Not helpful" }).click();

  // Then
  await expect(page.locator(".answer-feedback").getByRole("alert")).toContainText("Feedback storage unavailable");
  await expect(page.getByRole("button", { name: "Not helpful" })).toHaveAttribute("aria-pressed", "false");
  await page.getByRole("button", { name: "Retry feedback" }).click();
  await expect(page.getByRole("status")).toContainText("Feedback saved");
  await expect(page.getByRole("button", { name: "Not helpful" })).toHaveAttribute("aria-pressed", "true");
  expect(attempts).toBe(2);
});

test("replaces a saved vote when the other rating is selected", async ({ page }) => {
  // Given
  const ratings: FeedbackRating[] = [];
  await page.route(FEEDBACK_URL, async (route) => {
    const payload: { readonly rating: FeedbackRating } = route.request().postDataJSON();
    ratings.push(payload.rating);
    await route.fulfill({ json: feedbackResponse(payload.rating, null) });
  });
  await renderCompleteAnswer(page);
  const helpful = page.getByRole("button", { name: "Helpful", exact: true });
  const notHelpful = page.getByRole("button", { name: "Not helpful" });
  await helpful.click();
  await expect(helpful).toHaveAttribute("aria-pressed", "true");

  // When
  await notHelpful.click();

  // Then
  await expect(notHelpful).toHaveAttribute("aria-pressed", "true");
  await expect(helpful).toHaveAttribute("aria-pressed", "false");
  expect(ratings).toEqual(["thumbs_up", "thumbs_down"]);
});

test("does not show feedback controls for provisional or error messages", async ({ page }) => {
  // Given
  const releaseError = deferred();
  await page.route(`${API_BASE_URL}/api/v1/nlp/index/answer/${KNOWLEDGE_BASE_ID}/stream`, async (route) => {
    await releaseError.promise;
    await route.fulfill({
      contentType: "text/event-stream",
      body: "event: error\ndata: {\"detail\":\"provider unavailable\",\"message\":\"Answer streaming failed\"}\n\nevent: done\ndata: {}\n\n",
    });
  });
  await page.goto("/");
  await page.getByRole("combobox").selectOption(KNOWLEDGE_BASE_ID);

  // When
  await page.getByPlaceholder("Ask anything...").fill("Trigger an error");
  await page.getByPlaceholder("Ask anything...").press("Enter");

  // Then
  await expect(page.locator("article.message.assistant")).toContainText("Thinking…");
  await expect(page.getByRole("group", { name: "Rate this answer" })).toHaveCount(0);
  releaseError.resolve();
  await expect(page.locator("article.message.assistant").getByRole("alert")).toContainText("Answer streaming failed");
  await expect(page.getByRole("group", { name: "Rate this answer" })).toHaveCount(0);
});
