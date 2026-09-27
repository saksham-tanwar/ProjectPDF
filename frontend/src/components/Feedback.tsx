import { CircleAlert, LoaderCircle, RotateCw } from "lucide-react";

import { Brand } from "./Brand";

export function Spinner({ size = 18, label }: { size?: number; label?: string }) {
  return (
    <span className="spinner" role={label ? "status" : undefined} aria-label={label}>
      <LoaderCircle size={size} aria-hidden />
    </span>
  );
}

export function FullPageSpinner({ label }: { label: string }) {
  return (
    <main className="full-page">
      <Brand />
      <Spinner size={28} label={label} />
    </main>
  );
}

export function FullPageError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <main className="full-page">
      <Brand />
      <div className="notice notice-error" role="alert">
        <CircleAlert size={18} aria-hidden />
        <span>{message}</span>
      </div>
      <button type="button" className="button button-secondary" onClick={onRetry}>
        <RotateCw size={16} aria-hidden /> Try again
      </button>
    </main>
  );
}
