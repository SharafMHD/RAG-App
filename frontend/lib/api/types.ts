export type RetrievalStrategy = "vector" | "bm25" | "hybrid";

export type WelcomeResponse = {
  readonly message: string;
  readonly app_name: string;
  readonly version: string;
  readonly environment: string;
  readonly generation_model: string | null;
};

export type Citation = {
  source_id: string;
  rank: number;
  score: number | null;
  document_name: string | null;
  page_number: number | null;
  chunk_id: string | null;
};

export type SourceChunk = {
  source_id: string;
  rank: number;
  text: string;
  score: number | null;
  metadata: Record<string, unknown>;
};

export type RetrievalMetadata = {
  strategy: string;
  requested_top_k: number;
  returned_count: number;
  vector_top_k: number | null;
  bm25_top_k: number | null;
  rerank_top_n: number | null;
  min_relevance_score: number | null;
  prompt_name?: string | null;
  prompt_version?: string | null;
  prompt_source?: string | null;
};

export type ChatAnswerResponse = {
  status: boolean;
  knowledge_base_id: string;
  answer: string;
  citations: Citation[];
  source_chunks: SourceChunk[];
  confidence: number | null;
  retrieval_metadata: RetrievalMetadata;
  trace_id: string;
  message: string;
};

export type AnswerRequest = {
  text: string;
  limit?: number;
  strategy?: RetrievalStrategy;
  preprocessing?: QueryPreprocessingRequest | null;
};

export type QueryPreprocessingRequest = {
  readonly expand?: boolean;
  readonly decompose?: boolean;
  readonly max_generated_queries?: number | null;
};

export type FeedbackRating = "thumbs_up" | "thumbs_down";
export type FeedbackDeliveryStatus = "disabled" | "sent" | "failed";

export type FeedbackRequest = {
  readonly trace_id: string;
  readonly knowledge_base_id: string;
  readonly rating: FeedbackRating;
  readonly comment?: string | null;
  readonly question: string;
  readonly answer: string;
  readonly citations: readonly Citation[];
  readonly source_chunks: readonly SourceChunk[];
};

export type FeedbackResponse = {
  readonly status: boolean;
  readonly trace_id: string;
  readonly rating: FeedbackRating;
  readonly comment: string | null;
  readonly langfuse_status: FeedbackDeliveryStatus;
  readonly message: string;
};

export type AnswerStreamTokenPayload = {
  readonly content: string;
};

export type AnswerStreamFinalPayload = {
  readonly response: ChatAnswerResponse;
};

export type AnswerStreamErrorPayload = {
  readonly detail: string;
  readonly message: string;
};

export type AnswerStreamDonePayload = Record<string, never>;

// This is the user-facing SSE answer stream; NDJSON is reserved for backend data and chunk pipelines.
export type AnswerStreamEvent =
  | { readonly event: "token"; readonly data: AnswerStreamTokenPayload }
  | { readonly event: "final"; readonly data: AnswerStreamFinalPayload }
  | { readonly event: "error"; readonly data: AnswerStreamErrorPayload }
  | { readonly event: "done"; readonly data: AnswerStreamDonePayload };

export type KnowledgeBaseSummary = {
  knowledge_base_id: string;
  knowledge_base_name: string;
  description: string | null;
  owner: string | null;
  documents_count?: number;
  chunks_count?: number;
  kb_status?: "empty" | "needs_processing" | "ready" | "processing" | "failed" | string;
};

export type KnowledgeBaseListResponse = {
  status: boolean;
  knowledge_bases: KnowledgeBaseSummary[];
  page: number;
  page_size: number;
  total_pages: number;
  total_count: number;
  message: string;
};

export type AdminCreateKnowledgeBaseRequest = {
  knowledge_base_name: string;
  description?: string;
  owner?: string;
};

export type AdminCreateKnowledgeBaseResponse = KnowledgeBaseSummary & {
  status: boolean;
  message: string;
};

export type AdminProcessKnowledgeBaseRequest = {
  file_id?: string | null;
  chunk_size?: number;
  overlap_size?: number;
  do_reset?: boolean;
};

export type AdminProcessKnowledgeBaseResponse = {
  status: boolean;
  knowledge_base_id: string;
  workflow_task_id: string;
  message: string;
};

export type AdminDeleteKnowledgeBaseResponse = {
  status: boolean;
  knowledge_base_id: string;
  deleted_documents_and_chunks: boolean;
  deleted_upload_dir: boolean;
  deleted_vector_collection: boolean;
  message: string;
};

export type AdminCreateUploadProcessResponse = AdminCreateKnowledgeBaseResponse & {
  file_name: string;
  file_id: string;
  asset_id: string;
  workflow_task_id: string;
};

export type AdminTaskStatusResponse = {
  status: boolean;
  task_id: string;
  state: string;
  ready: boolean;
  successful: boolean;
  failed: boolean;
  result: unknown;
};

export type HealthResponse = {
  status: string;
  checks?: Record<string, string>;
};

export type AdminDocumentSummary = {
  asset_id: string;
  file_id: string;
  asset_type: string;
  asset_size: number;
  description: string | null;
  created_at: string | null;
  chunks_count: number;
};

export type AdminDocumentListResponse = {
  status: boolean;
  knowledge_base_id: string;
  documents: AdminDocumentSummary[];
  page: number;
  page_size: number;
  total_pages: number;
  total_count: number;
};

export type AdminDeleteDocumentResponse = {
  status: boolean;
  asset_id: string;
  knowledge_base_id: string;
  deleted_file: boolean;
  deleted_chunks: boolean;
  vector_collection_rebuilt: boolean;
  vector_collection_deleted: boolean;
  message: string;
};

export type AdminChunkSummary = {
  chunk_id: string;
  chunk_asset_id: string;
  chunk_knowledge_base_id: string;
  chunk_order: number;
  chunk_content: string;
  chunk_metadata: Record<string, unknown>;
  chunking_strategy: string | null;
  embedding_model: string | null;
  content_hash: string | null;
  parent_chunk_id: string | null;
};

export type AdminChunkListResponse = {
  status: boolean;
  asset_id: string;
  chunks: AdminChunkSummary[];
  page: number;
  page_size: number;
  total_pages: number;
  total_count: number;
};
