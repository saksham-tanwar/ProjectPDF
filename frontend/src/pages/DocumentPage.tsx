import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CircleAlert, MessagesSquare, RotateCw, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";

import { ApiError, api } from "../api/client";
import { keys, useConfig, useDocument, useMe } from "../api/queries";
import { isPending, type PaperDocument } from "../api/types";
import { Composer, MessageList } from "../components/Chat";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { Spinner } from "../components/Feedback";
import { StatusBadge } from "../components/StatusBadge";
import { useToast } from "../components/Toast";
import { formatBytes } from "../lib/format";
import { clearConversation, useConversation } from "../lib/useConversation";

export function DocumentPage() {
  const { id = "" } = useParams();
  // Keyed so switching documents resets every piece of local state.
  return <DocumentView key={id} id={id} />;
}

function DocumentView({ id }: { id: string }) {
  const document = useDocument(id);
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const toast = useToast();
  const [confirmDelete, setConfirmDelete] = useState(false);

  const status = document.data?.status;
  useEffect(() => {
    // Keep the sidebar in step once processing finishes or fails.
    if (status && !isPending(status)) void queryClient.invalidateQueries({ queryKey: keys.documents, exact: true });
  }, [status, queryClient]);

  const remove = useMutation({
    mutationFn: () => api.deleteDocument(id),
    onSuccess: () => {
      clearConversation(id);
      queryClient.setQueryData<PaperDocument[]>(keys.documents, (current) => current?.filter((doc) => doc.id !== id));
      queryClient.removeQueries({ queryKey: keys.document(id) });
      toast.success("Document deleted.");
      navigate("/", { replace: true });
    },
    onError: (error) => toast.error(error.message),
  });

  if (document.isPending) {
    return (
      <div className="center-state">
        <Spinner size={24} label="Loading document" />
      </div>
    );
  }

  if (document.isError) {
    const notFound = document.error instanceof ApiError && document.error.status === 404;
    return (
      <div className="center-state">
        <CircleAlert size={28} aria-hidden className="center-state-icon" />
        <h1>{notFound ? "Document not found" : "Couldn't load this document"}</h1>
        <p>{notFound ? "It may have been deleted, or it belongs to another account." : document.error.message}</p>
        {notFound ? (
          <Link to="/" className="button button-primary">
            Upload a document
          </Link>
        ) : (
          <button type="button" className="button button-secondary" onClick={() => document.refetch()}>
            <RotateCw size={16} aria-hidden /> Try again
          </button>
        )}
      </div>
    );
  }

  const doc = document.data;
  const meta = [doc.pages ? `${doc.pages} ${doc.pages === 1 ? "page" : "pages"}` : null, formatBytes(doc.size)].filter(Boolean);

  return (
    <div className="document">
      <header className="document-header">
        <div className="document-title">
          <h1 title={doc.name}>{doc.name}</h1>
          <p>
            <StatusBadge status={doc.status} />
            {meta.length > 0 && <span className="document-meta">{meta.join(" · ")}</span>}
          </p>
        </div>
        <button type="button" className="button button-ghost" onClick={() => setConfirmDelete(true)} aria-label="Delete document">
          <Trash2 size={16} aria-hidden />
          <span className="hide-small">Delete</span>
        </button>
      </header>

      {isPending(doc.status) && <ProcessingState document={doc} />}
      {doc.status === "failed" && <FailedState document={doc} onDelete={() => setConfirmDelete(true)} />}
      {doc.status === "ready" && <ReadyState document={doc} />}

      <ConfirmDialog
        open={confirmDelete}
        title="Delete this document?"
        confirmLabel="Delete"
        busy={remove.isPending}
        onClose={() => setConfirmDelete(false)}
        onConfirm={() => remove.mutate()}
      >
        <p>
          <strong>{doc.name}</strong> and its extracted text will be permanently removed.
        </p>
      </ConfirmDialog>
    </div>
  );
}

function ProcessingState({ document }: { document: PaperDocument }) {
  const label = document.status === "processing" ? "Reading pages and indexing text…" : "Waiting for a reader to pick this up…";
  return (
    <div className="center-state">
      <div className="reading-illustration" aria-hidden>
        <span />
        <span />
        <span />
      </div>
      <h2>Getting your document ready</h2>
      <p role="status">{label}</p>
      <p className="muted small">Large PDFs can take a minute. You can leave this page — we'll keep working.</p>
    </div>
  );
}

function FailedState({ document, onDelete }: { document: PaperDocument; onDelete: () => void }) {
  return (
    <div className="center-state">
      <CircleAlert size={28} aria-hidden className="center-state-icon danger" />
      <h2>We couldn't read this PDF</h2>
      <p>{document.error ?? "Something went wrong while processing it."}</p>
      <div className="button-row">
        <button type="button" className="button button-secondary" onClick={onDelete}>
          <Trash2 size={16} aria-hidden /> Delete
        </button>
        <Link to="/" className="button button-primary">
          Upload another PDF
        </Link>
      </div>
    </div>
  );
}

function ReadyState({ document }: { document: PaperDocument }) {
  const { data: user } = useMe();
  const config = useConfig();
  const conversation = useConversation(document.id);

  return (
    <div className="chat">
      <div className="chat-scroll">
        {conversation.messages.length === 0 ? (
          <div className="chat-empty">
            <MessagesSquare size={28} aria-hidden />
            <h2>Ask anything about this document</h2>
            <p>Ask in your own words — summaries, comparisons, definitions or follow-ups. Answers cite the pages they use.</p>
            {config.data?.ai_enabled === false && (
              <p className="notice notice-warn">
                AI answers aren't configured on this server (AI_API_KEY is missing), so you'll get matching passages
                instead of answers.
              </p>
            )}
          </div>
        ) : (
          <MessageList
            messages={conversation.messages}
            userName={user?.name ?? "You"}
            userPicture={user?.picture}
            onRetry={(message) => message.question && void conversation.ask(message.question, message.id)}
          />
        )}
      </div>
      <div className="chat-footer">
        <Composer disabled={conversation.busy} onSubmit={(question) => void conversation.ask(question)} />
      </div>
    </div>
  );
}
