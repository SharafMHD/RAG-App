"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import Swal from "sweetalert2";
import { useParams } from "next/navigation";
import { ArrowLeft, Copy, Eye, FileText, Layers, RefreshCw, Search, Trash2, Upload, X } from "lucide-react";
import {
  adminDeleteDocument,
  adminGetTaskStatus,
  adminListDocumentChunks,
  adminListDocuments,
  adminProcessKnowledgeBase,
  adminUploadProcessDocument,
} from "@/lib/api/rag";
import type { AdminChunkSummary, AdminDocumentSummary, AdminTaskStatusResponse } from "@/lib/api/types";

const STORAGE_KEY = "rag-chat:selected-knowledge-base-id";

export default function KnowledgeBaseDetailPage() {
  const params = useParams<{ knowledgeBaseId: string }>();
  const knowledgeBaseId = params.knowledgeBaseId;
  const [documents, setDocuments] = useState<AdminDocumentSummary[]>([]);
  const [documentPage, setDocumentPage] = useState(1);
  const [documentTotalPages, setDocumentTotalPages] = useState(1);
  const [selectedAsset, setSelectedAsset] = useState<AdminDocumentSummary | null>(null);
  const [chunks, setChunks] = useState<AdminChunkSummary[]>([]);
  const [chunkPage, setChunkPage] = useState(1);
  const [chunkTotalPages, setChunkTotalPages] = useState(1);
  const [chunkQuery, setChunkQuery] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [fileInputKey, setFileInputKey] = useState(0);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [taskStatus, setTaskStatus] = useState<AdminTaskStatusResponse | null>(null);
  const [isLoadingDocuments, setIsLoadingDocuments] = useState(false);
  const [isLoadingChunks, setIsLoadingChunks] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refreshDocuments = useCallback(async () => {
    setIsLoadingDocuments(true);
    setError(null);
    try {
      const response = await adminListDocuments(knowledgeBaseId, documentPage, 12);
      setDocuments(response.documents || []);
      setDocumentTotalPages(Math.max(response.total_pages || 1, 1));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load documents");
    } finally {
      setIsLoadingDocuments(false);
    }
  }, [documentPage, knowledgeBaseId]);

  const refreshChunks = useCallback(async () => {
    if (!selectedAsset) return;
    setIsLoadingChunks(true);
    setError(null);
    try {
      const response = await adminListDocumentChunks(selectedAsset.asset_id, chunkPage, 10);
      setChunks(response.chunks || []);
      setChunkTotalPages(Math.max(response.total_pages || 1, 1));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load chunks");
    } finally {
      setIsLoadingChunks(false);
    }
  }, [chunkPage, selectedAsset]);

  useEffect(() => {
    refreshDocuments();
  }, [refreshDocuments]);

  useEffect(() => {
    refreshChunks();
  }, [refreshChunks]);

  useEffect(() => {
    if (!taskId || taskStatus?.ready) return;
    const interval = window.setInterval(async () => {
      try {
        const status = await adminGetTaskStatus(taskId);
        setTaskStatus(status);
        if (status.ready) refreshDocuments();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Could not poll task status");
      }
    }, 2500);
    return () => window.clearInterval(interval);
  }, [refreshDocuments, taskId, taskStatus?.ready]);

  useEffect(() => {
    if (!notice && !error) return;
    const timeout = window.setTimeout(() => {
      setNotice(null);
      setError(null);
    }, 4500);
    return () => window.clearTimeout(timeout);
  }, [error, notice]);

  function trackTask(nextTaskId: string) {
    setTaskId(nextTaskId);
    setTaskStatus({ status: true, task_id: nextTaskId, state: "PENDING", ready: false, successful: false, failed: false, result: null });
  }

  async function uploadAndProcess(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) return;
    setIsSubmitting(true);
    setNotice(null);
    setError(null);
    try {
      const formData = new FormData();
      formData.set("file", file);
      formData.set("do_reset", "false");
      const response = await adminUploadProcessDocument(knowledgeBaseId, formData);
      trackTask(response.workflow_task_id);
      setFile(null);
      setFileInputKey((current) => current + 1);
      setNotice(`Uploaded ${response.file_name}. Processing started.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not upload document");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function reprocessKb() {
    setIsSubmitting(true);
    setNotice(null);
    setError(null);
    try {
      const response = await adminProcessKnowledgeBase(knowledgeBaseId, { file_id: null, chunk_size: 900, overlap_size: 150, do_reset: true });
      trackTask(response.workflow_task_id);
      setNotice("Knowledge base reprocess started.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not reprocess knowledge base");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function deleteDocument(doc: AdminDocumentSummary) {
    const confirmation = await Swal.fire({
      title: "Delete file?",
      html: `<strong>${doc.file_id}</strong><br/>This deletes the file, all related chunks, and rebuilds/removes vectors for this collection.`,
      icon: "warning",
      showCancelButton: true,
      confirmButtonText: "Delete file",
      cancelButtonText: "Cancel",
      confirmButtonColor: "#dc2626",
      reverseButtons: true,
    });
    if (!confirmation.isConfirmed) return;
    setIsSubmitting(true);
    setNotice(null);
    setError(null);
    try {
      await adminDeleteDocument(doc.asset_id);
      if (selectedAsset?.asset_id === doc.asset_id) {
        setSelectedAsset(null);
        setChunks([]);
      }
      setNotice(`Deleted ${doc.file_id} and related chunks/vectors.`);
      await refreshDocuments();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete document");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function copyChunk(chunk: AdminChunkSummary) {
    await navigator.clipboard.writeText(chunk.chunk_content);
    setNotice(`Copied Chunk ${chunk.chunk_order} text.`);
  }

  const filteredChunks = chunks.filter((chunk) => !chunkQuery.trim() || chunk.chunk_content.toLowerCase().includes(chunkQuery.trim().toLowerCase()));
  const totalChunks = documents.reduce((sum, doc) => sum + doc.chunks_count, 0);

  return (
    <div className="admin-page kb-detail-page">
      <header className="admin-page-header compact">
        <div>
          <h1>Documents & Chunks</h1>
          <p>Manage documents, chunks, and indexing for this collection.</p>
        </div>
        <div className="header-actions">
          <Link className="secondary-button" href="/admin/knowledge-bases"><ArrowLeft size={16} /> Back</Link>
          <Link className="primary-action" href="/" onClick={() => window.localStorage.setItem(STORAGE_KEY, knowledgeBaseId)}>Open Chat</Link>
        </div>
      </header>

      {error ? <div className="toast error"><span>{error}</span><button type="button" onClick={() => setError(null)}><X size={14} /></button></div> : null}
      {notice ? <div className="toast success"><span>{notice}</span><button type="button" onClick={() => setNotice(null)}><X size={14} /></button></div> : null}
      {taskStatus ? <div className={`task-status ${taskStatus.failed ? "failed" : taskStatus.successful ? "success" : "running"}`}><strong>Task {taskStatus.state}</strong><span>{taskStatus.task_id}</span></div> : null}

      <section className="kb-detail-summary">
        <div><FileText size={18} /><strong>{documents.length}</strong><span>documents on this page</span></div>
        <div><Layers size={18} /><strong>{totalChunks}</strong><span>chunks in listed docs</span></div>
        <button className="reprocess-card" type="button" onClick={reprocessKb} disabled={isSubmitting || documents.length === 0}>
          <RefreshCw size={18} />
          <span><strong>Reprocess knowledge base</strong><small>Rebuild chunks and vectors for all documents</small></span>
        </button>
      </section>

      <div className="admin-grid two-columns detail-columns">
        <section className="admin-card">
          <div className="admin-card-header">
            <div><h2>Documents</h2><p>Upload and manage related documents.</p></div>
            <button className="secondary-button" type="button" onClick={refreshDocuments}><RefreshCw size={16} className={isLoadingDocuments ? "spin" : ""} /> Refresh</button>
          </div>

          <form className="upload-strip" onSubmit={uploadAndProcess}>
            <input
              key={fileInputKey}
              id="document-upload"
              type="file"
              accept="application/pdf,text/plain"
              hidden
              onChange={(event) => setFile(event.target.files?.[0] || null)}
            />
            <label className="secondary-button" htmlFor="document-upload"><Upload size={16} /> Choose file</label>
            <span className="muted">{file ? file.name : "No file selected"}</span>
            <button className="primary-action" type="submit" disabled={!file || isSubmitting}>Upload & process</button>
          </form>

          <div className="document-list">
            {documents.length === 0 && !isLoadingDocuments ? <p className="muted">No documents yet. Upload a PDF or TXT file.</p> : null}
            {documents.map((doc) => (
              <article className={selectedAsset?.asset_id === doc.asset_id ? "document-card selected" : "document-card"} key={doc.asset_id}>
                <div className="doc-main"><FileText size={18} /><div><strong>{doc.file_id}</strong><span>{formatBytes(doc.asset_size)} · {doc.chunks_count} chunks</span></div></div>
                <div className="doc-actions">
                  <button type="button" onClick={() => { setSelectedAsset(doc); setChunkPage(1); }}><Eye size={14} /> Chunks</button>
                  <button className="danger-action" type="button" disabled={isSubmitting} onClick={() => deleteDocument(doc)}><Trash2 size={14} /> Delete file</button>
                </div>
              </article>
            ))}
          </div>
          <Pagination page={documentPage} totalPages={documentTotalPages} onPrevious={() => setDocumentPage((p) => Math.max(1, p - 1))} onNext={() => setDocumentPage((p) => p + 1)} />
        </section>

        <section className="admin-card">
          <div className="admin-card-header">
            <div><h2>Chunks</h2><p>{selectedAsset ? selectedAsset.file_id : "Select a document to inspect chunks."}</p></div>
          </div>
          <label className="search-box chunk-search"><Search size={16} /><input value={chunkQuery} onChange={(event) => setChunkQuery(event.target.value)} placeholder="Search loaded chunks..." /></label>
          <div className="chunk-list">
            {!selectedAsset ? <p className="muted">Choose a document from the left panel.</p> : null}
            {selectedAsset && filteredChunks.length === 0 && !isLoadingChunks ? <p className="muted">No chunks found for this document.</p> : null}
            {filteredChunks.map((chunk) => (
              <article className="chunk-card" key={chunk.chunk_id}>
                <header>
                  <strong>Chunk {chunk.chunk_order}</strong>
                  <button type="button" title="Copy chunk text" aria-label={`Copy chunk ${chunk.chunk_order}`} onClick={() => copyChunk(chunk)}>
                    <Copy size={13} /> Copy
                  </button>
                </header>
                <p>{chunk.chunk_content}</p>
                <footer><span>{chunk.chunking_strategy || "strategy n/a"}</span><span>{chunk.embedding_model || "embedding n/a"}</span></footer>
              </article>
            ))}
          </div>
          <Pagination page={chunkPage} totalPages={chunkTotalPages} onPrevious={() => setChunkPage((p) => Math.max(1, p - 1))} onNext={() => setChunkPage((p) => p + 1)} disabled={!selectedAsset} />
        </section>
      </div>
    </div>
  );
}

function Pagination({ page, totalPages, disabled, onPrevious, onNext }: { page: number; totalPages: number; disabled?: boolean; onPrevious: () => void; onNext: () => void }) {
  return <footer className="pagination-bar"><button type="button" disabled={disabled || page <= 1} onClick={onPrevious}>Previous</button><span>Page {page} of {totalPages}</span><button type="button" disabled={disabled || page >= totalPages} onClick={onNext}>Next</button></footer>;
}

function formatBytes(bytes: number) {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / 1024 ** index).toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}
