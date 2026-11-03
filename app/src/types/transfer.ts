import type { PatientMetadata } from "./metadata";

/**
 * App <-> Transfer extension contract, duplicated from
 * extension/src/shared/contract.ts on purpose (docs/adr/0002).
 * Keep both sides in sync; the `version` guards drift.
 */
export const TRANSFER_CHANNEL = "rx-transfer";
export const TRANSFER_CONTRACT_VERSION = 1;

export type TransferFieldStatus = "filled" | "not_found" | "failed";

export type TransferFieldResult = {
  field: keyof PatientMetadata;
  status: TransferFieldStatus;
  strategy?: "selector" | "label";
  detail?: string;
};

export type TransferReport = {
  transferId: string;
  timestamp: string;
  overall: "ok" | "partial" | "error";
  targetUrl?: string;
  durationMs: number;
  fields: TransferFieldResult[];
  detail?: string;
};

export type TransferRequestMessage = {
  channel: typeof TRANSFER_CHANNEL;
  version: number;
  type: "transfer-request";
  transferId: string;
  metadata: PatientMetadata;
};

export type TransferResultMessage = {
  channel: typeof TRANSFER_CHANNEL;
  version: number;
  type: "transfer-result";
  transferId: string;
  report: TransferReport;
};
