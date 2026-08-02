import { apiFetch } from "./client";
import type {
  AdminChunkListResponse,
  AdminCreateKnowledgeBaseRequest,
  AdminCreateKnowledgeBaseResponse,
  AdminCreateUploadProcessResponse,
  AdminDeleteDocumentResponse,
  AdminDeleteKnowledgeBaseResponse,
  AdminDocumentListResponse,
  AdminProcessKnowledgeBaseRequest,
  AdminProcessKnowledgeBaseResponse,
  AdminTaskStatusResponse,
  AnswerRequest,
  ChatAnswerResponse,
  FeedbackRequest,
  FeedbackResponse,
  HealthResponse,
  KnowledgeBaseListResponse,
  WelcomeResponse,
} from "./types";

export { streamAnswer } from "./answer-stream";

export async function getWelcome(): Promise<WelcomeResponse> {
  return apiFetch<WelcomeResponse>("/api/v1/welcome", { method: "GET" });
}

export async function generateAnswer(knowledgeBaseId: string, payload: AnswerRequest): Promise<ChatAnswerResponse> {
  return apiFetch<ChatAnswerResponse>(`/api/v1/nlp/index/answer/${knowledgeBaseId}`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function submitAnswerFeedback(
  knowledgeBaseId: string,
  payload: FeedbackRequest,
): Promise<FeedbackResponse> {
  return apiFetch<FeedbackResponse>(
    `/api/v1/nlp/index/answer/${encodeURIComponent(knowledgeBaseId)}/feedback`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

export async function listKnowledgeBases(): Promise<KnowledgeBaseListResponse> {
  return apiFetch<KnowledgeBaseListResponse>("/api/v1/data/knowledge-bases", {
    method: "GET",
  });
}

export async function adminListKnowledgeBases(page = 1, pageSize = 12): Promise<KnowledgeBaseListResponse> {
  return apiFetch<KnowledgeBaseListResponse>(`/api/v1/admin/knowledge-bases?page=${page}&page_size=${pageSize}`, {
    method: "GET",
  });
}

export async function adminCreateKnowledgeBase(payload: AdminCreateKnowledgeBaseRequest): Promise<AdminCreateKnowledgeBaseResponse> {
  return apiFetch<AdminCreateKnowledgeBaseResponse>("/api/v1/admin/knowledge-bases/create", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function adminProcessKnowledgeBase(
  knowledgeBaseId: string,
  payload: AdminProcessKnowledgeBaseRequest,
): Promise<AdminProcessKnowledgeBaseResponse> {
  return apiFetch<AdminProcessKnowledgeBaseResponse>(`/api/v1/admin/knowledge-bases/${knowledgeBaseId}/process`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function adminDeleteKnowledgeBase(knowledgeBaseId: string): Promise<AdminDeleteKnowledgeBaseResponse> {
  return apiFetch<AdminDeleteKnowledgeBaseResponse>(`/api/v1/admin/knowledge-bases/${knowledgeBaseId}`, {
    method: "DELETE",
  });
}

export async function adminCreateUploadProcessKnowledgeBase(formData: FormData): Promise<AdminCreateUploadProcessResponse> {
  return apiFetch<AdminCreateUploadProcessResponse>("/api/v1/admin/knowledge-bases/create-and-process", {
    method: "POST",
    body: formData,
  });
}

export async function adminGetTaskStatus(taskId: string): Promise<AdminTaskStatusResponse> {
  return apiFetch<AdminTaskStatusResponse>(`/api/v1/admin/tasks/${taskId}`, {
    method: "GET",
  });
}

export async function adminListDocuments(knowledgeBaseId: string, page = 1, pageSize = 20): Promise<AdminDocumentListResponse> {
  return apiFetch<AdminDocumentListResponse>(`/api/v1/admin/knowledge-bases/${knowledgeBaseId}/documents?page=${page}&page_size=${pageSize}`, {
    method: "GET",
  });
}

export async function adminUploadProcessDocument(knowledgeBaseId: string, formData: FormData): Promise<AdminCreateUploadProcessResponse> {
  return apiFetch<AdminCreateUploadProcessResponse>(`/api/v1/admin/knowledge-bases/${knowledgeBaseId}/documents/upload-and-process`, {
    method: "POST",
    body: formData,
  });
}

export async function adminListDocumentChunks(assetId: string, page = 1, pageSize = 20): Promise<AdminChunkListResponse> {
  return apiFetch<AdminChunkListResponse>(`/api/v1/admin/documents/${assetId}/chunks?page=${page}&page_size=${pageSize}`, {
    method: "GET",
  });
}

export async function adminDeleteDocument(assetId: string): Promise<AdminDeleteDocumentResponse> {
  return apiFetch<AdminDeleteDocumentResponse>(`/api/v1/admin/documents/${assetId}`, {
    method: "DELETE",
  });
}

export async function getLiveness(): Promise<HealthResponse> {
  return apiFetch<HealthResponse>("/api/v1/health/live", { method: "GET" });
}

export async function getReadiness(): Promise<HealthResponse> {
  return apiFetch<HealthResponse>("/api/v1/health", { method: "GET" });
}
