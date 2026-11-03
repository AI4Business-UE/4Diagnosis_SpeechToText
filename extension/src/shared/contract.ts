import type { PatientMetadata } from "./metadata";
import type { TransferReport } from "./report";

/**
 * Versioned app-page <-> extension contract carried over window.postMessage
 * on the TRANSFER_CHANNEL. The app page broadcasts a transfer-request;
 * the app-page content script relays it to the background and posts the
 * resulting transfer-result back to the page. See docs/adr/0002.
 */
export const TRANSFER_CHANNEL = "rx-transfer";
export const TRANSFER_CONTRACT_VERSION = 1;

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

export type TransferWindowMessage = TransferRequestMessage | TransferResultMessage;

export function isTransferRequest(data: unknown): data is TransferRequestMessage {
  const message = data as Partial<TransferRequestMessage>;
  return (
    message?.channel === TRANSFER_CHANNEL &&
    message?.type === "transfer-request" &&
    typeof message.transferId === "string" &&
    typeof message.metadata === "object" &&
    message.metadata !== null
  );
}

/** Internal chrome.runtime message shapes (content script <-> background). */
export type BackgroundRequest = {
  type: "rx:transfer-request";
  version: number;
  transferId: string;
  metadata: PatientMetadata;
};
