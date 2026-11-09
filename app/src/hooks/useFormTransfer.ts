import { useCallback, useEffect, useRef, useState } from "react";

import { useToast } from "./useToast";
import type { ToastMessage } from "@/contexts/ToastContext";
import type { PatientMetadata } from "@/types/metadata";
import {
  TRANSFER_CHANNEL,
  TRANSFER_CONTRACT_VERSION,
  type TransferReport,
} from "@/types/transfer";

/** Extension answers within ~5 s; the watchdog covers an uninstalled/dead extension. */
const TRANSFER_WATCHDOG_MS = 6000;

// Mirrors FIELD_LABELS in extension/src/options/index.ts (separate bundles by design, ADR-0002).
const FIELD_LABELS: Record<keyof PatientMetadata, string> = {
  organ: "Badany narząd",
  name: "Imię i nazwisko",
  age: "Wiek",
  pesel: "PESEL",
  description: "Opis badania",
};

function formatTransferToast(report: TransferReport): ToastMessage {
  const unfilled = report.fields.filter((field) => field.status !== "filled");
  const unfilledLabels = unfilled
    .map((field) => (field.detail ? `${FIELD_LABELS[field.field]} (${field.detail})` : FIELD_LABELS[field.field]))
    .join(", ");
  const total = report.fields.length;
  const filled = total - unfilled.length;

  if (report.overall === "ok") {
    return {
      type: "success",
      message: `Przeniesiono dane do formularza (${filled}/${total})`,
    };
  }
  if (report.overall === "partial") {
    return {
      type: "warning",
      message: `Przeniesiono ${filled}/${total} pól — nie uzupełniono: ${unfilledLabels}`,
    };
  }
  if (report.fields.length > 0) {
    return {
      type: "error",
      message: `Nie przeniesiono żadnego pola — nie uzupełniono: ${unfilledLabels}`,
    };
  }
  return {
    type: "error",
    message: `Przeniesienie nie powiodło się: ${report.detail ?? "nieznany błąd"}`,
  };
}

/**
 * Drives the Transfer flow over the versioned window.postMessage contract:
 * broadcasts a transfer-request with the current Patient Metadata and waits
 * for the matching, source-checked transfer-result from the extension.
 * Exactly one Transfer can be in flight per hook instance (`pending`).
 */
export function useFormTransfer() {
  const { addMessage } = useToast();
  const [pending, setPending] = useState(false);
  const inFlight = useRef<{ transferId: string; watchdog: number } | null>(null);

  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      if (event.source !== window) return;

      const data = event.data as {
        channel?: unknown;
        type?: unknown;
        version?: unknown;
        transferId?: unknown;
        report?: TransferReport;
      };
      if (data?.channel !== TRANSFER_CHANNEL || data?.type !== "transfer-result") return;
      if (inFlight.current?.transferId !== data.transferId) return;

      window.clearTimeout(inFlight.current.watchdog);
      inFlight.current = null;
      setPending(false);

      // ADR-0002: an unknown contract version is reported, never guessed at.
      if (data.version !== TRANSFER_CONTRACT_VERSION) {
        addMessage({
          type: "error",
          message: "Nieobsługiwana wersja kontraktu Transfer. Zaktualizuj aplikację lub rozszerzenie.",
        });
        return;
      }
      if (data.report) {
        addMessage(formatTransferToast(data.report));
      }
    };

    window.addEventListener("message", handleMessage);
    return () => window.removeEventListener("message", handleMessage);
  }, [addMessage]);

  useEffect(() => {
    return () => {
      if (inFlight.current) {
        window.clearTimeout(inFlight.current.watchdog);
        inFlight.current = null;
      }
    };
  }, []);

  const transfer = useCallback(
    (metadata: PatientMetadata): Promise<void> => {
      if (inFlight.current) {
        return Promise.reject(new Error("Transfer już jest w trakcie"));
      }

      const transferId = window.crypto.randomUUID();
      window.postMessage(
        {
          channel: TRANSFER_CHANNEL,
          version: TRANSFER_CONTRACT_VERSION,
          type: "transfer-request",
          transferId,
          metadata,
        },
        window.location.origin,
      );
      setPending(true);

      const watchdog = window.setTimeout(() => {
        inFlight.current = null;
        setPending(false);
        addMessage({
          type: "error",
          message:
            "Brak odpowiedzi rozszerzenia. Sprawdź, czy rozszerzenie jest zainstalowane i wybrano aktywny profil Transfer.",
        });
      }, TRANSFER_WATCHDOG_MS);
      inFlight.current = { transferId, watchdog };

      return Promise.resolve();
    },
    [addMessage],
  );

  return { pending, transfer };
}
