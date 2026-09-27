import { ArrowUp, ChevronDown, CircleAlert, FileSearch, RotateCw } from "lucide-react";
import { useEffect, useLayoutEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";

import type { AnswerMode, Source } from "../api/types";
import type { ChatMessage } from "../lib/useConversation";
import { Avatar } from "./Avatar";
import { BrandMark } from "./Brand";

const MAX_QUESTION = 2000;

export function MessageList({
  messages,
  userName,
  userPicture,
  onRetry,
}: {
  messages: ChatMessage[];
  userName: string;
  userPicture?: string | null;
  onRetry: (message: ChatMessage) => void;
}) {
  const endRef = useRef<HTMLDivElement>(null);
  const last = messages[messages.length - 1];

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end", behavior: "smooth" });
  }, [messages.length, last?.status]);

  return (
    <div className="messages" aria-live="polite" aria-busy={last?.status === "pending"}>
      {messages.map((message) =>
        message.role === "user" ? (
          <div key={message.id} className="message message-user">
            <div className="message-bubble">
              <Paragraphs text={message.text} />
            </div>
            <Avatar name={userName} picture={userPicture} size={30} />
          </div>
        ) : (
          <div key={message.id} className="message message-assistant">
            <span className="assistant-mark">
              <BrandMark size={30} />
            </span>
            <div className="message-body">
              {message.status === "pending" && (
                <div className="typing" aria-label="Looking through the document">
                  <span />
                  <span />
                  <span />
                </div>
              )}
              {message.status === "error" && (
                <div className="notice notice-error message-error" role="alert">
                  <CircleAlert size={16} aria-hidden />
                  <span>{message.text}</span>
                  {message.question && (
                    <button type="button" className="button button-ghost button-small" onClick={() => onRetry(message)}>
                      <RotateCw size={14} aria-hidden /> Retry
                    </button>
                  )}
                </div>
              )}
              {message.status === "done" && (
                <>
                  <ModeNote mode={message.mode} />
                  <div className="answer">
                    <Paragraphs text={message.text} />
                  </div>
                  {message.sources && message.sources.length > 0 && <Sources sources={message.sources} />}
                </>
              )}
            </div>
          </div>
        ),
      )}
      <div ref={endRef} />
    </div>
  );
}

function Paragraphs({ text }: { text: string }) {
  return (
    <>
      {text
        .split(/\n{2,}/)
        .filter((paragraph) => paragraph.trim())
        .map((paragraph, index) => (
          <p key={index}>{paragraph}</p>
        ))}
    </>
  );
}

function ModeNote({ mode }: { mode?: AnswerMode }) {
  if (mode !== "extractive") return null;
  return (
    <p className="mode-note">
      <FileSearch size={14} aria-hidden /> Relevant passages, not a generated answer
    </p>
  );
}

function Sources({ sources }: { sources: Source[] }) {
  const [openIndex, setOpenIndex] = useState<number | null>(null);
  const open = openIndex === null ? null : sources[openIndex];

  return (
    <div className="sources">
      <p className="sources-label">Sources</p>
      <div className="source-chips">
        {sources.map((source, index) => (
          <button
            key={`${source.page}-${index}`}
            type="button"
            className={`source-chip${openIndex === index ? " source-chip-open" : ""}`}
            aria-expanded={openIndex === index}
            onClick={() => setOpenIndex(openIndex === index ? null : index)}
          >
            Page {source.page}
            <ChevronDown size={14} aria-hidden />
          </button>
        ))}
      </div>
      {open && (
        <blockquote className="source-passage">
          <p>{open.text}</p>
          <footer>Page {open.page}</footer>
        </blockquote>
      )}
    </div>
  );
}

export function Composer({ disabled, onSubmit }: { disabled: boolean; onSubmit: (question: string) => void }) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useLayoutEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`;
  }, [value]);

  const question = value.trim();
  const canSend = !disabled && question.length > 0 && question.length <= MAX_QUESTION;

  function submit(event?: FormEvent) {
    event?.preventDefault();
    if (!canSend) return;
    onSubmit(question);
    setValue("");
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      submit();
    }
  }

  return (
    <form className="composer" onSubmit={submit}>
      <div className="composer-box">
        <label htmlFor="question" className="visually-hidden">
          Ask a question about this document
        </label>
        <textarea
          id="question"
          ref={textareaRef}
          rows={1}
          value={value}
          maxLength={MAX_QUESTION}
          placeholder="Ask a question about this document…"
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={onKeyDown}
        />
        <button type="submit" className="send-button" disabled={!canSend} aria-label="Send question">
          <ArrowUp size={18} aria-hidden />
        </button>
      </div>
      <p className="composer-hint">
        <span>Enter to send · Shift + Enter for a new line</span>
        {value.length > MAX_QUESTION - 200 && (
          <span>
            {value.length}/{MAX_QUESTION}
          </span>
        )}
      </p>
    </form>
  );
}
