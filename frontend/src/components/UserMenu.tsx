import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ChevronsUpDown, LogOut, ShieldCheck, Trash2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router";

import { api } from "../api/client";
import { keys, useMe } from "../api/queries";
import { Avatar } from "./Avatar";
import { ConfirmDialog } from "./ConfirmDialog";
import { useToast } from "./Toast";

export function UserMenu() {
  const { data: user } = useMe();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (event: MouseEvent | KeyboardEvent) => {
      if (event instanceof KeyboardEvent ? event.key === "Escape" : !menuRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", close);
    };
  }, [open]);

  const signedOut = () => {
    queryClient.clear();
    queryClient.setQueryData(keys.me, null);
    navigate("/login", { replace: true });
  };

  const logout = useMutation({
    mutationFn: api.logout,
    onSuccess: signedOut,
    onError: (error) => toast.error(error.message),
  });

  const deleteAccount = useMutation({
    mutationFn: api.deleteAccount,
    onSuccess: () => {
      try {
        window.sessionStorage.clear();
      } catch {
        // Ignore blocked storage.
      }
      signedOut();
    },
    onError: (error) => toast.error(error.message),
  });

  if (!user) return null;

  return (
    <div className="user-menu" ref={menuRef}>
      <button
        type="button"
        className="user-menu-trigger"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        <Avatar name={user.name} picture={user.picture} />
        <span className="user-menu-text">
          <span className="user-menu-name">{user.name}</span>
          <span className="user-menu-email">{user.email}</span>
        </span>
        <ChevronsUpDown size={16} aria-hidden />
      </button>
      {open && (
        <div className="menu" role="menu">
          <Link to="/privacy" role="menuitem" className="menu-item" onClick={() => setOpen(false)}>
            <ShieldCheck size={16} aria-hidden /> Privacy
          </Link>
          <button type="button" role="menuitem" className="menu-item" onClick={() => logout.mutate()} disabled={logout.isPending}>
            <LogOut size={16} aria-hidden /> Sign out
          </button>
          <div className="menu-separator" role="separator" />
          <button
            type="button"
            role="menuitem"
            className="menu-item menu-item-danger"
            onClick={() => {
              setOpen(false);
              setConfirmDelete(true);
            }}
          >
            <Trash2 size={16} aria-hidden /> Delete account
          </button>
        </div>
      )}
      <ConfirmDialog
        open={confirmDelete}
        title="Delete your account?"
        confirmLabel="Delete account"
        busy={deleteAccount.isPending}
        onClose={() => setConfirmDelete(false)}
        onConfirm={() => deleteAccount.mutate()}
      >
        <p>This permanently deletes your account, every uploaded PDF and all extracted text. This can't be undone.</p>
      </ConfirmDialog>
    </div>
  );
}
