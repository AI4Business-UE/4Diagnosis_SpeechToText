/**
 * The five canonical Patient Metadata keys transferred to the Target Page.
 * Mirrors PatientMetadata in app/src/types/metadata.ts.
 */
export type MetadataKey = "organ" | "name" | "age" | "pesel" | "description";

export const METADATA_KEYS: readonly MetadataKey[] = [
  "organ",
  "name",
  "age",
  "pesel",
  "description",
];

export type PatientMetadata = Record<MetadataKey, string>;
