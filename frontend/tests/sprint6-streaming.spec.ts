import { createServer, type ServerResponse } from "node:http";
import { expect, test } from "@playwright/test";

const API_BASE_URL = "http://127.0.0.1:8000";
const STREAM_SERVER_URL = "http://127.0.0.1:38080/stream";

type Deferred = {
  readonly promise: Promise<void>;
  readonly resolve: () => void;
};

type StreamResponder = (response: ServerResponse) => Promise<void>;

let streamResponder: StreamResponder = async (response) => {
  response.writeHead(503);
  response.end();
};

const streamServer = createServer((request, response) => {
  if (request.method === "OPTIONS") {
    response.writeHead(204, {
      "Access-Control-Allow-Headers": "Content-Type, X-API-Key",
      "Access-Control-Allow-Methods": "POST, OPTIONS",
      "Access-Control-Allow-Origin": "*",
    });
    response.end();
    return;
  }

  void streamResponder(response);
});

function deferred(): Deferred {
  let resolve = (): void => undefined;
  const promise = new Promise<void>((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
}

function startSse(response: ServerResponse): void {
  response.writeHead(200, {
    "Access-Control-Allow-Origin": "*",
    "Cache-Control": "no-cache",
    Connection: "keep-alive",
    "Content-Type": "text/event-stream",
  });
  response.flushHeaders();
}

function sendEvent(response: ServerResponse, event: string, data: unknown): void {
  response.write(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`);
}

const finalResponse = {
  status: true,
  knowledge_base_id: "kb-stream",
  answer: "The final answer replaced provisional tokens.",
  citations: [
    {
      source_id: "source-final",
      rank: 1,
      score: 0.97,
      document_name: "stream-fixture.pdf",
      page_number: 4,
      chunk_id: "chunk-final",
    },
  ],
  source_chunks: [],
  confidence: 0.97,
  retrieval_metadata: {
    strategy: "hybrid",
    requested_top_k: 5,
    returned_count: 1,
    vector_top_k: 5,
    bm25_top_k: 5,
    rerank_top_n: null,
    min_relevance_score: null,
  },
  trace_id: "trace-final",
  message: "ok",
} as const;

test.beforeAll(async () => {
  await new Promise<void>((resolve, reject) => {
    streamServer.once("error", reject);
    streamServer.listen(38080, "127.0.0.1", resolve);
  });
});

test.afterAll(async () => {
  await new Promise<void>((resolve, reject) => {
    streamServer.close((error) => {
      if (error) {
        reject(error);
        return;
      }
      resolve();
    });
  });
});

test.beforeEach(async ({ page }) => {
  streamResponder = async (response) => {
    response.writeHead(503);
    response.end();
  };
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
            knowledge_base_id: "kb-stream",
            knowledge_base_name: "Streaming Knowledge Base",
            description: "Local SSE fixture",
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
  await page.route(`${API_BASE_URL}/api/v1/nlp/index/answer/kb-stream/stream`, async (route) => {
    await route.continue({ url: STREAM_SERVER_URL });
  });
});

test("streams a placeholder and incremental tokens before reconciling the final cited answer", async ({ page }) => {
  // Given
  const releaseFirstToken = deferred();
  const releaseFinal = deferred();
  streamResponder = async (response) => {
    startSse(response);
    await releaseFirstToken.promise;
    sendEvent(response, "token", { content: "Provisional token" });
    await releaseFinal.promise;
    sendEvent(response, "token", { content: " content" });
    sendEvent(response, "final", { response: finalResponse });
    sendEvent(response, "done", {});
    response.end();
  };
  await page.goto("/");
  await page.getByRole("combobox").selectOption("kb-stream");
  const composer = page.getByPlaceholder("Ask anything...");

  // When
  await composer.fill("Stream this answer");
  await composer.press("Enter");

  // Then
  const assistant = page.locator("article.message.assistant");
  await expect(assistant).toContainText("Thinking…");
  await expect(page.locator("article.message.user")).toHaveCount(1);
  await expect(assistant).toHaveCount(1);
  releaseFirstToken.resolve();
  await expect(assistant).toContainText("Provisional token");
  await expect(page.locator(".answer-details")).toHaveCount(0);
  releaseFinal.resolve();
  await expect(assistant).toContainText(finalResponse.answer);
  await expect(assistant).not.toContainText("Provisional token content");
  await expect(page.getByText("stream-fixture.pdf")).toBeVisible();
});

test("renders an in-conversation assistant error without answer details", async ({ page }) => {
  // Given
  streamResponder = async (response) => {
    startSse(response);
    sendEvent(response, "token", { content: "Partial answer" });
    sendEvent(response, "error", { detail: "provider unavailable", message: "Answer streaming failed" });
    sendEvent(response, "done", {});
    response.end();
  };
  await page.goto("/");
  await page.getByRole("combobox").selectOption("kb-stream");

  // When
  await page.getByPlaceholder("Ask anything...").fill("Trigger an error");
  await page.getByRole("button", { name: "Send message" }).click();

  // Then
  const assistant = page.locator("article.message.assistant");
  await expect(assistant.getByRole("alert")).toContainText("Answer streaming failed");
  await expect(assistant.locator(".answer-details")).toHaveCount(0);
  await expect(page.locator("article.message.user")).toHaveCount(1);
});

test("aborts a cleared stream so stale tokens cannot update a new chat", async ({ page }) => {
  // Given
  const releaseStaleToken = deferred();
  const staleConnectionClosed = deferred();
  streamResponder = async (response) => {
    startSse(response);
    response.once("close", staleConnectionClosed.resolve);
    await releaseStaleToken.promise;
    sendEvent(response, "token", { content: "STALE_TOKEN" });
  };
  await page.goto("/");
  await page.getByRole("combobox").selectOption("kb-stream");
  await page.getByPlaceholder("Ask anything...").fill("Old chat");
  await page.getByPlaceholder("Ask anything...").press("Enter");
  await expect(page.locator("article.message.assistant")).toContainText("Thinking…");

  // When
  await page.getByRole("button", { name: "New chat" }).click();
  streamResponder = async (response) => {
    startSse(response);
    sendEvent(response, "final", { response: { ...finalResponse, answer: "Fresh resumed answer." } });
    sendEvent(response, "done", {});
    response.end();
  };
  releaseStaleToken.resolve();
  await staleConnectionClosed.promise;
  await page.getByPlaceholder("Ask anything...").fill("Fresh chat");
  await page.getByPlaceholder("Ask anything...").press("Enter");

  // Then
  await expect(page.locator("article.message.assistant")).toContainText("Fresh resumed answer.");
  await expect(page.locator("article.message.user")).toHaveCount(1);
  await expect(page.getByText("STALE_TOKEN")).toHaveCount(0);
});

test("turns malformed SSE into an assistant error instead of a page crash", async ({ page }) => {
  // Given
  streamResponder = async (response) => {
    startSse(response);
    response.write("event: token\ndata: {broken}\n\n");
    response.end();
  };
  await page.goto("/");
  await page.getByRole("combobox").selectOption("kb-stream");

  // When
  await page.getByPlaceholder("Ask anything...").fill("Malformed stream");
  await page.getByPlaceholder("Ask anything...").press("Enter");

  // Then
  await expect(page.locator("article.message.assistant").getByRole("alert")).toBeVisible();
  await expect(page.locator("main.demo-shell")).toBeVisible();
});

test("renders an assistant error when the stream request fails externally", async ({ page }) => {
  // Given
  streamResponder = async (response) => {
    response.writeHead(503, { "Access-Control-Allow-Origin": "*" });
    response.end("provider offline");
  };
  await page.goto("/");
  await page.getByRole("combobox").selectOption("kb-stream");

  // When
  await page.getByPlaceholder("Ask anything...").fill("External failure");
  await page.getByPlaceholder("Ask anything...").press("Enter");

  // Then
  await expect(page.locator("article.message.assistant").getByRole("alert")).toContainText("status 503");
  await expect(page.locator("article.message.user")).toHaveCount(1);
});
