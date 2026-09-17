import { Link } from "react-router";

export function BrandMark({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" aria-hidden className="brand-mark">
      <rect width="64" height="64" rx="14" fill="var(--accent)" />
      <path d="M20 14h17l11 11v25a4 4 0 0 1-4 4H20a4 4 0 0 1-4-4V18a4 4 0 0 1 4-4Z" fill="var(--accent-contrast)" />
      <path d="M37 14v8a3 3 0 0 0 3 3h8" fill="var(--accent-soft)" />
      <rect x="23" y="33" width="18" height="3" rx="1.5" fill="var(--accent)" />
      <rect x="23" y="40" width="12" height="3" rx="1.5" fill="var(--accent)" />
    </svg>
  );
}

export function Brand({ to = "/" }: { to?: string }) {
  return (
    <Link to={to} className="brand" aria-label="Paperchat home">
      <BrandMark />
      <span className="brand-name">
        paper<span>chat</span>
      </span>
    </Link>
  );
}
