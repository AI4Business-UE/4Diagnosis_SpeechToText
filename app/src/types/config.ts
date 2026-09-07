export type AudioConfig = {
  sampleRate: number;
  channelCount: number;
  echoCancellation: boolean;
  noiseSuppression: boolean;
  audioBitsPerSecond: number;
  chunkInterval: number;
};