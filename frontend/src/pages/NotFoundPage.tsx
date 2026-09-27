import { Link } from "react-router";

import { Brand } from "../components/Brand";

export function NotFoundPage() {
  return (
    <main className="full-page">
      <Brand />
      <h1>Page not found</h1>
      <p className="muted">The page you're looking for doesn't exist.</p>
      <Link to="/" className="button button-primary">
        Go to Paperchat
      </Link>
    </main>
  );
}
