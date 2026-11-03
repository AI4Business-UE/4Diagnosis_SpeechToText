import { METADATA_KEYS, type MetadataKey } from "../shared/metadata";
import type { FieldMapping, MappingSet } from "../shared/config";

export type ResolvedField = {
  field: MetadataKey;
  status: "found" | "not_found";
  strategy?: "selector" | "label";
  element?: HTMLElement;
};

/**
 * Resolves each Patient Metadata field of a Field Mapping to its control on the
 * Target Page: selector candidates in order first (see FieldMapping.selectors).
 * Label-text fallback is applied when no selector hits.
 */
export function resolveFieldControls(doc: Document, mapping: MappingSet): ResolvedField[] {
  return METADATA_KEYS.map((field) => resolveOne(doc, field, mapping[field]));
}

function resolveOne(doc: Document, field: MetadataKey, entry: FieldMapping): ResolvedField {
  for (const selector of entry.selectors) {
    let candidate: Element | null = null;
    try {
      candidate = doc.querySelector(selector);
    } catch {
      continue; // an invalid selector is simply a missed candidate
    }
    if (candidate instanceof HTMLElement) {
      return { field, status: "found", strategy: "selector", element: candidate };
    }
  }

  const byLabel = findByLabelText(doc, entry.label);
  if (byLabel) {
    return { field, status: "found", strategy: "label", element: byLabel };
  }

  return { field, status: "not_found" };
}

/** Case/space-insensitive, trailing-colon-insensitive label text match. */
function normalizeLabel(text: string): string {
  return text.replace(/\s+/g, " ").replace(/[:\s]+$/g, "").trim().toLowerCase();
}

function findByLabelText(doc: Document, label: string): HTMLElement | undefined {
  const wanted = normalizeLabel(label);
  if (!wanted) return undefined;

  for (const labelElement of Array.from(doc.querySelectorAll("label"))) {
    if (normalizeLabel(labelElement.textContent ?? "") !== wanted) continue;

    if (labelElement.htmlFor) {
      const bound = doc.getElementById(labelElement.htmlFor);
      if (bound instanceof HTMLElement && isFillable(bound)) return bound;
    }
    const wrapped = Array.from(labelElement.querySelectorAll("input, select, textarea"))[0];
    if (wrapped instanceof HTMLElement) return wrapped;
  }
  return undefined;
}

function isFillable(element: HTMLElement): boolean {
  const tag = element.tagName.toLowerCase();
  return tag === "input" || tag === "select" || tag === "textarea";
}
