import type { MetadataKey } from "./metadata";

/** How to find the control on the Target Page representing one metadata field. */
export type FieldMapping = {
  /** CSS selector candidates, tried in order. */
  selectors: string[];
  /** Visible label text fallback (diacritics/case/space-insensitive). */
  label: string;
};

export type MappingSet = Record<MetadataKey, FieldMapping>;

/** A Transfer Profile: Target Page URL pattern + Field Mappings (see GLOSSARY.md). */
export type TransferProfile = {
  name: string;
  /** Chrome-style match pattern for the Target Page, e.g. "http://localhost:3011/*". */
  urlPattern: string;
  /** Match pattern for pages allowed to *initiate* a Transfer (our app), e.g. "http://localhost:3010/*". */
  appUrlPattern: string;
  mapping: MappingSet;
};

export type TransferConfig = {
  version: 1;
  profiles: TransferProfile[];
  activeProfileName: string;
};

export const CONFIG_STORAGE_KEY = "rx-transfer-config";
export const HISTORY_STORAGE_KEY = "rx-transfer-history";
export const HISTORY_LIMIT = 20;

function mapping(label: string, ...selectors: string[]): FieldMapping {
  return { selectors, label };
}

/** Built-in Mock profile matching extension/mock pages; the dev->prod cutover edits this. */
export const DEFAULT_CONFIG: TransferConfig = {
  version: 1,
  activeProfileName: "Mock",
  profiles: [
    {
      name: "Mock",
      urlPattern: "http://localhost:3011/*",
      appUrlPattern: "http://localhost:3010/*",
      mapping: {
        organ: mapping("Badany narząd", "#field-organ"),
        name: mapping("Imię i nazwisko", "#field-name"),
        age: mapping("Wiek", "#field-age"),
        pesel: mapping("PESEL", "#field-pesel"),
        description: mapping("Opis badania", "#field-description"),
      },
    },
  ],
};

export function activeProfile(config: TransferConfig): TransferProfile | undefined {
  return config.profiles.find((profile) => profile.name === config.activeProfileName);
}

/**
 * Anchored wildcard match against a Chrome-style pattern: `*` matches any run
 * of characters; everything else is literal. Used to gate both the requesting
 * app page and the target tab, so the runtime config is the real gate
 * (docs/adr/0001).
 */
export function matchesUrlPattern(pattern: string, url: string): boolean {
  const body = pattern.split("*").map(escapeRegExp).join(".*");
  return new RegExp(`^${body}$`).test(url);
}

function escapeRegExp(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
