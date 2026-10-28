import type { AudioConfig } from "./types/config";

const BACKEND_HOST_STRUCTURE = "localhost:8000";

export const WEBSOCKET_URL = `ws://${BACKEND_HOST_STRUCTURE}/ws/audio/`;
export const API_URL = `http://${BACKEND_HOST_STRUCTURE}/api`;

export const AUDIO_WORKLET_URL = "/audio-worklets/BaseProcessor.js";

export const AUDIO_CONFIG: AudioConfig = {
  sampleRate: 16000,
  channelCount: 1,
  echoCancellation: true,
  noiseSuppression: true,
  audioBitsPerSecond: 16000,
  chunkInterval: 250,
};
