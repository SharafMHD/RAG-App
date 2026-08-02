import assert from "node:assert/strict";
import test from "node:test";

import { AnswerStreamParserError, parseAnswerStream, streamAnswer } from "./answer-stream";
import { ApiError } from "./client";
import type { AnswerStreamEvent } from "./types";

const encoder = new TextEncoder();

const finalResponse = {
  status: true,
  knowledge_base_id: "kb-1",
  answer: "hello",
  citations: [],
  source_chunks: [],
  confidence: 0.9,
  retrieval_metadata: {
    strategy: "hybrid",
    requested_top_k: 5,
    returned_count: 1,
    vector_top_k: 5,
    bm25_top_k: 5,
    rerank_top_n: null,
    min_relevance_score: null,
  },
  trace_id: "trace-1",
  message: "ok",
} as const;

function streamFromChunks(chunks: readonly string[]): ReadableStream<Uint8Array> {
  return new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(encoder.encode(chunk));
      }
      controller.close();
    },
  });
}

async function collectEvents(stream: AsyncIterable<AnswerStreamEvent>): Promise<readonly AnswerStreamEvent[]> {
  const events: AnswerStreamEvent[] = [];
  for await (const event of stream) {
    events.push(event);
  }
  return events;
}

test("parses split and batched SSE frames with a typed final response", async () => {
  // Given
  const finalFrame = `event: final\ndata: ${JSON.stringify({ response: finalResponse })}\n\n`;
  const body = streamFromChunks([
    "event: token\ndata: {\"content\":\"hel",
    "\"}\n\nevent: token\ndata: {\"content\":\"lo\"}\n\n" + finalFrame.slice(0, 24),
    finalFrame.slice(24) + "event: done\ndata: {}\n\n",
  ]);

  // When
  const events = await collectEvents(parseAnswerStream(body));

  // Then
  assert.deepEqual(
    events.map((event) => event.event),
    ["token", "token", "final", "done"],
  );
  const firstEvent = events[0];
  const finalEvent = events[2];
  if (firstEvent?.event !== "token" || finalEvent?.event !== "final") {
    assert.fail("Expected token and final events at their protocol positions");
  }
  assert.equal(firstEvent.data.content, "hel");
  assert.equal(finalEvent.data.response.answer, "hello");
});

test("rejects malformed JSON with a typed parser error", async () => {
  // Given
  const body = streamFromChunks(["event: token\ndata: {broken}\n\n"]);

  // When / Then
  await assert.rejects(
    collectEvents(parseAnswerStream(body)),
    (error: unknown) => error instanceof AnswerStreamParserError && error.code === "malformed_json",
  );
});

test("aborts a pending read and a fresh parser can resume independently", async () => {
  // Given
  const abortController = new AbortController();
  let cancelReason: unknown;
  const pendingBody = new ReadableStream<Uint8Array>({
    cancel(reason: unknown) {
      cancelReason = reason;
    },
  });
  const pendingEvents = collectEvents(parseAnswerStream(pendingBody, abortController.signal));
  const abortReason = new DOMException("manual abort", "AbortError");

  // When
  abortController.abort(abortReason);

  // Then
  await assert.rejects(pendingEvents, (error: unknown) => error === abortReason);
  assert.equal(cancelReason, abortReason);
  const resumed = await collectEvents(parseAnswerStream(streamFromChunks(["event: done\ndata: {}\n\n"])));
  assert.deepEqual(resumed.map((event) => event.event), ["done"]);
});

test("releases the reader lock when parsing starts with an aborted signal", async () => {
  // Given
  const body = streamFromChunks(["event: done\ndata: {}\n\n"]);
  const abortController = new AbortController();
  const abortReason = new DOMException("already aborted", "AbortError");
  abortController.abort(abortReason);

  // When / Then
  await assert.rejects(
    collectEvents(parseAnswerStream(body, abortController.signal)),
    (error: unknown) => error === abortReason,
  );
  assert.equal(body.locked, false, "pre-aborted parsing must not retain the reader lock");
});

test("releases the reader lock when a consumer exits iteration early", async () => {
  // Given
  const body = streamFromChunks([
    "event: token\ndata: {\"content\":\"first\"}\n\nevent: token\ndata: {\"content\":\"second\"}\n\n",
  ]);
  const events = parseAnswerStream(body);

  // When
  const first = await events.next();
  await events.return(undefined);

  // Then
  assert.equal(first.value?.event, "token");
  assert.equal(body.locked, false, "early consumer exit must release the reader lock");
});

test("posts the answer request with the configured API key", async (context) => {
  // Given
  const previousApiKey = process.env.NEXT_PUBLIC_API_KEY;
  process.env.NEXT_PUBLIC_API_KEY = "test-key";
  let capturedUrl: string | URL | Request | undefined;
  let capturedInit: RequestInit | undefined;
  context.mock.method(globalThis, "fetch", async (url: string | URL | Request, init?: RequestInit): Promise<Response> => {
    capturedUrl = url;
    capturedInit = init;
    return new Response(streamFromChunks(["event: done\ndata: {}\n\n"]), {
      status: 200,
      headers: { "Content-Type": "text/event-stream" },
    });
  });

  try {
    // When
    const events = await collectEvents(streamAnswer("kb 1", { text: "question", limit: 3 }));

    // Then
    if (capturedInit === undefined) {
      assert.fail("Expected fetch request options");
    }
    const headers = new Headers(capturedInit.headers);
    assert.equal(String(capturedUrl), "http://localhost:8000/api/v1/nlp/index/answer/kb%201/stream");
    assert.equal(capturedInit.method, "POST");
    assert.equal(capturedInit.body, JSON.stringify({ text: "question", limit: 3 }));
    assert.equal(headers.get("Content-Type"), "application/json");
    assert.equal(headers.get("Accept"), "text/event-stream");
    assert.equal(headers.get("X-API-Key"), "test-key");
    assert.deepEqual(events.map((event) => event.event), ["done"]);
  } finally {
    if (previousApiKey === undefined) {
      delete process.env.NEXT_PUBLIC_API_KEY;
    } else {
      process.env.NEXT_PUBLIC_API_KEY = previousApiKey;
    }
  }
});

test("surfaces an HTTP failure as ApiError", async (context) => {
  // Given
  context.mock.method(globalThis, "fetch", async (): Promise<Response> => new Response("unavailable", { status: 503 }));

  // When / Then
  await assert.rejects(collectEvents(streamAnswer("kb-1", { text: "question" })), (error: unknown) => {
    return error instanceof ApiError && error.status === 503 && error.details === "unavailable";
  });
});

test("rejects a misleading successful response without a stream body", async (context) => {
  // Given
  context.mock.method(globalThis, "fetch", async (): Promise<Response> => new Response(null, { status: 200 }));

  // When / Then
  await assert.rejects(collectEvents(streamAnswer("kb-1", { text: "question" })), (error: unknown) => {
    return error instanceof ApiError && error.status === 200;
  });
});
