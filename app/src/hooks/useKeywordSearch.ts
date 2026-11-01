import { useMemo, useState } from "react";
import type { KeywordEntry } from "@/hooks/useKeywordCatalog";

function searchKey(value: string): string {
  return value
    .toLocaleLowerCase("pl")
    .replaceAll("ł", "l")
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "");
}

export default function useKeywordSearch(keywords: KeywordEntry[]) {
  const [query, setQuery] = useState("");
  const visibleKeywords = useMemo(() => {
    const normalizedQuery = searchKey(query.trim());
    const collator = new Intl.Collator("pl", { sensitivity: "base" });
    return keywords
      .filter((keyword) => searchKey(keyword.text).includes(normalizedQuery))
      .sort((left, right) => collator.compare(left.text, right.text));
  }, [keywords, query]);

  return { query, setQuery, visibleKeywords };
}
