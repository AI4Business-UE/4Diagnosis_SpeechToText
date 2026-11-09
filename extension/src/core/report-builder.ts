import type { FieldResult, TransferReport } from "../shared/report";

type ReportInput = {
  transferId: string;
  timestamp: string;
  durationMs: number;
  targetUrl?: string;
  results: FieldResult[];
};

/**
 * Assembles a Transfer Report from per-field results. Overall semantics:
 * ok = every field filled, partial = some filled, error = none filled.
 * Field results are normalized to the report vocabulary so transferred
 * values can never leak into a report or its history.
 */
export function buildReport(input: ReportInput): TransferReport {
  const fields = input.results.map(normalizeFieldResult);
  const filled = fields.filter((field) => field.status === "filled").length;
  const overall = filled === 0 ? "error" : filled === fields.length ? "ok" : "partial";

  const report: TransferReport = {
    transferId: input.transferId,
    timestamp: input.timestamp,
    overall,
    durationMs: input.durationMs,
    fields,
  };
  if (input.targetUrl !== undefined) report.targetUrl = input.targetUrl;
  return report;
}

export function errorReport(input: {
  transferId: string;
  timestamp: string;
  durationMs: number;
  detail: string;
  targetUrl?: string;
}): TransferReport {
  const report: TransferReport = {
    transferId: input.transferId,
    timestamp: input.timestamp,
    overall: "error",
    durationMs: input.durationMs,
    fields: [],
    detail: input.detail,
  };
  if (input.targetUrl !== undefined) report.targetUrl = input.targetUrl;
  return report;
}

function normalizeFieldResult(result: FieldResult): FieldResult {
  const normalized: FieldResult = { field: result.field, status: result.status };
  if (result.strategy !== undefined) normalized.strategy = result.strategy;
  if (result.detail !== undefined) normalized.detail = result.detail;
  return normalized;
}
