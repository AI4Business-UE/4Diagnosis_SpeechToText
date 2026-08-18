import { AudioStreamProcessor, checkWAVSupport } from "@/lib/audio/AudioStreamProcessor";
import { AudioConfig } from "../types/config";

export const createAudioUtilities = (config: AudioConfig) => {
  const getUserMedia = async (): Promise<MediaStream | null> => {
    try {
      return await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: { ideal: config.sampleRate },
          channelCount: { exact: config.channelCount },
          echoCancellation: { ideal: config.echoCancellation },
          noiseSuppression: { ideal: config.noiseSuppression },
        },
      });
    } catch (e) {
      console.log(e);
      return null;
    }
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