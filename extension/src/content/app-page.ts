import { sendMessageToRuntime } from "../shared/chrome-api";
import {
  TRANSFER_CHANNEL,
  TRANSFER_CONTRACT_VERSION,
  isTransferRequest,
  type TransferResultMessage,
} from "../shared/contract";
import type { TransferReport } from "../shared/report";

/**
 * App-page content script: bridges the versioned window.postMessage contract
 * (ADR-0002) to the extension background, and posts the Transfer Report back
 * to the app page as a transfer-result.
 */

window.addEventListener("message", (event) => {
  if (event.source !== window) return;
  if (!isTransferRequest(event.data)) return;

  sendMessageToRuntime({
    type: "rx:transfer-request",
    version: event.data.version,
    transferId: event.data.transferId,
    metadata: event.data.metadata,
  }).catch(() => {
    // background errors are surfaced through the transfer-result message;
    // a rejected send means the extension context is unavailable
  });
});

chrome.runtime.onMessage.addListener((message) => {
  if (message?.type === "rx:transfer-result") {
    const report = message.report as TransferReport;
    const response: TransferResultMessage = {
      channel: TRANSFER_CHANNEL,
      version: TRANSFER_CONTRACT_VERSION,
      type: "transfer-result",
      transferId: report.transferId,
      report,
    };
    window.postMessage(response, window.location.origin);
  }
  return false;
});
