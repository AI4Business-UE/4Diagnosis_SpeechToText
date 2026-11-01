import { ArrowLeft, Plus, Search } from "lucide-react";
import { Link } from "react-router-dom";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import useKeywordCatalog, { type KeywordEntry } from "@/hooks/useKeywordCatalog";
import useKeywordSearch from "@/hooks/useKeywordSearch";
import { Keyword } from "@/components/Keyword";

export default function KeywordDictionary() {
  const { keywords, error, isLoading, create, update, remove } = useKeywordCatalog();
  const { query, setQuery, visibleKeywords } = useKeywordSearch(keywords);
  const [newKeyword, setNewKeyword] = useState("");
  const [isAdding, setIsAdding] = useState(false);

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const created = await create(newKeyword);
    if (created) {
      setNewKeyword("");
      setIsAdding(false);
    }
  }

  async function handleDelete(keyword: KeywordEntry) {
    if (!window.confirm(`Czy na pewno chcesz usunąć hasło „${keyword.text}”?`)) return;
    await remove(keyword.id);
  }

  return (
    <main className="min-h-screen w-full bg-gradient-to-br from-blue-50 to-indigo-100 p-4 sm:p-8">
      <div className="mx-auto w-full max-w-4xl">
        <Link
          to="/record-description"
          className="mb-6 inline-flex items-center gap-2 rounded-md px-2 py-2 text-blue-800 hover:bg-white/70 focus-visible:outline focus-visible:outline-2"
        >
          <ArrowLeft size={18} />
          Wróć do nagrywania
        </Link>

        <Card className="p-5 shadow-xl sm:p-8">
          <header className="mb-6">
            <h1 className="text-center text-3xl font-semibold">Słownik</h1>
            <p className="mt-2 text-center text-slate-600">
              Hasła są używane podczas każdej nowej transkrypcji. ({keywords.length}/200)
            </p>
          </header>

          <label className="relative mb-5 block">
            <span className="sr-only">Szukaj haseł</span>
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" size={18} />
            <input
              aria-label="Szukaj haseł"
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Szukaj haseł"
              className="w-full rounded-lg border border-slate-300 bg-white py-3 pl-10 pr-3 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-200"
            />
          </label>

          {error && <p role="alert" className="mb-4 text-center font-medium text-red-700">{error}</p>}

          {isLoading ? (
            <p className="py-8 text-center text-slate-600">Wczytywanie Słownika…</p>
          ) : (
            <ul aria-label="Lista haseł" className="flex max-h-[55vh] flex-col gap-3 overflow-y-auto px-1">
              {visibleKeywords.map((keyword) => (
                <Keyword
                  key={keyword.id}
                  text={keyword.text}
                  onKeywordUpdate={(text) => update(keyword.id, text)}
                  onKeywordDelete={() => handleDelete(keyword)}
                />
              ))}
              {visibleKeywords.length === 0 && (
                <li className="py-8 text-center text-slate-600">
                  {keywords.length === 0 ? "Słownik jest pusty." : "Brak haseł pasujących do wyszukiwania."}
                </li>
              )}
            </ul>
          )}

          {isAdding ? (
            <form onSubmit={handleCreate} className="mt-5 flex flex-col gap-3 rounded-xl border border-slate-200 p-3 shadow-sm sm:flex-row">
              <label className="flex-1">
                <span className="sr-only">Nowe hasło</span>
                <input
                  autoFocus
                  aria-label="Nowe hasło"
                  type="text"
                  maxLength={50}
                  value={newKeyword}
                  onChange={(event) => setNewKeyword(event.target.value)}
                  placeholder="Wpisz hasło"
                  className="w-full rounded-lg border border-slate-300 p-2.5 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-200"
                />
              </label>
              <div className="flex justify-end gap-2">
                <Button type="button" variant="outline" aria-label="Anuluj dodawanie" onClick={() => setIsAdding(false)}>
                  <ArrowLeft />
                  Anuluj
                </Button>
                <Button type="submit" disabled={keywords.length >= 200} className="bg-blue-600 text-white hover:bg-blue-700">
                  <Plus />
                  Zapisz hasło
                </Button>
              </div>
            </form>
          ) : (
            <Button
              className="mt-5 w-full"
              variant="secondary"
              disabled={keywords.length >= 200}
              onClick={() => setIsAdding(true)}
            >
              <Plus />
              Dodaj nowe hasło
            </Button>
          )}
        </Card>
      </div>
    </main>
  );
}
