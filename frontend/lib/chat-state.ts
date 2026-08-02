import type { AnswerStreamEvent, ChatAnswerResponse } from "@/lib/api/types";

export type UserMessage = {
  readonly id: string;
  readonly kind: "user";
  readonly content: string;
};

export type AssistantStreamingMessage = {
  readonly id: string;
  readonly kind: "assistant_streaming";
  readonly content: string;
  readonly question: string;
};

export type AssistantCompleteMessage = {
  readonly id: string;
  readonly kind: "assistant_complete";
  readonly content: string;
  readonly question: string;
  readonly response: ChatAnswerResponse;
};

export type AssistantErrorMessage = {
  readonly id: string;
  readonly kind: "assistant_error";
  readonly content: string;
};

export type ChatMessage =
  | UserMessage
  | AssistantStreamingMessage
  | AssistantCompleteMessage
  | AssistantErrorMessage;

export type AnswerStreamContentEvent = Exclude<AnswerStreamEvent, { readonly event: "done" }>;

export function assertNever(value: never): never {
  throw new TypeError(`Unexpected chat variant: ${JSON.stringify(value)}`);
}

export function applyAnswerStreamEvent(
  messages: readonly ChatMessage[],
  assistantMessageId: string,
  event: AnswerStreamContentEvent,
): ChatMessage[] {
  return messages.map((message) => {
    if (message.id !== assistantMessageId) return message;

    switch (message.kind) {
      case "user":
      case "assistant_complete":
      case "assistant_error":
        return message;
      case "assistant_streaming":
        switch (event.event) {
          case "token":
            return { ...message, content: message.content + event.data.content };
          case "final":
            return {
              id: message.id,
              kind: "assistant_complete",
              content: event.data.response.answer,
              question: message.question,
              response: event.data.response,
            };
          case "error":
            return { id: message.id, kind: "assistant_error", content: event.data.message };
          default:
            return assertNever(event);
        }
      default:
        return assertNever(message);
    }
  });
}
