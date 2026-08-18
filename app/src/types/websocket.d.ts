import { PatientMetadata } from "./metadata";

export type ConnectionState = {
  isConnected: boolean;
  ws: WebSocket | null;
};

export type WebSocketOutgoingMessage = {
  type:
    | "metadata"
    | "audio_chunk"
    | "recording_start"
    | "recording_end"
    | "metadata_update"
    | "transcription"
    | "stop_recording"
    | "error";
  data?: any;
  text?: string;
  metadata?: PatientMetadata;
  control?: string;
}; 

export type WebSocketFormData = {
  organ?: string;
  name?: string;
  age?: string;
  pesel?: string;
  description?: string;
}

export type WebSocketIncomingMessage = {
  type: 'recording_start' | 'form_data' | 'error';
  text?: string;
  ack?: boolean;
  transcription?: string;
  formData?: WebSocketFormData
};
