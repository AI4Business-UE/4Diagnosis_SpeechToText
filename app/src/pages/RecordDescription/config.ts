import { AudioConfig } from "./types";

export const WEBSOCKET_URL = "ws://localhost:8010/ws/audio/";

export const AUDIO_CONFIG: AudioConfig = {
  sampleRate: 16000,
  channelCount: 1,
  echoCancellation: true,
  noiseSuppression: true,
  audioBitsPerSecond: 16000,
  chunkInterval: 250,
};
