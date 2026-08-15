const DEFAULT_API_BASE_URL = "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  details: unknown;

  constructor(message: string, status: number, details?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.details = details;
  }
}

export function getApiBaseUrl(): string {
  return (process.env.NEXT_PUBLIC_API_BASE_URL || DEFAULT_API_BASE_URL).replace(/\/$/, "");
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function extractErrorMessage(body: unknown): string | undefined {
  if (typeof body === "string") {
    const message = body.trim();
    return message.length > 0 ? message : undefined;
  }
  if (!isRecord(body)) {
    return undefined;
  }
  for (const field of ["detail", "message", "error"] as const) {
    const value = body[field];
    if (typeof value === "string") {
      const message = value.trim();
      if (message.length > 0) {
        return message;
      }
    }
  }
  return undefined;
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const apiKey = process.env.NEXT_PUBLIC_API_KEY;
  const headers = new Headers(init.headers);

  if (!headers.has("Content-Type") && init.body && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (apiKey) {
    headers.set("X-API-Key", apiKey);
  }

  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    ...init,
    headers,
  });

  const contentType = response.headers.get("content-type") || "";
  const body = contentType.includes("application/json") ? await response.json() : await response.text();

  if (!response.ok) {
    const message = extractErrorMessage(body) || `Request failed with status ${response.status}`;
    throw new ApiError(message, response.status, body);
  }

  return body as T;
}
