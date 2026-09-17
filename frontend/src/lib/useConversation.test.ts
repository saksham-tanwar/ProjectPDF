import { describe, expect, it } from "vitest";

import { historyFor, type ChatMessage } from "./useConversation";

const message = (id: number, role: ChatMessage["role"], text: string, extra: Partial<ChatMessage> = {}): ChatMessage => ({
  id: String(id),
  role,
  text,
  status: "done",
  ...extra,
});

describe("historyFor", () => {
  it("keeps the most recent completed turns in order", () => {
    const messages = Array.from({ length: 10 }, (_, index) =>
      message(index, index % 2 ? "assistant" : "user", `turn ${index}`),
    );
    expect(historyFor(messages).map((turn) => turn.content)).toEqual(["turn 4", "turn 5", "turn 6", "turn 7", "turn 8", "turn 9"]);
  });

  it("skips pending, failed and no-match messages and truncates long answers", () => {
    const history = historyFor([
      message(1, "user", "q1"),
      message(2, "assistant", "x".repeat(5000), { mode: "llm" }),
      message(3, "user", "q2"),
      message(4, "assistant", "error", { status: "error" }),
      message(5, "assistant", "nothing found", { mode: "none" }),
      message(6, "assistant", "", { status: "pending" }),
    ]);
    expect(history.map((turn) => turn.role)).toEqual(["user", "assistant", "user"]);
    expect(history[1]?.content).toHaveLength(4000);
  });
});
