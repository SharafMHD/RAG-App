"use client";

import { createContext, useContext, useId, useState } from "react";
import type { ComponentProps, Dispatch, SetStateAction } from "react";
import Markdown, { type Components, type ExtraProps } from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Citation, SourceChunk } from "@/lib/api/types";

const CITATION_MARKER = /\[source_\d+\]/g;
const CITATION_HREF_PREFIX = "#citation-";

type CitedAnswerProps = {
  readonly content: string;
  readonly citations: readonly Citation[];
  readonly source_chunks: readonly SourceChunk[];
};

type CitationMarkdownContextValue = {
  readonly citations: readonly Citation[];
  readonly disclosureId: string;
  readonly openSourceId: string | null;
  readonly setOpenSourceId: Dispatch<SetStateAction<string | null>>;
};

type MarkdownAnchorProps = ComponentProps<"a"> & ExtraProps;
type MarkdownTableProps = ComponentProps<"table"> & ExtraProps;

const CitationMarkdownContext = createContext<CitationMarkdownContextValue | null>(null);
const markdownComponents: Components = {
  a: MarkdownLink,
  table: MarkdownTable,
};

function markdownWithCitationLinks(content: string, citations: readonly Citation[]): string {
  return content.replace(CITATION_MARKER, (marker) => {
    const sourceId = marker.slice(1, -1);
    const hasCitation = citations.some((citation) => citation.source_id === sourceId);
    return hasCitation ? `[\\${marker.slice(0, 1)}${sourceId}\\${marker.slice(-1)}](${CITATION_HREF_PREFIX}${sourceId})` : marker;
  });
}

function useCitationMarkdownContext(): CitationMarkdownContextValue {
  const value = useContext(CitationMarkdownContext);
  if (value === null) {
    throw new Error("Citation markdown context is missing");
  }
  return value;
}

function MarkdownLink({ children, href }: MarkdownAnchorProps) {
  const { citations, disclosureId, openSourceId, setOpenSourceId } = useCitationMarkdownContext();
  if (href?.startsWith(CITATION_HREF_PREFIX)) {
    const sourceId = href.slice(CITATION_HREF_PREFIX.length);
    const citation = citations.find((candidate) => candidate.source_id === sourceId);
    if (citation === undefined) return <span>{children}</span>;

    const documentName = citation.document_name?.trim() || "Unknown document";
    const isExpanded = openSourceId === sourceId;
    return (
      <button
        aria-controls={disclosureId}
        aria-expanded={isExpanded}
        aria-label={`View ${sourceId}: ${documentName}`}
        className="citation-marker"
        onClick={() => setOpenSourceId((current) => current === sourceId ? null : sourceId)}
        type="button"
      >
        <bdi dir="ltr">{children}</bdi>
      </button>
    );
  }

  return <a href={href} rel="noreferrer" target="_blank">{children}</a>;
}

function MarkdownTable({ children }: MarkdownTableProps) {
  return <div className="markdown-table-wrap"><table>{children}</table></div>;
}

export function CitedAnswer({ content, citations, source_chunks }: CitedAnswerProps) {
  const disclosureId = useId();
  const [openSourceId, setOpenSourceId] = useState<string | null>(null);
  const openCitation = citations.find((citation) => citation.source_id === openSourceId);
  const openSourceChunk = source_chunks.find((chunk) => chunk.source_id === openSourceId);
  const markdownContent = markdownWithCitationLinks(content, citations);

  return (
    <div className="cited-answer">
      <CitationMarkdownContext.Provider value={{ citations, disclosureId, openSourceId, setOpenSourceId }}>
        <div className="cited-answer-text">
          <Markdown components={markdownComponents} remarkPlugins={[remarkGfm]}>{markdownContent}</Markdown>
        </div>
      </CitationMarkdownContext.Provider>

      <section
        aria-label="Source details"
        className="citation-disclosure"
        hidden={openCitation === undefined}
        id={disclosureId}
      >
        {openCitation === undefined ? null : (
          <>
            <header>
              <strong><bdi dir="auto">{openCitation.document_name?.trim() || "Unknown document"}</bdi></strong>
              {openCitation.page_number === null ? null : <span>Page {openCitation.page_number}</span>}
            </header>
            {openSourceChunk?.text ? <p dir="auto">{openSourceChunk.text}</p> : null}
          </>
        )}
      </section>
    </div>
  );
}
