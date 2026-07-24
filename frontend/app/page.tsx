"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { ArrowUp, Database, Globe2, MessageSquare, Paperclip, PanelLeft, Settings, SquarePen, Trash2 } from "lucide-react";
import { AnswerDetails } from "@/components/answer-details";
import { generateAnswer, listKnowledgeBases } from "@/lib/api/rag";
import type { ChatAnswerResponse, KnowledgeBaseSummary, RetrievalStrategy } from "@/lib/api/types";

type Message =
  | { id: string; role: "user"; content: string }
  | { id: string; role: "assistant"; content: string; response: ChatAnswerResponse };

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

function isLikelyRtl(text: string): boolean {
  return /[\u0600-\u06FF]/.test(text);
}

export default function ChatPage() {
  const [knowledgeBaseId, setKnowledgeBaseId] = useState("");
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBaseSummary[]>([]);
  const [kbError, setKbError] = useState<string | null>(null);
  const [isLoadingKnowledgeBases, setIsLoadingKnowledgeBases] = useState(false);
  const [question, setQuestion] = useState("");
  const [limit, setLimit] = useState(5);
  const [strategy, setStrategy] = useState<RetrievalStrategy>("hybrid");
  const [messages, setMessages] = useState<Message[]>([]);
  const [isAnswering, setIsAnswering] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);

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
  }, [refreshKnowledgeBases, updateKnowledgeBaseId]);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = question.trim();
    if (!text || !knowledgeBaseId.trim()) return;

    setChatError(null);
    setIsAnswering(true);
    setQuestion("");
    setMessages((current) => [...current, { id: makeId(), role: "user", content: text }]);

    try {
      const response = await generateAnswer(knowledgeBaseId.trim(), { text, limit, strategy });
      setMessages((current) => [...current, { id: makeId(), role: "assistant", content: response.answer, response }]);
    } catch (error) {
      setChatError(error instanceof Error ? error.message : "Unable to generate answer");
    } finally {
      setIsAnswering(false);
    }
  }

  return (
    <main className="demo-shell">
      <aside className="demo-sidebar">
        <div className="sidebar-icon-row">
          <button title="Chat"><MessageSquare size={17} /></button>
          <button title="Sidebar"><PanelLeft size={17} /></button>
        </div>

        <button className="sidebar-action primary" type="button" onClick={() => setMessages([])}>
          <SquarePen size={16} /> New chat
        </button>
        <Link className="sidebar-action" href="/admin/knowledge-bases">
          <Settings size={16} /> Admin
        </Link>
        <button className="sidebar-action" type="button" onClick={() => setMessages([])}>
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
              {messages.map((message) => (
                <article className={`message ${message.role}`} key={message.id} dir={isLikelyRtl(message.content) ? "rtl" : "ltr"}>
                  <div className="avatar">{message.role === "user" ? "U" : "AI"}</div>
                  <div className="bubble">
                    <p>{message.content}</p>
                    {message.role === "assistant" ? <AnswerDetails response={message.response} /> : null}
                  </div>
                </article>
              ))}
              {isAnswering ? <div className="thinking">Thinking…</div> : null}
              {chatError ? <div className="error-box">{chatError}</div> : null}
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
              <button type="button" title="Attach"><Paperclip size={15} /></button>
              <label>
                <Database size={15} />
                <select value={strategy} onChange={(event) => setStrategy(event.target.value as RetrievalStrategy)}>
                  <option value="hybrid">Hybrid</option>
                  <option value="vector">Vector</option>
                  <option value="bm25">BM25</option>
                </select>
              </label>
              <label>
                Top K
                <input type="number" min={1} max={50} value={limit} onChange={(event) => setLimit(Number(event.target.value))} />
              </label>
            </div>
            <button className="send-circle" type="submit" disabled={!canSend}><ArrowUp size={16} /></button>
          </div>
        </form>
      </section>
    </main>
  );
}
