import { AudioConfig } from "./types";
import { AudioStreamProcessor, checkWAVSupport } from "@/lib/audio/AudioStreamProcessor";

export const createAudioUtilities = (config: AudioConfig) => {
  const getUserMedia = async (): Promise<MediaStream> => {
    return navigator.mediaDevices.getUserMedia({
      audio: {
        sampleRate: config.sampleRate,
        channelCount: config.channelCount,
        echoCancellation: config.echoCancellation,
        noiseSuppression: config.noiseSuppression,
      },
    });
  };

  const createAudioStreamProcessor = (
    stream: MediaStream,
    onDataAvailable: (b64data: string) => void
  ): AudioStreamProcessor => {
    if (!checkWAVSupport()) {
      throw new Error("WAV streaming is not supported in this browser");
    }

    const processor = new AudioStreamProcessor(onDataAvailable);
    return processor;
  };

  const stopStream = (stream: MediaStream | null): void => {
    if (stream) {
      stream.getTracks().forEach((track) => track.stop());
    }
  };

  return { getUserMedia, createAudioStreamProcessor, stopStream };
};
