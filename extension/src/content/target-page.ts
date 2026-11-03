import { resolveFieldControls } from "../core/mapping-resolver";
import { fillControl } from "../core/form-filler";
import type { MappingSet } from "../shared/config";
import type { FieldResult } from "../shared/report";
import type { PatientMetadata, MetadataKey } from "../shared/metadata";

type FillMessage = {
  type: "rx:fill";
  transferId: string;
  metadata: PatientMetadata;
  mapping: MappingSet;
};

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type !== "rx:fill") return false;

  const request = message as FillMessage;
  const results = applyTransfer(document, request.metadata, request.mapping);
  sendResponse({ results });
  return true;
});

/**
 * Resolves every mapped field and fills the ones found on the page.
 * Never submits the form and never clicks anything (glossary: Transfer).
 */
function applyTransfer(
  doc: Document,
  metadata: PatientMetadata,
  mapping: MappingSet,
): FieldResult[] {
  const resolved = resolveFieldControls(doc, mapping);
  const results: FieldResult[] = [];

  for (const entry of resolved) {
    if (entry.status === "not_found" || !entry.element) {
      results.push({ field: entry.field, status: "not_found" });
      continue;
    }
    try {
      fillControl(entry.element, metadata[entry.field as MetadataKey] ?? "");
      results.push({ field: entry.field, status: "filled", strategy: entry.strategy });
    } catch (error) {
      results.push({
        field: entry.field,
        status: "failed",
        strategy: entry.strategy,
        detail: error instanceof Error ? error.message : undefined,
      });
    }
  }

  return results;
}
