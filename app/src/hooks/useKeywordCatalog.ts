import { useCallback, useEffect, useState } from "react";
import { API_URL } from "@/config";

export type KeywordEntry = { id: number; text: string };

function normalizeKeywordText(text: string): string | null {
  const normalized = text.trim();
  if (!normalized) return "Wpisz hasło.";
  if (normalized.length > 50) return "Hasło może mieć maksymalnie 50 znaków.";
  if (/[<>\r\n]/u.test(normalized)) {
    return "Hasło musi być zapisane w jednej linii i nie może zawierać znaków < ani >.";
  }
  return null;
}

function errorMessageFrom(body: unknown): string | null {
  if (!body || typeof body !== "object") return null;
  const detail = (body as { detail?: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object") {
    const messages = Object.values(detail).flatMap((value) => Array.isArray(value) ? value : [value]);
    const message = messages.find((value): value is string => typeof value === "string");
    if (message) return message;
  }
  return null;
}

export default function useKeywordCatalog() {
  const [keywords, setKeywords] = useState<KeywordEntry[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const refresh = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_URL}/keyword/list`);
      const body = await response.json();
      if (!response.ok) {
        setError(errorMessageFrom(body) ?? "Nie udało się pobrać Słownika.");
        return;
      }
      if (!Array.isArray(body)) {
        setError("Otrzymano nieprawidłową odpowiedź serwera.");
        return;
      }
      setKeywords(body as KeywordEntry[]);
    } catch {
      setError("Nie udało się połączyć z serwerem. Spróbuj ponownie.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const mutate = useCallback(async (path: string, method: string, text?: string) => {
    setError(null);
    try {
      const response = await fetch(`${API_URL}${path}`, {
        method,
        ...(text === undefined ? {} : {
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text }),
        }),
      });
      if (!response.ok) {
        const body = response.status === 204 ? null : await response.json().catch(() => null);
        setError(errorMessageFrom(body) ?? "Nie udało się zapisać zmian w Słowniku.");
        return false;
      }
      await refresh();
      return true;
    } catch {
      setError("Nie udało się połączyć z serwerem. Spróbuj ponownie.");
      return false;
    }
  }, [refresh]);

  const create = useCallback((text: string) => {
    const validationError = normalizeKeywordText(text);
    if (validationError) {
      setError(validationError);
      return Promise.resolve(false);
    }
    if (keywords.length >= 200) {
      setError("Słownik może zawierać maksymalnie 200 haseł.");
      return Promise.resolve(false);
    }
    return mutate("/keyword/create", "POST", text.trim());
  }, [keywords.length, mutate]);

  const update = useCallback((id: number, text: string) => {
    const validationError = normalizeKeywordText(text);
    if (validationError) {
      setError(validationError);
      return Promise.resolve(false);
    }
    return mutate(`/keyword/update/${id}`, "PUT", text.trim());
  }, [mutate]);
  const remove = useCallback((id: number) => mutate(`/keyword/delete/${id}`, "DELETE"), [mutate]);

  return { keywords, error, isLoading, refresh, create, update, remove };
}
