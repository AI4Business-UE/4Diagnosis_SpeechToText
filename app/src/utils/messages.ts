import { WebSocketOutgoingMessage } from "../types/websocket";
import { PatientMetadata } from "../types/metadata";

export const createMessage = (
  type: WebSocketOutgoingMessage["type"],
  data?: any,
  metadata?: PatientMetadata
): WebSocketOutgoingMessage => {
  const message: WebSocketOutgoingMessage = { type };
  
  if (data) {
    message.data = data;
  }
  
  if (metadata) {
    message.metadata = metadata;
  }
  
  return message;
};

export const createMetadataMessage = (
  metadata: PatientMetadata
): WebSocketOutgoingMessage => createMessage("metadata", metadata);

export const createAudioChunkMessage = (
  audioData: string,
  metadata: PatientMetadata
): WebSocketOutgoingMessage => createMessage("audio_chunk", audioData, metadata);

export const createRecordingStartMessage = (
  metadata: PatientMetadata
): WebSocketOutgoingMessage => createMessage("recording_start", undefined, metadata);

export const createRecordingEndMessage = (
  metadata: PatientMetadata
): WebSocketOutgoingMessage => createMessage("recording_end", undefined, metadata);

export const createMetadataUpdateMessage = (
  metadata: PatientMetadata
): WebSocketOutgoingMessage => createMessage("metadata_update", null, metadata);