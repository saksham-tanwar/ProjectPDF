import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CircleAlert, RefreshCw, Sparkles } from "lucide-react";

import { api } from "../api/client";
import { keys, useConfig } from "../api/queries";
import type { PaperDocument } from "../api/types";
import { Spinner } from "./Feedback";
import { useToast } from "./Toast";

export function SummaryPanel({ document }: { document: PaperDocument }) {
  const config = useConfig();
  const queryClient = useQueryClient();
  const toast = useToast();

  const regenerate = useMutation({
    mutationFn: () => api.regenerateSummary(document.id),
    onSuccess: (summary) => {
      queryClient.setQueryData<PaperDocument>(keys.document(document.id), (current) =>
        current ? { ...current, ...summary, summary_error: null } : current,
      );
      toast.success("Summary regenerated.");
    },
    onError: (error) => toast.error(error.message),
  });

  const aiEnabled = config.data?.ai_enabled !== false;

  return (
    <div className="panel">
      <div className="panel-head">
        <h2>
          <Sparkles size={18} aria-hidden /> Summary
        </h2>
        {aiEnabled && (
          <button
            type="button"
            className="button button-ghost button-small"
            onClick={() => regenerate.mutate()}
            disabled={regenerate.isPending}
          >
            {regenerate.isPending ? <Spinner size={14} /> : <RefreshCw size={14} aria-hidden />} Regenerate
          </button>
        )}
      </div>

      {!aiEnabled && (
        <p className="notice notice-warn">
          Summaries need an AI provider. Set AI_API_KEY on the server to turn them on.
        </p>
      )}

      {aiEnabled && !document.summary && (
        <p className="notice notice-error" role="alert">
          <CircleAlert size={16} aria-hidden />
          {document.summary_error ?? "No summary was generated for this document yet."}
        </p>
      )}

      {document.summary && (
        <>
          <p className="summary-text">{document.summary}</p>
          {document.key_points.length > 0 && (
            <>
              <h3 className="panel-subhead">Key points</h3>
              <ul className="key-points">
                {document.key_points.map((point, index) => (
                  <li key={index}>{point}</li>
                ))}
              </ul>
            </>
          )}
        </>
      )}
    </div>
  );
}
