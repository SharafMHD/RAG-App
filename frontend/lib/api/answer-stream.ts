import { ApiError, getApiBaseUrl } from "./client";
import type {
  AnswerRequest,
  AnswerStreamEvent,
  ChatAnswerResponse,
  Citation,
  RetrievalMetadata,
  SourceChunk,
} from "./types";

export type AnswerStreamParserErrorCode =
  | "invalid_frame"
  | "invalid_payload"
  | "malformed_json"
  | "unsupported_event";

export class AnswerStreamParserError extends Error {
  readonly name = "AnswerStreamParserError";
  readonly code: AnswerStreamParserErrorCode;
  readonly frame: string;

  constructor(code: AnswerStreamParserErrorCode, frame: string, options?: ErrorOptions) {
    super(`Invalid answer stream frame: ${code}`, options);
    this.code = code;
    this.frame = frame;
  }
}

export type AnswerStreamOptions = {
  readonly signal?: AbortSignal;
};

function isRecord(value: unknown): value is Readonly<Record<string, unknown>> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isUnknownArray(value: unknown): value is unknown[] {
  return Array.isArray(value);
}

function isNullableNumber(value: unknown): value is number | null {
  return value === null || typeof value === "number";
}

function isNullableString(value: unknown): value is string | null {
  return value === null || typeof value === "string";
}

function isCitation(value: unknown): value is Citation {
  return (
    isRecord(value) &&
    typeof value.source_id === "string" &&
    typeof value.rank === "number" &&
    isNullableNumber(value.score) &&
    isNullableString(value.document_name) &&
    isNullableNumber(value.page_number) &&
    isNullableString(value.chunk_id)
  );
}

function isSourceChunk(value: unknown): value is SourceChunk {
  return (
    isRecord(value) &&
    typeof value.source_id === "string" &&
    typeof value.rank === "number" &&
    typeof value.text === "string" &&
    isNullableNumber(value.score) &&
    isRecord(value.metadata)
  );
}

function isOptionalNullableString(record: Readonly<Record<string, unknown>>, key: string): boolean {
  return !(key in record) || isNullableString(record[key]);
}

function isRetrievalMetadata(value: unknown): value is RetrievalMetadata {
  return (
    isRecord(value) &&
    typeof value.strategy === "string" &&
    typeof value.requested_top_k === "number" &&
    typeof value.returned_count === "number" &&
    isNullableNumber(value.vector_top_k) &&
    isNullableNumber(value.bm25_top_k) &&
    isNullableNumber(value.rerank_top_n) &&
    isNullableNumber(value.min_relevance_score) &&
    isOptionalNullableString(value, "prompt_name") &&
    isOptionalNullableString(value, "prompt_version") &&
    isOptionalNullableString(value, "prompt_source")
  );
}

function isChatAnswerResponse(value: unknown): value is ChatAnswerResponse {
  return (
    isRecord(value) &&
    typeof value.status === "boolean" &&
    typeof value.knowledge_base_id === "string" &&
    typeof value.answer === "string" &&
    isUnknownArray(value.citations) &&
    value.citations.every(isCitation) &&
    isUnknownArray(value.source_chunks) &&
    value.source_chunks.every(isSourceChunk) &&
    isNullableNumber(value.confidence) &&
    isRetrievalMetadata(value.retrieval_metadata) &&
    typeof value.trace_id === "string" &&
    typeof value.message === "string"
  );
}

function isAnswerStreamEventName(value: string): value is AnswerStreamEvent["event"] {
  return value === "token" || value === "final" || value === "error" || value === "done";
}

function assertNever(value: never, frame: string): never {
  throw new AnswerStreamParserError("unsupported_event", frame, { cause: value });
}

function parseFrame(frame: string): AnswerStreamEvent {
  let eventName: string | undefined;
  const dataLines: string[] = [];

  for (const line of frame.split(/\r?\n/)) {
    if (line.startsWith("event:")) {
      eventName = line.slice("event:".length).trimStart();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice("data:".length).trimStart());
    }
  }

  if (eventName === undefined || dataLines.length === 0) {
    throw new AnswerStreamParserError("invalid_frame", frame);
  }
  if (!isAnswerStreamEventName(eventName)) {
    throw new AnswerStreamParserError("unsupported_event", frame);
  }

  let data: unknown;
  try {
    data = JSON.parse(dataLines.join("\n"));
  } catch (error) {
    if (error instanceof SyntaxError) {
      throw new AnswerStreamParserError("malformed_json", frame, { cause: error });
    }
    throw error;
  }

  switch (eventName) {
    case "token":
      if (isRecord(data) && typeof data.content === "string" && data.content.length > 0) {
        return { event: "token", data: { content: data.content } };
      }
      throw new AnswerStreamParserError("invalid_payload", frame);
    case "final":
      if (isRecord(data) && isChatAnswerResponse(data.response)) {
        return { event: "final", data: { response: data.response } };
      }
      throw new AnswerStreamParserError("invalid_payload", frame);
    case "error":
      if (
        isRecord(data) &&
        typeof data.detail === "string" &&
        data.detail.length > 0 &&
        typeof data.message === "string" &&
        data.message.length > 0
      ) {
        return { event: "error", data: { detail: data.detail, message: data.message } };
      }
      throw new AnswerStreamParserError("invalid_payload", frame);
    case "done":
      if (isRecord(data) && Object.keys(data).length === 0) {
        return { event: "done", data: {} };
      }
      throw new AnswerStreamParserError("invalid_payload", frame);
    default:
      return assertNever(eventName, frame);
  }
}

export async function* parseAnswerStream(
  body: ReadableStream<Uint8Array>,
  signal?: AbortSignal,
): AsyncGenerator<AnswerStreamEvent, void, undefined> {
  signal?.throwIfAborted();
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  const cancelRead = (): void => {
    void reader.cancel(signal?.reason);
  };

  signal?.addEventListener("abort", cancelRead, { once: true });

  try {
    while (true) {
      const result = await reader.read();
      signal?.throwIfAborted();
      if (result.done) {
        buffer += decoder.decode();
        break;
      }

      buffer += decoder.decode(result.value, { stream: true });
      let frameBoundary = /\r?\n\r?\n/.exec(buffer);
      while (frameBoundary !== null) {
        const frame = buffer.slice(0, frameBoundary.index);
        buffer = buffer.slice(frameBoundary.index + frameBoundary[0].length);
        if (frame.trim().length > 0) {
          yield parseFrame(frame);
        }
        frameBoundary = /\r?\n\r?\n/.exec(buffer);
      }
    }

    if (buffer.trim().length > 0) {
      yield parseFrame(buffer);
    }
  } finally {
    signal?.removeEventListener("abort", cancelRead);
    reader.releaseLock();
  }
}

export async function* streamAnswer(
  knowledgeBaseId: string,
  payload: AnswerRequest,
  options: AnswerStreamOptions = {},
): AsyncGenerator<AnswerStreamEvent, void, undefined> {
  const headers = new Headers({
    Accept: "text/event-stream",
    "Content-Type": "application/json",
  });
  const apiKey = process.env.NEXT_PUBLIC_API_KEY;
  if (apiKey) {
    headers.set("X-API-Key", apiKey);
  }

  const response = await fetch(
    `${getApiBaseUrl()}/api/v1/nlp/index/answer/${encodeURIComponent(knowledgeBaseId)}/stream`,
    {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
      signal: options.signal,
    },
  );

  if (!response.ok) {
    const details = await response.text();
    throw new ApiError(`Request failed with status ${response.status}`, response.status, details);
  }
  if (response.body === null) {
    throw new ApiError("Streaming response did not include a body", response.status);
  }

  yield* parseAnswerStream(response.body, options.signal);
}
