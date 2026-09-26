import { RotateCw, Search } from "lucide-react";
import { useDeferredValue, useState, type FormEvent } from "react";

import { useSearch } from "../api/queries";
import type { PaperDocument } from "../api/types";
import { Spinner } from "./Feedback";

// Marking "the" or "is" adds noise rather than helping the eye find the match.
const STOP_WORDS = new Set([
  "and", "are", "but", "can", "did", "does", "for", "from", "had", "has", "have", "how", "into", "its", "not", "the",
  "that", "them", "then", "there", "these", "they", "this", "was", "were", "what", "when", "where", "which", "who",
  "why", "will", "with", "you", "your",
]);

export function searchWords(query: string): string[] {
  const words = query.toLowerCase().match(/[\p{L}\p{N}]{3,}/gu) ?? [];
  return [...new Set(words.filter((word) => !STOP_WORDS.has(word)))];
}

/** Splits text so searched words can be marked, matching whole words only and never using innerHTML. */
export function highlight(text: string, query: string) {
  const words = searchWords(query);
  if (words.length === 0) return [text];
  const escaped = words.map((word) => word.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|");
  return text.split(new RegExp(`(?<![\\p{L}\\p{N}])(${escaped})(?![\\p{L}\\p{N}])`, "giu"));
}

function Snippet({ text, query }: { text: string; query: string }) {
  const words = new Set(searchWords(query));
  return (
    <p>
      {highlight(text, query).map((part, index) =>
        words.has(part.toLowerCase()) ? <mark key={index}>{part}</mark> : <span key={index}>{part}</span>,
      )}
    </p>
  );
}

export function SearchPanel({ document }: { document: PaperDocument }) {
  const [input, setInput] = useState("");
  const query = useDeferredValue(input);
  const search = useSearch(document.id, query);
  const trimmed = query.trim();

  return (
    <div className="panel">
      <form className="search-box" onSubmit={(event: FormEvent) => event.preventDefault()} role="search">
        <Search size={18} aria-hidden />
        <label htmlFor="document-search" className="visually-hidden">
          Search inside this document
        </label>
        <input
          id="document-search"
          type="search"
          value={input}
          placeholder="Search this document…"
          autoComplete="off"
          onChange={(event) => setInput(event.target.value)}
        />
        {search.isFetching && trimmed.length > 1 && <Spinner size={16} />}
      </form>

      {trimmed.length <= 1 && (
        <p className="panel-hint">
          Finds passages by meaning as well as exact words, so "how do I send it back" finds the returns policy.
        </p>
      )}

      {search.isError && (
        <p className="notice notice-error" role="alert">
          {search.error.message}
          <button type="button" className="button button-ghost button-small" onClick={() => search.refetch()}>
            <RotateCw size={14} aria-hidden /> Retry
          </button>
        </p>
      )}

      {search.data && trimmed.length > 1 && (
        <>
          <p className="panel-subhead" aria-live="polite">
            {search.data.length === 0 ? "No matching passages" : `${search.data.length} passage${search.data.length === 1 ? "" : "s"}`}
          </p>
          <ol className="search-results">
            {search.data.map((result, index) => (
              <li key={`${result.page}-${index}`}>
                <span className="result-page">Page {result.page}</span>
                <Snippet text={result.text} query={trimmed} />
              </li>
            ))}
          </ol>
        </>
      )}
    </div>
  );
}
