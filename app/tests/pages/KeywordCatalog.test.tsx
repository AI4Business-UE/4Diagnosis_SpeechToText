import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import KeywordDictionary from "@/components/KeywordDictionary";

type Keyword = { id: number; text: string };

let catalog: Keyword[];

function renderCatalog() {
  return render(
    <MemoryRouter initialEntries={["/keywords"]}>
      <Routes>
        <Route path="/keywords" element={<KeywordDictionary />} />
        <Route path="/record-description" element={<h1>Nagrywanie</h1>} />
      </Routes>
    </MemoryRouter>,
  );
}

function mockCatalogApi() {
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const method = init?.method ?? "GET";
    if (url.endsWith("/keyword/list")) {
      return new Response(JSON.stringify(catalog), { status: 200 });
    }
    if (url.endsWith("/keyword/create")) {
      const payload = JSON.parse(String(init?.body)) as { text: string };
      const created = { id: 2, text: payload.text };
      catalog = [...catalog, created];
      return new Response(JSON.stringify(created), { status: 201 });
    }
    if (url.endsWith("/keyword/update/1")) {
      const payload = JSON.parse(String(init?.body)) as { text: string };
      catalog = catalog.map((keyword) => keyword.id === 1 ? { ...keyword, text: payload.text } : keyword);
      return new Response(JSON.stringify(catalog.find((keyword) => keyword.id === 1)), { status: 200 });
    }
    if (url.endsWith("/keyword/delete/1") && method === "DELETE") {
      catalog = catalog.filter((keyword) => keyword.id !== 1);
      return new Response(null, { status: 204 });
    }
    return new Response(JSON.stringify({ detail: "Nieznany adres API." }), { status: 404 });
  }));
}

describe("strona Słownika", () => {
  beforeEach(() => {
    catalog = [{ id: 1, text: "Żółciak" }];
    mockCatalogApi();
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("filters without Polish diacritics and navigates back to recording", async () => {
    const user = userEvent.setup();
    renderCatalog();

    expect(await screen.findByText("Żółciak")).toBeTruthy();
    await user.type(screen.getByRole("searchbox", { name: "Szukaj haseł" }), "zolciak");
    expect(screen.getByText("Żółciak")).toBeTruthy();

    await user.click(screen.getByRole("link", { name: "Wróć do nagrywania" }));
    expect(await screen.findByRole("heading", { name: "Nagrywanie" })).toBeTruthy();
  });

  it("sorts the catalog using Polish alphabetical rules", async () => {
    catalog = [
      { id: 1, text: "żaba" },
      { id: 3, text: "zebra" },
      { id: 2, text: "Łoś" },
    ];
    renderCatalog();

    const list = await screen.findByRole("list", { name: "Lista haseł" });
    expect(within(list).getAllByRole("listitem").map((item) => item.textContent)).toEqual([
      expect.stringContaining("Łoś"),
      expect.stringContaining("zebra"),
      expect.stringContaining("żaba"),
    ]);
  });

  it("creates, edits, and confirms deletion of catalog keywords", async () => {
    const user = userEvent.setup();
    vi.spyOn(window, "confirm").mockReturnValueOnce(false).mockReturnValueOnce(true);
    renderCatalog();

    await screen.findByText("Żółciak");
    await user.click(screen.getByRole("button", { name: "Dodaj nowe hasło" }));
    await user.type(screen.getByRole("textbox", { name: "Nowe hasło" }), "Torbiel");
    await user.click(screen.getByRole("button", { name: "Zapisz hasło" }));
    expect(await screen.findByText("Torbiel")).toBeTruthy();

    const row = screen.getByText("Żółciak").closest("li");
    await user.click(within(row as HTMLElement).getByRole("button", { name: "Edytuj Żółciak" }));
    const editInput = within(row as HTMLElement).getByRole("textbox", { name: "Edytuj hasło" });
    await user.clear(editInput);
    await user.type(editInput, "Żółciak nowy");
    await user.click(within(row as HTMLElement).getByRole("button", { name: "Zapisz zmianę" }));
    expect(await screen.findByText("Żółciak nowy")).toBeTruthy();

    await user.click(screen.getByRole("button", { name: "Usuń Żółciak nowy" }));
    expect(screen.getByText("Żółciak nowy")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Usuń Żółciak nowy" }));
    expect(window.confirm).toHaveBeenCalledWith("Czy na pewno chcesz usunąć hasło „Żółciak nowy”?");
    await waitFor(() => expect(screen.queryByText("Żółciak nowy")).toBeNull());
  });

  it("shows localized API errors", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === "POST") {
        return new Response(JSON.stringify({ detail: { text: ["Hasło o takiej nazwie już istnieje."] } }), { status: 400 });
      }
      return new Response(JSON.stringify(catalog), { status: 200 });
    }));
    const user = userEvent.setup();
    renderCatalog();

    await screen.findByText("Żółciak");
    await user.click(screen.getByRole("button", { name: "Dodaj nowe hasło" }));
    await user.type(screen.getByRole("textbox", { name: "Nowe hasło" }), "Żółciak");
    await user.click(screen.getByRole("button", { name: "Zapisz hasło" }));

    expect((await screen.findByRole("alert")).textContent).toContain("Hasło o takiej nazwie już istnieje.");
  });
});
