import { describe, expect, it } from "vitest";

import { highlight, searchWords } from "./SearchPanel";

describe("searchWords", () => {
  it("keeps meaningful words only", () => {
    expect(searchWords("How is the API secured?")).toEqual(["api", "secured"]);
    expect(searchWords("the is and")).toEqual([]);
  });
});

describe("highlight", () => {
  it("marks whole words, case-insensitively", () => {
    expect(highlight("The Warranty covers defects", "warranty defects")).toEqual([
      "The ",
      "Warranty",
      " covers ",
      "defects",
      "",
    ]);
  });

  it("never matches inside a longer word", () => {
    expect(highlight("rather than the API", "the")).toEqual(["rather than the API"]);
    expect(highlight("scanned scan", "scan")).toEqual(["scanned ", "scan", ""]);
  });

  it("handles regex characters and empty queries safely", () => {
    expect(highlight("a refund of (500) applies", "(500)")).toEqual(["a refund of (", "500", ") applies"]);
    expect(highlight("plain text", "   ")).toEqual(["plain text"]);
    expect(highlight("costs 50 each", "50")).toEqual(["costs 50 each"]); // under 3 characters: not a search word
  });
});
