import { Menu } from "lucide-react";
import { useState } from "react";
import { Outlet, useLocation } from "react-router";

import { Brand } from "./Brand";
import { Sidebar } from "./Sidebar";

export function AppShell() {
  const location = useLocation();
  const [openedAt, setOpenedAt] = useState<string | null>(null);
  // The mobile drawer closes itself whenever the route changes.
  const drawerOpen = openedAt === location.key;

  return (
    <div className={`app-shell${drawerOpen ? " drawer-open" : ""}`}>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <header className="mobile-bar">
        <button
          type="button"
          className="icon-button"
          aria-label="Open documents"
          aria-expanded={drawerOpen}
          onClick={() => setOpenedAt(location.key)}
        >
          <Menu size={20} aria-hidden />
        </button>
        <Brand />
      </header>
      <Sidebar onNavigate={() => setOpenedAt(null)} />
      <button type="button" className="drawer-scrim" aria-label="Close documents" onClick={() => setOpenedAt(null)} />
      <main id="main" className="main">
        <Outlet />
      </main>
    </div>
  );
}
