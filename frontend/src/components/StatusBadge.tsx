import type { DocumentStatus } from "../api/types";

const LABELS: Record<DocumentStatus, string> = {
  uploading: "Uploading",
  queued: "Queued",
  processing: "Reading",
  ready: "Ready",
  failed: "Failed",
};

export function StatusBadge({ status }: { status: DocumentStatus }) {
  return (
    <span className={`status-badge status-${status}`}>
      <span className="status-dot" aria-hidden />
      {LABELS[status]}
    </span>
  );
}

export function StatusDot({ status }: { status: DocumentStatus }) {
  return <span className={`status-dot status-${status}`} title={LABELS[status]} aria-label={LABELS[status]} role="img" />;
}
