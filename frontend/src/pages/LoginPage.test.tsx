import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { createQueryClient } from "../api/queries";
import type { PublicConfig } from "../api/types";
import { LoginPage } from "./LoginPage";

function mockApi(config: Partial<PublicConfig>) {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    if (url.endsWith("/api/me")) {
      return new Response('{"detail":"Please sign in to continue."}', { status: 401, headers: { "content-type": "application/json" } });
    }
    const body: PublicConfig = {
      max_upload_mb: 25,
      max_pages: 500,
      google_enabled: false,
      dev_login_enabled: false,
      ai_enabled: true,
      ...config,
    };
    return new Response(JSON.stringify(body), { status: 200, headers: { "content-type": "application/json" } });
  });
}

function renderLogin(path = "/login") {
  const router = createMemoryRouter([{ path: "/login", element: <LoginPage /> }], { initialEntries: [path] });
  render(
    <QueryClientProvider client={createQueryClient()}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

afterEach(() => vi.restoreAllMocks());

describe("LoginPage", () => {
  it("offers Google sign-in when configured", async () => {
    mockApi({ google_enabled: true });
    renderLogin();
    const link = await screen.findByRole("link", { name: /continue with google/i });
    expect(link).toHaveAttribute("href", "/auth/google/login");
    expect(screen.queryByRole("button", { name: /local developer/i })).not.toBeInTheDocument();
  });

  it("explains a failed Google sign-in", async () => {
    mockApi({ google_enabled: true });
    renderLogin("/login?error=google");
    expect(await screen.findByRole("alert")).toHaveTextContent("Google sign-in didn't complete");
  });

  it("warns when no sign-in method is configured", async () => {
    mockApi({});
    renderLogin();
    expect(await screen.findByText(/sign-in isn't configured/i)).toBeInTheDocument();
  });
});
