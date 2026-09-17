import { describe, expect, it } from "vitest";

import { formatBytes, formatRelativeDate, initials, validatePdf } from "./format";

describe("validatePdf", () => {
  const file = (name: string, size: number, type = "application/pdf") => new File([new Uint8Array(size)], name, { type });

  it("accepts PDFs within the limit", () => {
    expect(validatePdf(file("a.pdf", 1000), 1)).toBeNull();
    expect(validatePdf(file("A.PDF", 1000, ""), 1)).toBeNull();
  });

  it("rejects other types, empty files and oversized files", () => {
    expect(validatePdf(file("notes.txt", 10, "text/plain"), 1)).toBe("Please choose a PDF file.");
    expect(validatePdf(file("empty.pdf", 0), 1)).toBe("This file is empty.");
    expect(validatePdf(file("big.pdf", 2 * 1024 * 1024), 1)).toBe("This PDF is larger than 1 MB.");
  });
});

describe("formatting", () => {
  it("formats sizes", () => {
    expect(formatBytes(512)).toBe("512 B");
    expect(formatBytes(2048)).toBe("2 KB");
    expect(formatBytes(3 * 1024 * 1024)).toBe("3.0 MB");
    expect(formatBytes(null)).toBe("");
  });

  it("formats recent dates relatively", () => {
    const now = new Date("2026-09-17T12:00:00Z");
    expect(formatRelativeDate("2026-09-17T11:59:30Z", now)).toBe("just now");
    expect(formatRelativeDate("2026-09-17T11:15:00Z", now)).toBe("45 min ago");
    expect(formatRelativeDate("2026-09-15T12:00:00Z", now)).toBe("2 d ago");
  });

  it("builds initials", () => {
    expect(initials("Ada Lovelace")).toBe("AL");
    expect(initials("plato")).toBe("PL");
    expect(initials("  ")).toBe("?");
  });
});
