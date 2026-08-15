import assert from "node:assert/strict";
import test from "node:test";

const { ApiError, apiFetch }: typeof import("./client") = await import("./client" + ".ts");

test("uses a JSON error body's message field as the ApiError message", async (context) => {
  // Given
  const errorBody = {
    status: false,
    file_name: "20260313 - Pension Guide_AR.pdf",
    file_type: "application/pdf",
    file_size: 16283051,
    message: "file size exceeds the allowed limit",
  };
  context.mock.method(globalThis, "fetch", async (): Promise<Response> => {
    return new Response(JSON.stringify(errorBody), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  });

  // When / Then
  await assert.rejects(apiFetch("/api/v1/admin/upload"), (error: unknown) => {
    if (!(error instanceof ApiError)) {
      return false;
    }
    assert.equal(error.status, 400);
    assert.equal(error.message, errorBody.message);
    assert.deepEqual(error.details, errorBody);
    return true;
  });
});

test("falls back to the HTTP status when a JSON error body has no descriptive field", async (context) => {
  // Given
  context.mock.method(globalThis, "fetch", async (): Promise<Response> => {
    return new Response(JSON.stringify({ status: false }), {
      status: 502,
      headers: { "Content-Type": "application/json" },
    });
  });

  // When / Then
  await assert.rejects(apiFetch("/api/v1/admin/upload"), (error: unknown) => {
    return error instanceof ApiError && error.status === 502 && error.message === "Request failed with status 502";
  });
});
