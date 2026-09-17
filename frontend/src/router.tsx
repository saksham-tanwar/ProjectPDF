import { createBrowserRouter } from "react-router";

import { AppShell } from "./components/AppShell";
import { RequireAuth } from "./components/RequireAuth";
import { DocumentPage } from "./pages/DocumentPage";
import { HomePage } from "./pages/HomePage";
import { LoginPage } from "./pages/LoginPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { PrivacyPage } from "./pages/PrivacyPage";

export const router = createBrowserRouter([
  { path: "/login", element: <LoginPage /> },
  { path: "/privacy", element: <PrivacyPage /> },
  {
    element: (
      <RequireAuth>
        <AppShell />
      </RequireAuth>
    ),
    children: [
      { index: true, element: <HomePage /> },
      { path: "documents/:id", element: <DocumentPage /> },
    ],
  },
  { path: "*", element: <NotFoundPage /> },
]);
