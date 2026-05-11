import { PatientMetadata, WebSocketMessage } from "./types";

// ==================== PURE FUNCTIONS ====================

// Time formatting utilities
export const formatTime = (seconds: number): string => {
  const m = Math.floor(seconds / 60)
    .toString()
    .padStart(2, "0");
  const s = (seconds % 60).toString().padStart(2, "0");
  return `${m}:${s}`;
};

export const parseTime = (timeString: string): number => {
  const [minutes, seconds] = timeString.split(":").map(Number);
  return minutes * 60 + seconds;
};

// Metadata utilities
export const createEmptyMetadata = (): PatientMetadata => ({
  organ: "",
  name: "",
  age: "",
  pesel: "",
  description: "",
});

export const updateMetadataField = (
  metadata: PatientMetadata,
  field: keyof PatientMetadata,
  value: string
): PatientMetadata => ({
  ...metadata,
  [field]: value,
});

export const clearDescription = (metadata: PatientMetadata): PatientMetadata =>
  updateMetadataField(metadata, "description", "");

// Message creators
export const createMessage = (
  type: WebSocketMessage["type"],
  data?: any,
  metadata?: PatientMetadata
): WebSocketMessage => {
  const message: WebSocketMessage = { type };
  
  if (type === "audio_chunk" && typeof data === "string") {
    message.data = data;
  } else if (data) {
    message.data = data;
  }
  
  if (metadata) {
    message.metadata = metadata;
  }
  
  return message;
};

export const createMetadataMessage = (
  metadata: PatientMetadata
): WebSocketMessage => createMessage("metadata", metadata);

export const createAudioChunkMessage = (
  audioData: string,
  metadata: PatientMetadata
): WebSocketMessage => createMessage("audio_chunk", audioData, metadata);

export const createRecordingStartMessage = (
  metadata: PatientMetadata
): WebSocketMessage => createMessage("recording_start", undefined, metadata);

export const createRecordingEndMessage = (
  metadata: PatientMetadata
): WebSocketMessage => createMessage("recording_end", undefined, metadata);

export const createMetadataUpdateMessage = (
  metadata: PatientMetadata
): WebSocketMessage => createMessage("metadata_update", metadata);
