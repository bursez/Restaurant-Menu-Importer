import "@testing-library/jest-dom/vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";

const createdAt = "2026-05-05T12:00:00.000Z";

const textImport = {
  id: "11111111-1111-1111-1111-111111111111",
  input_type: "text",
  source_value: "Antipasti\nBruschetta 6,50",
  source_filename: "Dinner menu",
  status: "pending",
  error_message: null,
  model_used: null,
  duration_ms: null,
  created_at: createdAt,
  updated_at: createdAt,
  events: [
    {
      id: "22222222-2222-2222-2222-222222222222",
      stage: "created",
      message: "Text import created",
      event_metadata: { character_count: 25, line_count: 2 },
      created_at: createdAt,
    },
    {
      id: "33333333-3333-3333-3333-333333333333",
      stage: "ai_extraction",
      message: "AI extraction is not available yet for text imports",
      event_metadata: { placeholder: true },
      created_at: createdAt,
    },
  ],
};

function jsonResponse(payload: unknown, init?: ResponseInit) {
  return new Response(JSON.stringify(payload), {
    headers: { "Content-Type": "application/json" },
    status: 200,
    ...init,
  });
}

describe("App", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    fetchMock.mockReset();
  });

  it("loads import history", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse([textImport]));

    render(<App />);

    expect(await screen.findByRole("heading", { name: "History" })).toBeInTheDocument();
    expect(await screen.findByText("Dinner menu")).toBeInTheDocument();
    expect(screen.getByText("pending")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith("/api/imports");
  });

  it("creates a pasted text import and shows the placeholder detail", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse([]))
      .mockResolvedValueOnce(jsonResponse(textImport, { status: 201 }))
      .mockResolvedValueOnce(jsonResponse([textImport]));

    render(<App />);

    await screen.findByText("No imports yet.");
    await userEvent.type(screen.getByLabelText("Source name"), "Dinner menu");
    await userEvent.type(screen.getByLabelText("Menu text"), "Antipasti\nBruschetta 6,50");
    await userEvent.click(screen.getByRole("button", { name: "Create import" }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/imports/text",
        expect.objectContaining({
          body: JSON.stringify({
            text: "Antipasti\nBruschetta 6,50",
            source_name: "Dinner menu",
          }),
          method: "POST",
        }),
      );
    });
    expect(await screen.findByText("AI extraction pending")).toBeInTheDocument();
    expect(screen.getByText("Stored source text is ready for the Gemini extraction milestone.")).toBeInTheDocument();
  });
});
