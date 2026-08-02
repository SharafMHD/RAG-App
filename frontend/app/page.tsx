"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ArrowUp, Cpu, Globe2, MessageSquare, PanelLeft, Settings, SquarePen, Trash2 } from "lucide-react";
import { ChatMessage } from "@/components/chat-message";
import { getWelcome, listKnowledgeBases, streamAnswer } from "@/lib/api/rag";
import { applyAnswerStreamEvent, assertNever, type ChatMessage as ChatMessageState } from "@/lib/chat-state";
import type { KnowledgeBaseSummary, RetrievalStrategy } from "@/lib/api/types";

const STORAGE_KEY = "rag-chat:selected-knowledge-base-id";
const STRATEGY_KEY = "rag-chat:default-strategy";
const TOP_K_KEY = "rag-chat:default-top-k";
const EXAMPLES = [
  "What are the advantages of using this knowledge base?",
  "Write a cited summary from the selected document",
  "Help me understand the main obligations",
  "What does the document say about responsibilities?",
];

function makeId(): string {
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export default function ChatPage() {
  const [knowledgeBaseId, setKnowledgeBaseId] = useState("");
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBaseSummary[]>([]);
  const [kbError, setKbError] = useState<string | null>(null);
  const [isLoadingKnowledgeBases, setIsLoadingKnowledgeBases] = useState(false);
  const [question, setQuestion] = useState("");
  const [limit, setLimit] = useState(5);
  const [strategy, setStrategy] = useState<RetrievalStrategy>("hybrid");
  const [generationModel, setGenerationModel] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessageState[]>([]);
  const [isAnswering, setIsAnswering] = useState(false);
  const activeStream = useRef<AbortController | null>(null);

  const canSend = useMemo(() => knowledgeBaseId.trim().length > 0 && question.trim().length > 0 && !isAnswering, [knowledgeBaseId, question, isAnswering]);

  const updateKnowledgeBaseId = useCallback((value: string) => {
    setKnowledgeBaseId(value);
    if (typeof window !== "undefined") {
      window.localStorage.setItem(STORAGE_KEY, value);
    }
  }, []);

  const refreshKnowledgeBases = useCallback(async () => {
    setIsLoadingKnowledgeBases(true);
    setKbError(null);
    try {
      const response = await listKnowledgeBases();
      setKnowledgeBases(response.knowledge_bases || []);
    } catch (error) {
      setKnowledgeBases([]);
      setKbError(error instanceof Error ? error.message : "Unknown error");
    } finally {
      setIsLoadingKnowledgeBases(false);
    }
  }, []);

  useEffect(() => {
    const saved = typeof window !== "undefined" ? window.localStorage.getItem(STORAGE_KEY) : null;
    const savedStrategy = window.localStorage.getItem(STRATEGY_KEY) as RetrievalStrategy | null;
    const savedTopK = Number(window.localStorage.getItem(TOP_K_KEY) || 5);
    if (savedStrategy) setStrategy(savedStrategy);
    if (Number.isFinite(savedTopK)) setLimit(savedTopK);
    updateKnowledgeBaseId(saved || process.env.NEXT_PUBLIC_DEFAULT_KNOWLEDGE_BASE_ID || "");
    refreshKnowledgeBases();
    getWelcome().then(
      (response) => setGenerationModel(response.generation_model),
      () => setGenerationModel(null),
    );
  }, [refreshKnowledgeBases, updateKnowledgeBaseId]);

  useEffect(() => {
    return () => activeStream.current?.abort();
  }, []);

  const clearChat = useCallback(() => {
    activeStream.current?.abort();
    activeStream.current = null;
    setIsAnswering(false);
    setMessages([]);
  }, []);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = question.trim();
    const selectedKnowledgeBaseId = knowledgeBaseId.trim();
    if (!text || !selectedKnowledgeBaseId || isAnswering) return;

    activeStream.current?.abort();
    const abortController = new AbortController();
    const userMessageId = makeId();
    const assistantMessageId = makeId();
    activeStream.current = abortController;
    setIsAnswering(true);
    setQuestion("");
    setMessages((current) => [
      ...current,
      { id: userMessageId, kind: "user", content: text },
      { id: assistantMessageId, kind: "assistant_streaming", content: "", question: text },
    ]);

    try {
      for await (const streamEvent of streamAnswer(
        selectedKnowledgeBaseId,
        { text, limit, strategy },
        { signal: abortController.signal },
      )) {
        if (activeStream.current !== abortController) return;
        switch (streamEvent.event) {
          case "token":
          case "final":
          case "error":
            setMessages((current) => applyAnswerStreamEvent(current, assistantMessageId, streamEvent));
            break;
          case "done":
            return;
          default:
            return assertNever(streamEvent);
        }
      }
    } catch (error) {
      if (abortController.signal.aborted || activeStream.current !== abortController) return;
      const message = error instanceof Error ? error.message : "Unable to generate answer";
      setMessages((current) => applyAnswerStreamEvent(current, assistantMessageId, {
        event: "error",
        data: { detail: message, message },
      }));
    } finally {
      if (activeStream.current === abortController) {
        activeStream.current = null;
        setIsAnswering(false);
      }
    }
  }

  return (
    <main className="demo-shell">
      <aside className="demo-sidebar">
        <div className="sidebar-icon-row">
          <button title="Chat"><MessageSquare size={17} /></button>
          <button title="Sidebar"><PanelLeft size={17} /></button>
        </div>

        <button className="sidebar-action primary" type="button" onClick={clearChat}>
          <SquarePen size={16} /> New chat
        </button>
        <Link className="sidebar-action" href="/admin/knowledge-bases">
          <Settings size={16} /> Admin
        </Link>
        <button className="sidebar-action" type="button" onClick={clearChat}>
          <Trash2 size={16} /> Delete all
        </button>

        <div className="history-block">
          <h2>History</h2>
          <p>Your conversations will appear here once you start chatting!</p>
        </div>

        <div className="guest-row">
          <span className="guest-dot" />
          <strong>Guest</strong>
          <span>⌃</span>
        </div>
      </aside>

      <section className="demo-main">
        <header className="demo-topbar">
          <div className="kb-pill">
            <Globe2 size={16} />
            {knowledgeBases.length > 0 ? (
              <select value={knowledgeBaseId} onChange={(event) => updateKnowledgeBaseId(event.target.value)} disabled={isLoadingKnowledgeBases}>
                <option value="">Knowledge base</option>
                {knowledgeBases.map((kb) => (
                  <option value={kb.knowledge_base_id} key={kb.knowledge_base_id}>{kb.knowledge_base_name}</option>
                ))}
              </select>
            ) : (
              <input value={knowledgeBaseId} onChange={(event) => updateKnowledgeBaseId(event.target.value)} placeholder="Knowledge base ID" />
            )}
          </div>
          <a className="deploy-button" href="/admin/settings"><Settings size={16} /> Admin Settings</a>
        </header>

        <div className={messages.length === 0 ? "demo-center empty" : "demo-center with-messages"}>
          {messages.length === 0 ? (
            <section className="hero-prompt">
              <h1>What can I help with?</h1>
              <p>Ask a question, explore documents, or inspect cited sources.</p>
              {kbError ? <div className="inline-warning">Could not load KB list: {kbError}</div> : null}
              <div className="example-grid">
                {EXAMPLES.map((example) => (
                  <button key={example} type="button" onClick={() => setQuestion(example)}>
                    {example}
                  </button>
                ))}
              </div>
            </section>
          ) : (
            <div className="conversation">
              {messages.map((message) => <ChatMessage message={message} key={message.id} />)}
            </div>
          )}
        </div>

        <form className="demo-composer" onSubmit={onSubmit}>
          <textarea
            placeholder={knowledgeBaseId ? "Ask anything..." : "Select a knowledge base first..."}
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                event.currentTarget.form?.requestSubmit();
              }
            }}
          />
          <div className="composer-footer">
            <div className="composer-tools">
              <span className="composer-model"><Cpu size={15} />{generationModel || "unavailable"}</span>
            </div>
            <button className="send-circle" type="submit" aria-label="Send message" disabled={!canSend}><ArrowUp size={16} /></button>
          </div>
        </form>
      </section>
    </main>
  );
}
