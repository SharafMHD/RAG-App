"use client";

import { FormEvent, useEffect, useState } from "react";
import {
  adminCreateKnowledgeBase,
  adminCreateUploadProcessKnowledgeBase,
  adminGetTaskStatus,
  adminProcessKnowledgeBase,
} from "@/lib/api/rag";
import type { AdminTaskStatusResponse } from "@/lib/api/types";

type Props = {
  selectedKnowledgeBaseId: string;
  onKnowledgeBaseCreated: (knowledgeBaseId: string) => void;
  onRefreshKnowledgeBases: () => void;
};

export function AdminPanel({ selectedKnowledgeBaseId, onKnowledgeBaseCreated, onRefreshKnowledgeBases }: Props) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [owner, setOwner] = useState("admin");
  const [file, setFile] = useState<File | null>(null);
  const [fileInputKey, setFileInputKey] = useState(0);
  const [processKbId, setProcessKbId] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [taskStatus, setTaskStatus] = useState<AdminTaskStatusResponse | null>(null);

  useEffect(() => {
    if (!taskId || taskStatus?.ready) return;

    const interval = window.setInterval(async () => {
      try {
        const status = await adminGetTaskStatus(taskId);
        setTaskStatus(status);
        if (status.ready) {
          onRefreshKnowledgeBases();
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Could not poll task status");
      }
    }, 2500);

    return () => window.clearInterval(interval);
  }, [onRefreshKnowledgeBases, taskId, taskStatus?.ready]);

  function trackTask(nextTaskId: string) {
    setTaskId(nextTaskId);
    setTaskStatus({
      status: true,
      task_id: nextTaskId,
      state: "PENDING",
      ready: false,
      successful: false,
      failed: false,
      result: null,
    });
  }

  async function runAdminAction(action: () => Promise<string>) {
    setIsSubmitting(true);
    setResult(null);
    setError(null);
    try {
      const message = await action();
      setResult(message);
      onRefreshKnowledgeBases();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Admin request failed");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function onCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await runAdminAction(async () => {
      const response = await adminCreateKnowledgeBase({
        knowledge_base_name: name,
        description: description || undefined,
        owner: owner || "admin",
      });
      onKnowledgeBaseCreated(response.knowledge_base_id);
      setName("");
      setDescription("");
      return `Created KB ${response.knowledge_base_name}`;
    });
  }

  async function onCreateUploadProcess(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) {
      setError("Choose a file first");
      return;
    }
    await runAdminAction(async () => {
      const formData = new FormData();
      formData.set("knowledge_base_name", name);
      formData.set("description", description);
      formData.set("owner", owner || "admin");
      formData.set("do_reset", "true");
      formData.set("file", file);
      const response = await adminCreateUploadProcessKnowledgeBase(formData);
      onKnowledgeBaseCreated(response.knowledge_base_id);
      trackTask(response.workflow_task_id);
      setName("");
      setDescription("");
      setFile(null);
      setFileInputKey((current) => current + 1);
      return `Created, uploaded, and started processing. Workflow ${response.workflow_task_id}`;
    });
  }

  async function onProcessExisting(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const kbId = processKbId.trim() || selectedKnowledgeBaseId.trim();
    if (!kbId) {
      setError("Select or paste a knowledge base ID first");
      return;
    }
    await runAdminAction(async () => {
      const response = await adminProcessKnowledgeBase(kbId, {
        file_id: null,
        chunk_size: 900,
        overlap_size: 150,
        do_reset: true,
      });
      trackTask(response.workflow_task_id);
      return `Started processing/indexing. Workflow ${response.workflow_task_id}`;
    });
  }

  return (
    <section className="admin-panel">
      <p>No auth or permissions for now. Use this to create, upload, and process knowledge bases.</p>

      <form onSubmit={onCreate} className="admin-form">
        <strong>Create KB</strong>
        <input placeholder="Knowledge base name" value={name} onChange={(event) => setName(event.target.value)} required />
        <input placeholder="Description" value={description} onChange={(event) => setDescription(event.target.value)} />
        <input placeholder="Owner" value={owner} onChange={(event) => setOwner(event.target.value)} />
        <button type="submit" disabled={isSubmitting}>Create</button>
      </form>

      <form onSubmit={onCreateUploadProcess} className="admin-form">
        <strong>Create + Upload + Process</strong>
        <input placeholder="Knowledge base name" value={name} onChange={(event) => setName(event.target.value)} required />
        <input key={fileInputKey} type="file" accept="application/pdf,text/plain" onChange={(event) => setFile(event.target.files?.[0] || null)} required />
        <button type="submit" disabled={isSubmitting}>Create and process</button>
      </form>

      <form onSubmit={onProcessExisting} className="admin-form">
        <strong>Process current KB</strong>
        <input
          placeholder={selectedKnowledgeBaseId || "Knowledge base ID"}
          value={processKbId}
          onChange={(event) => setProcessKbId(event.target.value)}
        />
        <button type="submit" disabled={isSubmitting}>Process + index</button>
      </form>

      {taskStatus ? (
        <div className={`task-status ${taskStatus.failed ? "failed" : taskStatus.successful ? "success" : "running"}`}>
          <strong>Task {taskStatus.state}</strong>
          <span>{taskStatus.task_id}</span>
          {!taskStatus.ready ? <small>Polling every 2.5s. Keep Celery worker running.</small> : null}
        </div>
      ) : null}
      {result ? <div className="success-box">{result}</div> : null}
      {error ? <div className="error-box compact">{error}</div> : null}
    </section>
  );
}
