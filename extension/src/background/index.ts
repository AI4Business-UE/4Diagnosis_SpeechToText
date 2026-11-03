import { TRANSFER_CONTRACT_VERSION, type BackgroundRequest } from "../shared/contract";
import {
  CONFIG_STORAGE_KEY,
  HISTORY_LIMIT,
  HISTORY_STORAGE_KEY,
  DEFAULT_CONFIG,
  activeProfile,
  type TransferConfig,
} from "../shared/config";
import type { FieldResult, TransferReport } from "../shared/report";
import { buildReport, errorReport } from "../core/report-builder";
import { queryTabsByUrl, sendMessageToTab, storageGet, storageSet } from "../shared/chrome-api";

/** Target tab must answer within this window (Q11). */
const TARGET_TIMEOUT_MS = 5000;

async function loadConfig(): Promise<TransferConfig> {
  const stored = await storageGet(CONFIG_STORAGE_KEY);
  const config = stored[CONFIG_STORAGE_KEY] as TransferConfig | undefined;
  return config ?? DEFAULT_CONFIG;
}

async function handleRequest(request: BackgroundRequest, senderTabId: number): Promise<void> {
  const startedAt = Date.now();
  const transferId = request.transferId;

  if (request.version !== TRANSFER_CONTRACT_VERSION) {
    await finish(senderTabId, errorReport({
      transferId,
      timestamp: new Date().toISOString(),
      durationMs: Date.now() - startedAt,
      detail: "Nieobsługiwana wersja kontraktu Transfer",
    }));
    return;
  }

  const config = await loadConfig();
  const profile = activeProfile(config);
  if (!profile) {
    await finish(senderTabId, errorReport({
      transferId,
      timestamp: new Date().toISOString(),
      durationMs: Date.now() - startedAt,
      detail: "Brak aktywnego profilu Transfer",
    }));
    return;
  }

  const tabs = await queryTabsByUrl(profile.urlPattern);
  if (tabs.length === 0) {
    await finish(senderTabId, errorReport({
      transferId,
      timestamp: new Date().toISOString(),
      durationMs: Date.now() - startedAt,
      detail: "Strona docelowa nie jest otwarta",
    }));
    return;
  }
  if (tabs.length > 1) {
    await finish(senderTabId, errorReport({
      transferId,
      timestamp: new Date().toISOString(),
      durationMs: Date.now() - startedAt,
      detail: "Otwarta jest wiele kart strony docelowej",
    }));
    return;
  }

  const targetTab = tabs[0];
  let report: TransferReport;
  try {
    const response = (await Promise.race([
      sendMessageToTab<{ results: FieldResult[] }>(targetTab.id as number, {
        type: "rx:fill",
        transferId,
        metadata: request.metadata,
        mapping: profile.mapping,
      }),
      timeout(`Strona docelowa nie odpowiada (${TARGET_TIMEOUT_MS / 1000} s)`),
    ])) as { results: FieldResult[] };

    report = buildReport({
      transferId,
      timestamp: new Date().toISOString(),
      durationMs: Date.now() - startedAt,
      targetUrl: targetTab.url,
      results: response.results,
    });
  } catch (error) {
    report = errorReport({
      transferId,
      timestamp: new Date().toISOString(),
      durationMs: Date.now() - startedAt,
      targetUrl: targetTab.url,
      detail:
        error instanceof Error
          ? error.message
          : "Strona docelowa nie odpowiada",
    });
  }

  await finish(senderTabId, report);
}

async function finish(senderTabId: number, report: TransferReport): Promise<void> {
  await appendHistory(report);
  try {
    await sendMessageToTab(senderTabId, { type: "rx:transfer-result", report });
  } catch {
    // requesting tab may have navigated away; the report is already in history
  }
}

async function appendHistory(report: TransferReport): Promise<void> {
  const stored = await storageGet(HISTORY_STORAGE_KEY);
  const history = (stored[HISTORY_STORAGE_KEY] as TransferReport[] | undefined) ?? [];
  history.unshift(report);
  await storageSet({ [HISTORY_STORAGE_KEY]: history.slice(0, HISTORY_LIMIT) });
}

function timeout(message: string): Promise<never> {
  return new Promise((_, reject) => {
    setTimeout(() => reject(new Error(message)), TARGET_TIMEOUT_MS);
  });
}

chrome.runtime.onMessage.addListener((message, sender) => {
  if (message?.type === "rx:transfer-request" && typeof sender.tab?.id === "number") {
    void handleRequest(message as BackgroundRequest, sender.tab.id);
  }
  return false;
});
