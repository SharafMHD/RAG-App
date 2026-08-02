"use client";

import { useState } from "react";
import { LoaderCircle, MessageSquareText, ThumbsDown, ThumbsUp } from "lucide-react";
import { AnswerDetails } from "@/components/answer-details";
import { submitAnswerFeedback } from "@/lib/api/rag";
import type { ChatAnswerResponse, FeedbackRating } from "@/lib/api/types";
import { assertNever, type ChatMessage as ChatMessageState } from "@/lib/chat-state";

type FeedbackSubmissionState =
  | { readonly kind: "idle" }
  | { readonly kind: "pending"; readonly rating: FeedbackRating }
  | { readonly kind: "success"; readonly message: string }
  | { readonly kind: "error"; readonly rating: FeedbackRating; readonly message: string };

function isLikelyRtl(text: string): boolean {
  return /[\u0600-\u06FF]/.test(text);
}

export function ChatMessage({ message }: { readonly message: ChatMessageState }) {
  switch (message.kind) {
    case "user":
      return (
        <article className="message user" dir={isLikelyRtl(message.content) ? "rtl" : "ltr"}>
          <div className="avatar">U</div>
          <div className="bubble"><p>{message.content}</p></div>
        </article>
      );
    case "assistant_streaming":
      return (
        <article className="message assistant" dir={isLikelyRtl(message.content) ? "rtl" : "ltr"} aria-busy="true">
          <div className="avatar">AI</div>
          <div className="bubble"><p>{message.content || "Thinking…"}</p></div>
        </article>
      );
    case "assistant_complete":
      return (
        <article className="message assistant" dir={isLikelyRtl(message.content) ? "rtl" : "ltr"}>
          <div className="avatar">AI</div>
          <div className="bubble">
            <p>{message.content}</p>
            <FeedbackControls question={message.question} response={message.response} />
            <AnswerDetails response={message.response} />
          </div>
        </article>
      );
    case "assistant_error":
      return (
        <article className="message assistant" dir={isLikelyRtl(message.content) ? "rtl" : "ltr"}>
          <div className="avatar">AI</div>
          <div className="bubble"><div className="error-box compact" role="alert">{message.content}</div></div>
        </article>
      );
    default:
      return assertNever(message);
  }
}

function FeedbackControls({
  question,
  response,
}: {
  readonly question: string;
  readonly response: ChatAnswerResponse;
}) {
  const [comment, setComment] = useState("");
  const [isCommentOpen, setIsCommentOpen] = useState(false);
  const [savedRating, setSavedRating] = useState<FeedbackRating | null>(null);
  const [submission, setSubmission] = useState<FeedbackSubmissionState>({ kind: "idle" });
  const isPending = submission.kind === "pending";

  async function submit(rating: FeedbackRating): Promise<void> {
    setSubmission({ kind: "pending", rating });
    try {
      const feedback = await submitAnswerFeedback(response.knowledge_base_id, {
        trace_id: response.trace_id,
        knowledge_base_id: response.knowledge_base_id,
        rating,
        comment: comment.trim() || null,
        question,
        answer: response.answer,
        citations: response.citations,
        source_chunks: response.source_chunks,
      });
      setSavedRating(feedback.rating);
      setSubmission({ kind: "success", message: feedback.message });
    } catch (error) {
      setSubmission({
        kind: "error",
        rating,
        message: error instanceof Error ? error.message : "Unable to save feedback",
      });
    }
  }

  return (
    <section className="answer-feedback" aria-label="Answer feedback">
      <div className="feedback-row" role="group" aria-label="Rate this answer">
        <span>Was this helpful?</span>
        <button
          className="feedback-vote"
          type="button"
          aria-label="Helpful"
          aria-pressed={savedRating === "thumbs_up"}
          disabled={isPending}
          onClick={() => submit("thumbs_up")}
        >
          <ThumbsUp aria-hidden="true" size={16} />
        </button>
        <button
          className="feedback-vote"
          type="button"
          aria-label="Not helpful"
          aria-pressed={savedRating === "thumbs_down"}
          disabled={isPending}
          onClick={() => submit("thumbs_down")}
        >
          <ThumbsDown aria-hidden="true" size={16} />
        </button>
        <button
          className="feedback-comment-toggle"
          type="button"
          aria-expanded={isCommentOpen}
          onClick={() => setIsCommentOpen((current) => !current)}
        >
          <MessageSquareText aria-hidden="true" size={15} />
          {isCommentOpen ? "Hide comment" : "Add a comment"}
        </button>
      </div>

      {isCommentOpen ? (
        <label className="feedback-comment">
          Feedback comment
          <textarea
            value={comment}
            onChange={(event) => setComment(event.target.value)}
            placeholder="Optional details about this answer"
            maxLength={2000}
          />
        </label>
      ) : null}

      {submission.kind === "pending" ? (
        <div className="feedback-status" role="status">
          <LoaderCircle className="spin" aria-hidden="true" size={15} /> Saving feedback…
        </div>
      ) : null}
      {submission.kind === "success" ? (
        <div className="feedback-status success" role="status">{submission.message}</div>
      ) : null}
      {submission.kind === "error" ? (
        <div className="feedback-status error" role="alert">
          <span>{submission.message}</span>
          <button type="button" onClick={() => submit(submission.rating)}>Retry feedback</button>
        </div>
      ) : null}
    </section>
  );
}
