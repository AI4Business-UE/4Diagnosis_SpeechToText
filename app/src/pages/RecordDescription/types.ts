export interface PatientMetadata {
  organ: string;
  name: string;
  age: string;
  pesel: string;
  description: string;
}

export interface WebSocketMessage {
  type:
    | "metadata"
    | "audio_chunk"
    | "recording_start"
    | "recording_end"
    | "metadata_update"
    | "transcription";
  data?: any;
  text?: string;
  metadata?: PatientMetadata;
  control?: string;
}

export interface AudioConfig {
  sampleRate: number;
  channelCount: number;
  echoCancellation: boolean;
  noiseSuppression: boolean;
  audioBitsPerSecond: number;
  chunkInterval: number;
}

export interface RecordingState {
  isRecording: boolean;
  time: string;
  intervalId: NodeJS.Timeout | null;
}

export interface ConnectionState {
  isConnected: boolean;
  ws: WebSocket | null;
}
