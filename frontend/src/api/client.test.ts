import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, api, messageFor, request } from "./client";
import { pollDelay } from "./queries";
import type { PaperDocument } from "./types";

function respond(status: number, body: string, contentType = "application/json") {
  return vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(body, { status, headers: { "content-type": contentType } }));
}

afterEach(() => vi.restoreAllMocks());

describe("request", () => {
  it("returns parsed JSON and sends cookies", async () => {
    const fetchMock = respond(200, '{"ok":true}');
    await expect(request("/api/config")).resolves.toEqual({ ok: true });
    expect(fetchMock).toHaveBeenCalledWith("/api/config", expect.objectContaining({ credentials: "include" }));
  });

  it("uses the API's detail message for errors", async () => {
    respond(409, '{"detail":"This document isn\'t ready yet."}');
    await expect(request("/api/x")).rejects.toMatchObject({ status: 409, message: "This document isn't ready yet." });
  });

  it("survives non-JSON error pages from proxies", async () => {
    respond(502, "<html>Bad gateway</html>", "text/html");
    await expect(request("/api/x")).rejects.toMatchObject({
      status: 502,
      message: "The service is temporarily unreachable. Please try again.",
    });
  });

  it("reports network failures as offline", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("Failed to fetch"));
    const error = await request("/api/x").catch((caught: unknown) => caught);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(0);
  });
});

describe("api.me", () => {
  it("treats 401 as signed out rather than an error", async () => {
    respond(401, '{"detail":"Please sign in to continue."}');
    await expect(api.me()).resolves.toBeNull();
  });
});

describe("messageFor", () => {
  it("summarises validation errors", () => {
    expect(messageFor(422, { detail: [{ msg: "too long" }] })).toBe("Please check what you entered and try again.");
  });
});

describe("pollDelay", () => {
  const doc = (status: PaperDocument["status"]) => ({ status }) as PaperDocument;

  it("stops polling once processing ends", () => {
    expect(pollDelay(doc("ready"), 3)).toBe(false);
    expect(pollDelay(doc("failed"), 3)).toBe(false);
    expect(pollDelay(undefined, 0)).toBe(false);
  });

  it("backs off up to ten seconds", () => {
    expect(pollDelay(doc("queued"), 0)).toBe(1500);
    expect(pollDelay(doc("processing"), 50)).toBe(10_000);
  });
});
