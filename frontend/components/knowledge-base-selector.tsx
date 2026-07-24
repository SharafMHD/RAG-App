"use client";

import type { KnowledgeBaseSummary } from "@/lib/api/types";

type Props = {
  knowledgeBases: KnowledgeBaseSummary[];
  value: string;
  isLoading: boolean;
  error: string | null;
  onChange: (knowledgeBaseId: string) => void;
  onRefresh: () => void;
};

export function KnowledgeBaseSelector({ knowledgeBases, value, isLoading, error, onChange, onRefresh }: Props) {
  return (
    <section className="panel kb-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Knowledge base</p>
          <h2>Select indexed content</h2>
        </div>
        <button className="secondary-button" onClick={onRefresh} disabled={isLoading} type="button">
          {isLoading ? "Loading..." : "Refresh"}
        </button>
      </div>

      {knowledgeBases.length > 0 ? (
        <select value={value} onChange={(event) => onChange(event.target.value)} aria-label="Knowledge base">
          <option value="">Choose a knowledge base</option>
          {knowledgeBases.map((kb) => (
            <option value={kb.knowledge_base_id} key={kb.knowledge_base_id}>
              {kb.knowledge_base_name} — {kb.knowledge_base_id}
            </option>
          ))}
        </select>
      ) : (
        <label className="manual-kb">
          Knowledge base ID
          <input
            placeholder="Paste knowledge_base_id UUID"
            value={value}
            onChange={(event) => onChange(event.target.value)}
          />
        </label>
      )}

      {error ? <p className="warning">Could not load KB list: {error}. You can still paste a KB ID manually.</p> : null}
      {value ? <p className="muted break-word">Selected: {value}</p> : <p className="muted">Select or paste a knowledge base ID to enable chat.</p>}
    </section>
  );
}
