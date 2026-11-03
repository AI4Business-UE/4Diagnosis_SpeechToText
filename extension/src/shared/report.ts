import type { MetadataKey } from "./metadata";

/** Outcome for one Patient Metadata field during a Transfer. Never contains the value. */
export type FieldResult = {
  field: MetadataKey;
  status: "filled" | "not_found" | "failed";
  strategy?: "selector" | "label";
  detail?: string;
};

/**
 * Transfer Report envelope, per ADR-0002 and docs/adr/0001 context.
 * Reports are sent back to the app tab and kept (last 20) for the options page.
 */
export type TransferReport = {
  transferId: string;
  timestamp: string;
  overall: "ok" | "partial" | "error";
  targetUrl?: string;
  durationMs: number;
  fields: FieldResult[];
  detail?: string;
};
