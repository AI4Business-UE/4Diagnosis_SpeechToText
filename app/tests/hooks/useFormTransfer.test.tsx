import { renderHook, act, screen, waitFor, cleanup } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/contexts/ToastContext";
import ToastContainer from "@/components/ui/ToastContainer";
import { useFormTransfer } from "@/hooks/useFormTransfer";
import type { PatientMetadata } from "@/types/metadata";
import {
  TRANSFER_CHANNEL,
  TRANSFER_CONTRACT_VERSION,
  type TransferReport,
} from "@/types/transfer";

const metadata: PatientMetadata = {
  organ: "Skóra",
  name: "Jan Kowalski",
  age: "27",
  pesel: "99123456789",
  description: "Rozpoznienie na skórze przedramienia.",
};

function wrapper({ children }: { children: React.ReactNode }) {
  return (
    <ToastProvider>
      {children}
      <ToastContainer />
    </ToastProvider>
  );
}

function filledReport(transferId: string): TransferReport {
  return {
    transferId,
    timestamp: new Date().toISOString(),
    overall: "ok",
    durationMs: 42,
    fields: (["organ", "name", "age", "pesel", "description"] as const).map((field) => ({
      field,
      status: "filled" as const,
      strategy: "selector" as const,
    })),
  };
}

function postResultMessage(report: TransferReport) {
  window.dispatchEvent(
    new MessageEvent("message", {
      source: window,
      data: {
        channel: TRANSFER_CHANNEL,
        version: TRANSFER_CONTRACT_VERSION,
        type: "transfer-result",
        transferId: report.transferId,
        report,
      },
    }),
  );
}

describe("useFormTransfer", () => {
  beforeEach(() => {
    vi.spyOn(window, "postMessage");
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it("broadcasts a versioned transfer-request with the Patient Metadata", async () => {
    const { result } = renderHook(() => useFormTransfer(), { wrapper });

    await act(async () => {
      const transfer = result.current.transfer(metadata);
      postResultMessage(filledReport(await lastTransferId()));
      await transfer;
    });

    const [payload, origin] = (window.postMessage as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(origin).toBe(window.location.origin);
    expect(payload).toEqual({
      channel: TRANSFER_CHANNEL,
      version: TRANSFER_CONTRACT_VERSION,
      type: "transfer-request",
      transferId: expect.any(String),
      metadata,
    });
  });

  it("keeps the button pending until the transfer-result arrives", async () => {
    const { result } = renderHook(() => useFormTransfer(), { wrapper });

    act(() => {
      void result.current.transfer(metadata);
    });
    expect(result.current.pending).toBe(true);

    const transferId = await lastTransferId();
    act(() => postResultMessage(filledReport(transferId)));

    await waitFor(() => expect(result.current.pending).toBe(false));
  });

  it("shows a success toast when every field was filled", async () => {
    const { result } = renderHook(() => useFormTransfer(), { wrapper });

    act(() => {
      void result.current.transfer(metadata);
    });
    const transferId = await lastTransferId();
    act(() => postResultMessage(filledReport(transferId)));

    expect(await screen.findByText(/Przeniesiono dane do formularza \(5\/5\)/)).toBeTruthy();
  });

  it("lists unfilled fields in a partial-success toast", async () => {
    const { result } = renderHook(() => useFormTransfer(), { wrapper });

    act(() => {
      void result.current.transfer(metadata);
    });
    const transferId = await lastTransferId();
    const report = filledReport(transferId);
    report.overall = "partial";
    report.fields = report.fields.map((f) =>
      f.field === "age" || f.field === "pesel" ? { ...f, status: "not_found" as const } : f,
    );
    act(() => postResultMessage(report));

    expect(await screen.findByText(/Przeniesiono 3\/5 pól/)).toBeTruthy();
    expect(screen.getByText(/Wiek/)).toBeTruthy();
    expect(screen.getByText(/PESEL/)).toBeTruthy();
  });

  it("surfaces a routing failure detail in an error toast", async () => {
    const { result } = renderHook(() => useFormTransfer(), { wrapper });

    act(() => {
      void result.current.transfer(metadata);
    });
    const transferId = await lastTransferId();
    act(() =>
      postResultMessage({
        transferId,
        timestamp: new Date().toISOString(),
        overall: "error",
        durationMs: 1,
        fields: [],
        detail: "Strona docelowa nie jest otwarta",
      }),
    );

    expect(await screen.findByText(/Strona docelowa nie jest otwarta/)).toBeTruthy();
  });

  it("includes the per-field failure reason in the partial toast", async () => {
    const { result } = renderHook(() => useFormTransfer(), { wrapper });

    act(() => {
      void result.current.transfer(metadata);
    });
    const transferId = await lastTransferId();
    const report = filledReport(transferId);
    report.overall = "partial";
    report.fields = report.fields.map((f) =>
      f.field === "organ"
        ? { field: f.field, status: "failed" as const, detail: "Brak pasującej opcji na stronie docelowej" }
        : f,
    );
    act(() => postResultMessage(report));

    expect(await screen.findByText(/Brak pasującej opcji na stronie docelowej/)).toBeTruthy();
  });

  it("rejects a transfer-result from an incompatible contract version", async () => {
    const { result } = renderHook(() => useFormTransfer(), { wrapper });

    act(() => {
      void result.current.transfer(metadata);
    });
    const transferId = await lastTransferId();
    window.dispatchEvent(
      new MessageEvent("message", {
        source: window,
        data: {
          channel: TRANSFER_CHANNEL,
          version: 99,
          type: "transfer-result",
          transferId,
          report: filledReport(transferId),
        },
      }),
    );

    expect(await screen.findByText(/Nieobsługiwana wersja kontraktu/)).toBeTruthy();
    expect(result.current.pending).toBe(false);
  });

  it("errors out when the extension never answers (extension not installed)", async () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useFormTransfer(), { wrapper });

    act(() => {
      void result.current.transfer(metadata);
    });
    await act(async () => {
      vi.advanceTimersByTime(10_000);
    });
    vi.useRealTimers();

    expect(await screen.findByText(/Brak odpowiedzi rozszerzenia/)).toBeTruthy();
    expect(result.current.pending).toBe(false);
  });

  it("ignores results addressed to another transfer", async () => {
    const { result } = renderHook(() => useFormTransfer(), { wrapper });

    act(() => {
      void result.current.transfer(metadata);
    });
    act(() => postResultMessage(filledReport("obcy-transfer-id")));

    expect(screen.queryByText(/Przeniesiono/)).toBeNull();
    expect(result.current.pending).toBe(true);
  });
});

async function lastTransferId(): Promise<string> {
  const calls = (window.postMessage as ReturnType<typeof vi.fn>).mock.calls;
  const last = calls[calls.length - 1]?.[0] as { transferId?: string };
  return last.transferId as string;
}
