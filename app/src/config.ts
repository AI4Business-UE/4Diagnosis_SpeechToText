import type { AudioConfig } from "./types/config";

export const WEBSOCKET_URL = "ws://localhost:8000/ws/audio/";

export const AUDIO_WORKLET_URL = "/audio-worklets/BaseProcessor.js";

export const AUDIO_CONFIG: AudioConfig = {
  sampleRate: 16000,
  channelCount: 1,
  echoCancellation: true,
  noiseSuppression: true,
  audioBitsPerSecond: 16000,
  chunkInterval: 250,
};
