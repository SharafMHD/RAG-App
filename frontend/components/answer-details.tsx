import type { ChatAnswerResponse } from "@/lib/api/types";

function formatScore(score: number | null | undefined): string {
  return typeof score === "number" ? score.toFixed(3) : "n/a";
}

export function AnswerDetails({ response }: { response: ChatAnswerResponse }) {
  return (
    <div className="answer-details">
      <div className="meta-grid">
        <span>Confidence: {formatScore(response.confidence)}</span>
        <span>Strategy: {response.retrieval_metadata.strategy}</span>
        <span>Sources: {response.retrieval_metadata.returned_count}</span>
        <span className="break-word">Trace: {response.trace_id}</span>
      </div>

      {response.citations.length > 0 ? (
        <details open>
          <summary>Citations</summary>
          <div className="citation-list">
            {response.citations.map((citation) => (
              <div className="citation-card" key={`${citation.source_id}-${citation.rank}`}>
                <strong>[{citation.source_id}]</strong>
                <span>{citation.document_name || "Unknown document"}</span>
                {citation.page_number ? <span>Page {citation.page_number}</span> : null}
                <span>Score {formatScore(citation.score)}</span>
                {citation.chunk_id ? <small className="break-word">Chunk {citation.chunk_id}</small> : null}
              </div>
            ))}
          </div>
        </details>
      ) : null}

      {response.source_chunks.length > 0 ? (
        <details>
          <summary>Retrieved source chunks</summary>
          <div className="source-list">
            {response.source_chunks.map((chunk) => (
              <article className="source-card" key={`${chunk.source_id}-${chunk.rank}`}>
                <header>
                  <strong>{chunk.source_id}</strong>
                  <span>Rank {chunk.rank}</span>
                  <span>Score {formatScore(chunk.score)}</span>
                </header>
                <p>{chunk.text}</p>
              </article>
            ))}
          </div>
        </details>
      ) : null}
    </div>
  );
}
