"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import Swal from "sweetalert2";
import {
  CheckCircle2,
  Database,
  ExternalLink,
  FileText,
  Layers,
  Loader2,
  Plus,
  RefreshCw,
  Search,
  Trash2,
  TriangleAlert,
  X,
} from "lucide-react";
import { adminCreateKnowledgeBase, adminDeleteKnowledgeBase, adminListKnowledgeBases, adminProcessKnowledgeBase } from "@/lib/api/rag";
import type { KnowledgeBaseSummary } from "@/lib/api/types";

const STORAGE_KEY = "rag-chat:selected-knowledge-base-id";
const PAGE_SIZE = 12;

type Toast = { type: "success" | "error"; message: string } | null;

function statusMeta(status?: string, documents = 0, chunks = 0) {
  const normalized = status || (chunks > 0 ? "ready" : documents > 0 ? "needs_processing" : "empty");
  if (normalized === "ready") return { label: "Ready", className: "ready", icon: CheckCircle2 };
  if (normalized === "needs_processing") return { label: "Needs processing", className: "warning", icon: TriangleAlert };
  if (normalized === "processing") return { label: "Processing", className: "processing", icon: Loader2 };
  if (normalized === "failed") return { label: "Failed", className: "failed", icon: TriangleAlert };
  return { label: "Empty", className: "empty", icon: Database };
}

export default function AdminKnowledgeBasesPage() {
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBaseSummary[]>([]);
  const [selectedKnowledgeBaseId, setSelectedKnowledgeBaseId] = useState("");
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalCount, setTotalCount] = useState(0);
  const [query, setQuery] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [processingId, setProcessingId] = useState<string | null>(null);
  const [toast, setToast] = useState<Toast>(null);
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [createName, setCreateName] = useState("");
  const [createDescription, setCreateDescription] = useState("");
  const [createOwner, setCreateOwner] = useState("admin");
  const [isCreating, setIsCreating] = useState(false);

  const refreshKnowledgeBases = useCallback(async () => {
    setIsLoading(true);
    try {
      const response = await adminListKnowledgeBases(page, PAGE_SIZE);
      setKnowledgeBases(response.knowledge_bases || []);
      setTotalPages(Math.max(response.total_pages || 1, 1));
      setTotalCount(response.total_count || 0);
    } catch (err) {
      setToast({ type: "error", message: err instanceof Error ? err.message : "Could not load knowledge bases" });
    } finally {
      setIsLoading(false);
    }
  }, [page]);

  const selectKnowledgeBase = useCallback((knowledgeBaseId: string) => {
    setSelectedKnowledgeBaseId(knowledgeBaseId);
    window.localStorage.setItem(STORAGE_KEY, knowledgeBaseId);
  }, []);

  useEffect(() => {
    setSelectedKnowledgeBaseId(window.localStorage.getItem(STORAGE_KEY) || "");
    refreshKnowledgeBases();
  }, [refreshKnowledgeBases]);

  useEffect(() => {
    if (!toast) return;
    const timeout = window.setTimeout(() => setToast(null), 4500);
    return () => window.clearTimeout(timeout);
  }, [toast]);

  const filteredKnowledgeBases = useMemo(() => {
    const text = query.trim().toLowerCase();
    if (!text) return knowledgeBases;
    return knowledgeBases.filter((kb) =>
      [kb.knowledge_base_name, kb.description, kb.owner, kb.knowledge_base_id]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(text)),
    );
  }, [knowledgeBases, query]);

  async function createKnowledgeBase(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsCreating(true);
    try {
      const response = await adminCreateKnowledgeBase({
        knowledge_base_name: createName,
        description: createDescription || undefined,
        owner: createOwner || "admin",
      });
      selectKnowledgeBase(response.knowledge_base_id);
      setToast({ type: "success", message: `Created ${response.knowledge_base_name}. Open Manage to upload documents.` });
      setCreateName("");
      setCreateDescription("");
      setCreateOwner("admin");
      setIsCreateOpen(false);
      await refreshKnowledgeBases();
    } catch (err) {
      setToast({ type: "error", message: err instanceof Error ? err.message : "Could not create knowledge base" });
    } finally {
      setIsCreating(false);
    }
  }

  async function reprocessKnowledgeBase(kb: KnowledgeBaseSummary) {
    const documentsCount = kb.documents_count || 0;
    if (documentsCount <= 0) return;
    setProcessingId(kb.knowledge_base_id);
    try {
      const response = await adminProcessKnowledgeBase(kb.knowledge_base_id, {
        file_id: null,
        chunk_size: 900,
        overlap_size: 150,
        do_reset: true,
      });
      setToast({ type: "success", message: `Reprocess started for ${kb.knowledge_base_name}. Task ${response.workflow_task_id}` });
    } catch (err) {
      setToast({ type: "error", message: err instanceof Error ? err.message : "Could not start reprocess task" });
    } finally {
      setProcessingId(null);
    }
  }

  async function deleteKnowledgeBase(kb: KnowledgeBaseSummary) {
    const confirmation = await Swal.fire({
      title: `Delete ${kb.knowledge_base_name}?`,
      text: "This will permanently delete the collection, all related documents, chunks, uploaded files, and vector index.",
      icon: "warning",
      showCancelButton: true,
      confirmButtonText: "Delete",
      cancelButtonText: "Cancel",
      confirmButtonColor: "#dc2626",
      reverseButtons: true,
    });
    if (!confirmation.isConfirmed) return;
    setProcessingId(kb.knowledge_base_id);
    try {
      await adminDeleteKnowledgeBase(kb.knowledge_base_id);
      if (selectedKnowledgeBaseId === kb.knowledge_base_id) {
        setSelectedKnowledgeBaseId("");
        window.localStorage.removeItem(STORAGE_KEY);
      }
      setToast({ type: "success", message: `Deleted ${kb.knowledge_base_name} and all related documents/chunks.` });
      await refreshKnowledgeBases();
    } catch (err) {
      setToast({ type: "error", message: err instanceof Error ? err.message : "Could not delete knowledge base" });
    } finally {
      setProcessingId(null);
    }
  }

  return (
    <div className="admin-page kb-admin-page">
      {toast ? <div className={`toast ${toast.type}`}><span>{toast.message}</span><button type="button" onClick={() => setToast(null)}><X size={14} /></button></div> : null}

      <header className="admin-page-header compact">
        <div>
          <h1>Knowledge Bases</h1>
          <p>Manage document collections used by the chat assistant.</p>
        </div>
        <div className="header-actions">
          <button className="primary-action" type="button" onClick={() => setIsCreateOpen(true)}><Plus size={16} /> Create KB</button>
          <button className="secondary-button" type="button" onClick={refreshKnowledgeBases} disabled={isLoading}>
            <RefreshCw size={16} className={isLoading ? "spin" : ""} /> Refresh
          </button>
        </div>
      </header>

      <section className="kb-toolbar">
        <label className="search-box">
          <Search size={16} />
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search knowledge bases..." />
        </label>
        <p>Showing {filteredKnowledgeBases.length} of {totalCount} knowledge bases</p>
      </section>

      <section className="kb-tile-grid" aria-busy={isLoading}>
        {isLoading ? Array.from({ length: 6 }).map((_, index) => <div className="kb-tile skeleton" key={index} />) : null}
        {!isLoading && filteredKnowledgeBases.length === 0 ? (
          <div className="empty-kb-state">
            <Database size={34} />
            <h2>No knowledge bases found</h2>
            <p>Create your first knowledge base, then open Manage to upload documents and process them.</p>
            <button className="primary-action" type="button" onClick={() => setIsCreateOpen(true)}><Plus size={16} /> Create knowledge base</button>
          </div>
        ) : null}
        {!isLoading && filteredKnowledgeBases.map((kb) => {
          const documentsCount = kb.documents_count || 0;
          const chunksCount = kb.chunks_count || 0;
          const meta = statusMeta(kb.kb_status, documentsCount, chunksCount);
          const StatusIcon = meta.icon;
          const canReprocess = documentsCount > 0;
          return (
            <article className="kb-tile" key={kb.knowledge_base_id}>
              <div className="kb-tile-header">
                <div className="kb-icon"><Database size={28} /></div>
                <span className={`status-badge ${meta.className}`}><StatusIcon size={16} /> {meta.label}</span>
              </div>
              <h2>{kb.knowledge_base_name}</h2>
              <p>{kb.description || "No description provided."}</p>
              <div className="kb-metrics">
                <span><FileText size={17} /> {documentsCount} documents</span>
                <span><Layers size={17} /> {chunksCount} chunks</span>
              </div>
              <div className="kb-tile-actions">
                <Link href={`/admin/knowledge-bases/${kb.knowledge_base_id}`} title="Manage knowledge base" aria-label={`Manage ${kb.knowledge_base_name}`}>
                  <Database size={16} />
                </Link>
                <Link href="/" onClick={() => selectKnowledgeBase(kb.knowledge_base_id)} title="Open chat" aria-label={`Open chat for ${kb.knowledge_base_name}`}>
                  <ExternalLink size={16} />
                </Link>
                {canReprocess ? (
                  <button className="reprocess-action" type="button" title="Reprocess knowledge base" aria-label={`Reprocess ${kb.knowledge_base_name}`} disabled={processingId === kb.knowledge_base_id} onClick={() => reprocessKnowledgeBase(kb)}>
                    <RefreshCw size={16} className={processingId === kb.knowledge_base_id ? "spin" : ""} />
                  </button>
                ) : null}
                <button className="danger-action" type="button" title="Delete knowledge base" aria-label={`Delete ${kb.knowledge_base_name}`} disabled={processingId === kb.knowledge_base_id} onClick={() => deleteKnowledgeBase(kb)}>
                  <Trash2 size={16} />
                </button>
              </div>
              {!canReprocess ? <small className="tile-hint">No documents yet — open Manage to upload files.</small> : null}
            </article>
          );
        })}
      </section>

      <footer className="pagination-bar">
        <button type="button" disabled={page <= 1 || isLoading} onClick={() => setPage((current) => Math.max(1, current - 1))}>Previous</button>
        <span>Page {page} of {totalPages}</span>
        <button type="button" disabled={page >= totalPages || isLoading} onClick={() => setPage((current) => current + 1)}>Next</button>
      </footer>

      {isCreateOpen ? (
        <div className="modal-backdrop" role="presentation" onMouseDown={() => setIsCreateOpen(false)}>
          <section className="modal-card" role="dialog" aria-modal="true" aria-labelledby="create-kb-title" onMouseDown={(event) => event.stopPropagation()}>
            <header className="modal-header">
              <div>
                <h2 id="create-kb-title">Create knowledge base</h2>
                <p>Create the collection first. You can upload files and process them from Manage.</p>
              </div>
              <button className="icon-button" type="button" onClick={() => setIsCreateOpen(false)}><X size={18} /></button>
            </header>
            <form className="modal-form" onSubmit={createKnowledgeBase}>
              <label>Knowledge base name<input value={createName} onChange={(event) => setCreateName(event.target.value)} required autoFocus /></label>
              <label>Description<input value={createDescription} onChange={(event) => setCreateDescription(event.target.value)} /></label>
              <label>Owner<input value={createOwner} onChange={(event) => setCreateOwner(event.target.value)} /></label>
              <button className="primary-action full-width" type="submit" disabled={isCreating}>{isCreating ? "Creating..." : "Create KB"}</button>
            </form>
          </section>
        </div>
      ) : null}
    </div>
  );
}
