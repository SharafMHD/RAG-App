import type { ChatAnswerResponse } from "@/lib/api/types";

function formatScore(score: number | null | undefined): string {
  return typeof score === "number" ? score.toFixed(3) : "n/a";
}

export function AnswerDetails({ response }: { readonly response: ChatAnswerResponse }) {
  const hasAnswer = response.answer.trim().length > 0;
  const hasCitations = response.citations.length > 0;
  const emptyEvidenceTitle = hasAnswer
    ? "No citations"
    : hasCitations
      ? "No answer generated"
      : "No answer or citations";
  const emptyEvidenceMessage = response.source_chunks.length > 0
    ? "Retrieved source chunks are still available below."
    : hasCitations
      ? "Citations are still available below."
      : "The retrieval did not return supporting evidence for this response.";

  return (
    <section className="answer-details" aria-label="Answer evidence">
      <dl className="meta-grid">
        <div className="evidence-chip">
          <dt>Confidence</dt>
          <dd>{formatScore(response.confidence)}</dd>
        </div>
        <div className="evidence-chip">
          <dt>Strategy</dt>
          <dd dir="auto">{response.retrieval_metadata.strategy}</dd>
        </div>
        <div className="evidence-chip">
          <dt>Sources</dt>
          <dd>{response.retrieval_metadata.returned_count}</dd>
        </div>
        <div className="evidence-chip trace-chip">
          <dt>Trace</dt>
          <dd tabIndex={0}>
            <bdi>{response.trace_id}</bdi>
          </dd>
        </div>
      </dl>

      {!hasAnswer || !hasCitations ? (
        <div className="answer-evidence-empty" role="status">
          <strong>{emptyEvidenceTitle}</strong>
          <span>{emptyEvidenceMessage}</span>
        </div>
      ) : null}

      {hasCitations ? (
        <details className="evidence-disclosure" open>
          <summary>
            <span>Citations</span>
            <small>{response.citations.length} {response.citations.length === 1 ? "source" : "sources"}</small>
          </summary>
          <ol className="citation-list">
            {response.citations.map((citation) => (
              <li key={`${citation.source_id}-${citation.rank}`}>
                <article className="citation-card">
                  <header>
                    <span className="citation-rank">Source {citation.rank}</span>
                    <strong><bdi dir="ltr">{citation.document_name || "Unknown document"}</bdi></strong>
                  </header>
                  <dl className="citation-metadata">
                    <div className="citation-identifier"><dt>ID</dt><dd><bdi>{citation.source_id}</bdi></dd></div>
                    {citation.page_number != null ? <div><dt>Page</dt><dd>{citation.page_number}</dd></div> : null}
                    <div><dt>Score</dt><dd>{formatScore(citation.score)}</dd></div>
                    {citation.chunk_id ? <div className="citation-identifier"><dt>Chunk</dt><dd><bdi>{citation.chunk_id}</bdi></dd></div> : null}
                  </dl>
                </article>
              </li>
            ))}
          </ol>
        </details>
      ) : null}

      {response.source_chunks.length > 0 ? (
        <details className="evidence-disclosure">
          <summary>
            <span>Retrieved source chunks</span>
            <small>{response.source_chunks.length} {response.source_chunks.length === 1 ? "chunk" : "chunks"}</small>
          </summary>
          <ol className="source-list">
            {response.source_chunks.map((chunk) => (
              <li key={`${chunk.source_id}-${chunk.rank}`}>
                <article className="source-card">
                  <header>
                    <strong><bdi>{chunk.source_id}</bdi></strong>
                    <span>Rank {chunk.rank}</span>
                    <span>Score {formatScore(chunk.score)}</span>
                  </header>
                  <p dir="auto">{chunk.text}</p>
                </article>
              </li>
            ))}
          </ol>
        </details>
      ) : null}
    </section>
  );
}
