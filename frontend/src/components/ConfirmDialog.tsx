import { useEffect, useRef, type ReactNode } from "react";

import { Spinner } from "./Feedback";

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  children: ReactNode;
  confirmLabel: string;
  busy?: boolean;
  onConfirm: () => void;
  onClose: () => void;
}

/** Native <dialog>: focus trapping, Escape to close and inert background come from the browser. */
export function ConfirmDialog({ open, title, children, confirmLabel, busy = false, onConfirm, onClose }: ConfirmDialogProps) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal?.();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      className="dialog"
      aria-labelledby="dialog-title"
      onCancel={(event) => {
        event.preventDefault();
        if (!busy) onClose();
      }}
      onClick={(event) => {
        if (event.target === ref.current && !busy) onClose();
      }}
    >
      <div className="dialog-body">
        <h2 id="dialog-title">{title}</h2>
        <div className="dialog-content">{children}</div>
        <div className="dialog-actions">
          <button type="button" className="button button-secondary" onClick={onClose} disabled={busy}>
            Cancel
          </button>
          <button type="button" className="button button-danger" onClick={onConfirm} disabled={busy}>
            {busy && <Spinner size={16} />}
            {confirmLabel}
          </button>
        </div>
      </div>
    </dialog>
  );
}
