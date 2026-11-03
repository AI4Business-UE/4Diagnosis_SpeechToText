import { describe, expect, it } from "vitest";

import { buildReport, errorReport } from "../src/core/report-builder";
import type { FieldResult } from "../src/shared/report";

const results: FieldResult[] = [
  { field: "organ", status: "filled", strategy: "selector" },
  { field: "name", status: "filled", strategy: "label" },
  { field: "age", status: "not_found" },
  { field: "pesel", status: "failed", detail: "Brak opcji" },
  { field: "description", status: "filled", strategy: "selector" },
];

describe("buildReport", () => {
  it("marks a Transfer partial when some fields were not filled", () => {
    const report = buildReport({
      transferId: "t-1",
      timestamp: "2026-11-03T10:00:00.000Z",
      durationMs: 12,
      targetUrl: "http://localhost:3011/",
      results,
    });

    expect(report.transferId).toBe("t-1");
    expect(report.durationMs).toBe(12);
    expect(report.overall).toBe("partial");
    expect(report.fields).toEqual(results);
  });

  it("reports ok for all-filled and error for none-filled", () => {
    const all = results.map((r) => ({ ...r, status: "filled" as const }));
    const none = results.map((r) => ({ ...r, status: "not_found" as const }));

    expect(
      buildReport({ transferId: "t-2", timestamp: "x", durationMs: 1, results: all }).overall,
    ).toBe("ok");
    expect(
      buildReport({ transferId: "t-3", timestamp: "x", durationMs: 1, results: none }).overall,
    ).toBe("error");
  });

  it("strips any transferred values from the report", () => {
    const leaked = results.map((r) => ({ ...r, value: "PESEL 99123456789" }));
    const report = buildReport({
      transferId: "t-4",
      timestamp: "x",
      durationMs: 1,
      results: leaked,
    });

    const serialized = JSON.stringify(report);
    expect(serialized).not.toContain("99123456789");
    expect(serialized).not.toContain("PESEL 99123456789");
    expect(Object.keys(report)).toEqual(
      expect.arrayContaining(["transferId", "timestamp", "overall", "durationMs", "fields"]),
    );
  });
});

describe("errorReport", () => {
  it("builds an overall-error report with a detail and no field results", () => {
    const report = errorReport({
      transferId: "t-5",
      timestamp: "x",
      durationMs: 5000,
      detail: "Strona docelowa nie odpowiada",
    });

    expect(report.overall).toBe("error");
    expect(report.detail).toBe("Strona docelowa nie odpowiada");
    expect(report.fields).toEqual([]);
  });
});
