import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";

const createdAt = "2026-05-05T12:00:00.000Z";

const extractedMenu = {
  id: "66666666-6666-6666-6666-666666666666",
  restaurant_name: "Dinner menu",
  currency: "EUR",
  language: "it",
  confidence_score: 0.92,
  validation_status: "valid",
  canonical_json: {
    restaurant: "Dinner menu",
    currency: "EUR",
    language: "it",
    source: { type: "text", value: "Antipasti\nBruschetta 6,50" },
    categories: [
      {
        name: "Antipasti",
        items: [
          {
            name: "Bruschetta",
            description: "Tomato toast",
            price: 6.5,
            price_text: "€ 6,50",
            allergens: ["gluten"],
            tags: ["vegetarian"],
            variants: [],
          },
        ],
      },
    ],
    confidence_score: 0.92,
    validation_warnings: [
      {
        code: "normalized_price",
        message: "Comma decimal normalized",
        path: "categories.0.items.0.price",
        context: {},
      },
    ],
  },
  created_at: createdAt,
  updated_at: createdAt,
};

const textImport = {
  id: "11111111-1111-1111-1111-111111111111",
  input_type: "text",
  source_value: "Antipasti\nBruschetta 6,50",
  source_filename: "Dinner menu",
  status: "succeeded",
  error_message: null,
  model_used: "fake-gemini-menu-extractor",
  duration_ms: null,
  created_at: createdAt,
  updated_at: createdAt,
  extracted_menu: extractedMenu,
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
      message: "Menu extraction succeeded",
      event_metadata: { extracted_menu_id: extractedMenu.id },
      created_at: createdAt,
    },
  ],
};

const urlImport = {
  id: "44444444-4444-4444-4444-444444444444",
  input_type: "url",
  source_value: "Menu\nBruschetta 6,50",
  source_filename: "https://restaurant.example/menu",
  status: "pending",
  error_message: null,
  model_used: null,
  duration_ms: null,
  created_at: createdAt,
  updated_at: createdAt,
  extracted_menu: {
    ...extractedMenu,
    id: "77777777-7777-7777-7777-777777777777",
    restaurant_name: "Restaurant Example",
    canonical_json: {
      ...extractedMenu.canonical_json,
      restaurant: "Restaurant Example",
      source: { type: "url", value: "https://restaurant.example/menu" },
    },
  },
  events: [
    {
      id: "55555555-5555-5555-5555-555555555555",
      stage: "created",
      message: "URL import created",
      event_metadata: { requested_url: "https://restaurant.example/menu" },
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
    expect(screen.getByText("succeeded")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith("/api/imports");
  });

  it("creates a pasted text import and shows extracted results", async () => {
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
    expect(await screen.findByRole("heading", { name: "Dinner menu" })).toBeInTheDocument();
    expect(screen.getByText("Bruschetta")).toBeInTheDocument();
    expect((screen.getByLabelText("Canonical JSON editor") as HTMLTextAreaElement).value).toContain(
      '"restaurant": "Dinner menu"',
    );
    expect(screen.getByText("Comma decimal normalized")).toBeInTheDocument();
  });

  it("creates a URL import", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse([]))
      .mockResolvedValueOnce(jsonResponse(urlImport, { status: 201 }))
      .mockResolvedValueOnce(jsonResponse([urlImport]));

    render(<App />);

    await screen.findByText("No imports yet.");
    await userEvent.click(screen.getByRole("tab", { name: "URL" }));
    await userEvent.type(screen.getByLabelText("Menu page URL"), "https://restaurant.example/menu");
    await userEvent.click(screen.getByRole("button", { name: "Create import" }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/imports/url",
        expect.objectContaining({
          body: JSON.stringify({ url: "https://restaurant.example/menu" }),
          method: "POST",
        }),
      );
    });
    expect(await screen.findAllByText("https://restaurant.example/menu")).toHaveLength(2);
    expect(screen.getByText(/Bruschetta 6,50/)).toBeInTheDocument();
  });

  it("validates and saves edited JSON", async () => {
    const updatedImport = {
      ...textImport,
      extracted_menu: {
        ...extractedMenu,
        restaurant_name: "Corrected menu",
        canonical_json: {
          ...extractedMenu.canonical_json,
          restaurant: "Corrected menu",
        },
      },
    };
    fetchMock
      .mockResolvedValueOnce(jsonResponse([textImport]))
      .mockResolvedValueOnce(jsonResponse(textImport))
      .mockResolvedValueOnce(jsonResponse(updatedImport))
      .mockResolvedValueOnce(jsonResponse([updatedImport]));

    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: /Dinner menu/ }));
    const editor = await screen.findByLabelText("Canonical JSON editor");
    fireEvent.change(editor, { target: { value: JSON.stringify(updatedImport.extracted_menu.canonical_json, null, 2) } });
    await userEvent.click(screen.getByRole("button", { name: "Save JSON" }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/imports/11111111-1111-1111-1111-111111111111/json",
        expect.objectContaining({
          method: "PATCH",
        }),
      );
    });
    expect(await screen.findByText("JSON saved")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Corrected menu" })).toBeInTheDocument();
  });

  it("shows client-side validation errors for invalid JSON edits", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse([textImport])).mockResolvedValueOnce(jsonResponse(textImport));

    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: /Dinner menu/ }));
    const editor = await screen.findByLabelText("Canonical JSON editor");
    fireEvent.change(editor, { target: { value: '{"restaurant": ""}' } });
    await userEvent.click(screen.getByRole("button", { name: "Save JSON" }));

    expect(await screen.findByText(/restaurant:/)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
