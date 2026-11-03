import {
  CONFIG_STORAGE_KEY,
  DEFAULT_CONFIG,
  HISTORY_STORAGE_KEY,
  activeProfile,
  type TransferConfig,
  type TransferProfile,
} from "../shared/config";
import { storageGet, storageSet } from "../shared/chrome-api";
import { METADATA_KEYS, type MetadataKey } from "../shared/metadata";
import type { TransferReport } from "../shared/report";

// Mirrors FIELD_LABELS in app/src/hooks/useFormTransfer.ts (separate bundles by design, ADR-0002).
const FIELD_LABELS: Record<MetadataKey, string> = {
  organ: "Badany narząd",
  name: "Imię i nazwisko",
  age: "Wiek",
  pesel: "PESEL",
  description: "Opis badania",
};

let config: TransferConfig = structuredClone(DEFAULT_CONFIG);

function $<T extends HTMLElement = HTMLElement>(id: string): T {
  return document.getElementById(id) as T;
}

async function load(): Promise<void> {
  const stored = await storageGet([CONFIG_STORAGE_KEY, HISTORY_STORAGE_KEY]);
  if (stored[CONFIG_STORAGE_KEY]) {
    config = stored[CONFIG_STORAGE_KEY] as TransferConfig;
  }
  renderProfiles();
  renderFieldEditors();
  renderHistory((stored[HISTORY_STORAGE_KEY] as TransferReport[] | undefined) ?? []);
}

function currentProfile(): TransferProfile {
  return activeProfile(config) ?? config.profiles[0];
}

function renderProfiles(): void {
  const select = $<HTMLSelectElement>("active-profile-select");
  select.innerHTML = "";
  for (const profile of config.profiles) {
    const option = document.createElement("option");
    option.value = profile.name;
    option.textContent = profile.name;
    select.append(option);
  }
  select.value = config.activeProfileName;
  $<HTMLInputElement>("profile-name").value = currentProfile().name;
  $<HTMLInputElement>("profile-url").value = currentProfile().urlPattern;
  $<HTMLInputElement>("profile-app-url").value = currentProfile().appUrlPattern;
}

function renderFieldEditors(): void {
  const container = $<HTMLDivElement>("field-editors");
  container.innerHTML = "";
  const profile = currentProfile();

  for (const field of METADATA_KEYS) {
    const mapping = profile.mapping[field];
    const group = document.createElement("fieldset");
    const legend = document.createElement("legend");
    legend.append(`${FIELD_LABELS[field]} `);
    const legendHint = document.createElement("span");
    legendHint.className = "hint";
    legendHint.textContent = `(${field})`;
    legend.append(legendHint);
    group.append(legend);

    const selectorsLabel = document.createElement("label");
    selectorsLabel.textContent = "Kandydaci selektorów CSS (po jednym na linię)";
    const selectors = document.createElement("textarea");
    selectors.id = `selectors-${field}`;
    selectors.rows = 2;
    selectors.value = mapping.selectors.join("\n");

    const labelLabel = document.createElement("label");
    labelLabel.textContent = "Etykieta pola na stronie docelowej (fallback)";
    const labelText = document.createElement("input");
    labelText.type = "text";
    labelText.id = `label-${field}`;
    labelText.value = mapping.label;

    group.append(selectorsLabel, selectors, labelLabel, labelText);
    container.append(group);
  }
}

function syncProfileFromForm(): TransferConfig {
  const profile = currentProfile();
  profile.name = $<HTMLInputElement>("profile-name").value.trim() || profile.name;
  profile.urlPattern = $<HTMLInputElement>("profile-url").value.trim();
  profile.appUrlPattern = $<HTMLInputElement>("profile-app-url").value.trim();

  for (const field of METADATA_KEYS) {
    profile.mapping[field] = {
      selectors: $<HTMLTextAreaElement>(`selectors-${field}`)
        .value.split("\n")
        .map((line) => line.trim())
        .filter(Boolean),
      label: $<HTMLInputElement>(`label-${field}`).value.trim(),
    };
  }
  config.activeProfileName = profile.name;
  return config;
}

const OVERALL_LABELS: Record<TransferReport["overall"], string> = {
  ok: "Sukces",
  partial: "Częściowo",
  error: "Błąd",
};

function renderHistory(history: TransferReport[]): void {
  const rows = $<HTMLTableElement>("history-rows");
  rows.innerHTML = "";
  for (const report of history) {
    const missing = report.fields
      .filter((field) => field.status !== "filled")
      .map((field) => FIELD_LABELS[field.field])
      .join(", ");

    const row = rows.insertRow();
    cell(row, new Date(report.timestamp).toLocaleString("pl-PL"));
    // targetUrl is page-controlled; insert as text, never as HTML.
    cell(row, report.targetUrl ?? "-");
    const status = cell(row, OVERALL_LABELS[report.overall]);
    status.className = `status ${report.overall}`;
    cell(row, report.detail ?? (missing ? `brak: ${missing}` : "wszystkie pola wypełnione"));
  }
}

function cell(row: HTMLTableRowElement, text: string): HTMLTableCellElement {
  const td = row.insertCell();
  td.textContent = text;
  return td;
}

async function save(): Promise<void> {
  await storageSet({ [CONFIG_STORAGE_KEY]: syncProfileFromForm() });
  const status = $<HTMLSpanElement>("save-status");
  status.textContent = "Zapisano";
  status.className = "status ok";
  setTimeout(() => (status.textContent = ""), 2500);
  renderProfiles();
}

function showStatus(text: string, ok: boolean): void {
  const status = $<HTMLSpanElement>("save-status");
  status.textContent = text;
  status.className = `status ${ok ? "ok" : "error"}`;
}

$<HTMLButtonElement>("active-profile-select").addEventListener("change", (event) => {
  config.activeProfileName = (event.target as HTMLSelectElement).value;
  renderProfiles();
  renderFieldEditors();
});

$<HTMLButtonElement>("add-profile").addEventListener("click", () => {
  const name = `Profil ${config.profiles.length + 1}`;
  config.profiles.push({
    name,
    urlPattern: "https://example.com/*",
    appUrlPattern: currentProfile().appUrlPattern,
    mapping: structuredClone(DEFAULT_CONFIG.profiles[0].mapping),
  });
  config.activeProfileName = name;
  renderProfiles();
  renderFieldEditors();
});

$<HTMLButtonElement>("delete-profile").addEventListener("click", () => {
  if (config.profiles.length <= 1) {
    showStatus("Nie można usunąć ostatniego profilu", false);
    return;
  }
  config.profiles = config.profiles.filter((p) => p.name !== config.activeProfileName);
  config.activeProfileName = config.profiles[0].name;
  renderProfiles();
  renderFieldEditors();
});

$<HTMLButtonElement>("save-config").addEventListener("click", () => void save());

$<HTMLButtonElement>("export-json").addEventListener("click", () => {
  $<HTMLTextAreaElement>("raw-json").value = JSON.stringify(syncProfileFromForm(), null, 2);
});

$<HTMLButtonElement>("import-json").addEventListener("click", () => {
  try {
    const parsed = JSON.parse($<HTMLTextAreaElement>("raw-json").value) as TransferConfig;
    if (!Array.isArray(parsed.profiles) || parsed.profiles.length === 0) {
      throw new Error("Brak profilów");
    }
    config = parsed;
    if (!activeProfile(config)) config.activeProfileName = config.profiles[0].name;
    renderProfiles();
    renderFieldEditors();
    void save();
  } catch {
    showStatus("Nieprawidłowy JSON konfiguracji", false);
  }
});

$<HTMLButtonElement>("clear-history").addEventListener("click", async () => {
  await storageSet({ [HISTORY_STORAGE_KEY]: [] });
  renderHistory([]);
});

void load();
