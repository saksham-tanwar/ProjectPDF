import { FileText, Plus, RotateCw } from "lucide-react";
import { Link, NavLink } from "react-router";

import { useDocuments } from "../api/queries";
import { formatRelativeDate } from "../lib/format";
import { Brand } from "./Brand";
import { Spinner } from "./Feedback";
import { StatusDot } from "./StatusBadge";
import { UserMenu } from "./UserMenu";

export function Sidebar({ onNavigate }: { onNavigate: () => void }) {
  const documents = useDocuments();

  return (
    <aside className="sidebar" aria-label="Documents">
      <div className="sidebar-top">
        <Brand />
      </div>
      <Link to="/" className="button button-primary sidebar-new" onClick={onNavigate}>
        <Plus size={18} aria-hidden /> New document
      </Link>

      <nav className="sidebar-list" aria-label="Your documents">
        <p className="sidebar-heading">Your documents</p>
        {documents.isPending && (
          <div className="sidebar-empty">
            <Spinner label="Loading documents" />
          </div>
        )}
        {documents.isError && (
          <div className="sidebar-empty">
            <p>{documents.error.message}</p>
            <button type="button" className="button button-ghost button-small" onClick={() => documents.refetch()}>
              <RotateCw size={14} aria-hidden /> Retry
            </button>
          </div>
        )}
        {documents.data?.length === 0 && (
          <p className="sidebar-empty">Uploaded PDFs will appear here.</p>
        )}
        <ul>
          {documents.data?.map((doc) => (
            <li key={doc.id}>
              <NavLink to={`/documents/${doc.id}`} className="doc-link" onClick={onNavigate}>
                <FileText size={18} aria-hidden className="doc-link-icon" />
                <span className="doc-link-text">
                  <span className="doc-link-name" title={doc.name}>
                    {doc.name}
                  </span>
                  <span className="doc-link-meta">{formatRelativeDate(doc.created_at)}</span>
                </span>
                <StatusDot status={doc.status} />
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>

      <div className="sidebar-bottom">
        <UserMenu />
      </div>
    </aside>
  );
}
