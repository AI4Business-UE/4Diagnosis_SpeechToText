// Utility functions for audio processing and WAV conversion

import { AUDIO_CONFIG, AUDIO_WORKLET_URL } from "@/config";
import { WavEncoder } from "./WavEncoder";

export class AudioStreamProcessor {
  private audioContext: AudioContext | null = null;
  private wavEncoder: WavEncoder;
  private onReadyAudioData: (b64data: string) => void;

  constructor(
    onReadyAudioData: (b64data: string) => void,
  ) {
    this.wavEncoder = new WavEncoder(
      AUDIO_CONFIG.sampleRate,
      AUDIO_CONFIG.channelCount,
    );
    this.onReadyAudioData = onReadyAudioData;
  }

  async startProcessing(stream: MediaStream): Promise<void> {
    try {
      // Sprawdź czy browser obsługuje wymaganą częstotliwość próbkowania
      const constraints = stream.getTracks()[0].getSettings();
      console.log('Aktualne ustawienia audio:', constraints);

      this.audioContext = new AudioContext();
      const source = this.audioContext.createMediaStreamSource(stream);

      console.log('AudioContext sample rate:', this.audioContext.sampleRate);
      
      await this.audioContext.audioWorklet.addModule(AUDIO_WORKLET_URL);
      const worklet = new AudioWorkletNode(this.audioContext, 'base-processor', {
        numberOfInputs: 1,
        numberOfOutputs: 1,
        outputChannelCount: [1],
        processorOptions: {
          outputSampleRate: AUDIO_CONFIG.sampleRate
        }
      });

      worklet.port.onmessage = event => {
        const resampledAudio = event.data as Float32Array;
        if (!(resampledAudio instanceof Float32Array)) {
          throw new Error("Resampler returned an invalid audio buffer!");
        }

        const base64Data = this.wavEncoder.float32ArrayToBase64(resampledAudio);
        this.onReadyAudioData(base64Data);
      };

      const muteNode = this.audioContext.createGain();
      muteNode.gain.value = 0;

      source.connect(worklet);
      worklet.connect(muteNode);
      muteNode.connect(this.audioContext.destination);

      console.log('✅ WAV Audio streaming rozpoczęty - częstotliwość:', this.audioContext.sampleRate, 'Hz');
    } catch (error) {
      console.error('Error starting audio processing:', error);
      throw error;
    }
  }

  async stopProcessing() {
    // This instantly closes audio input so no processing should occur during cleanup.
    // Dereferencing happens after awaiting close status so GB should not interupt anything.
    if (this.audioContext) {
      await this.audioContext.close();
      this.audioContext = null;
    }
    
    console.log('🛑 WAV Audio streaming zakończony');
  }
}

// Helper function to check WAV support
export const checkWAVSupport = (): boolean => {
  try {
    return typeof AudioContext !== 'undefined' || typeof (window as any).webkitAudioContext !== 'undefined';
  } catch {
    return false;
  }
};

// Create stop recording control message
export const createStopRecordingMessage = () => ({
  control: "stop_recording"
});

// Create recording end message
export const createRecordingEndMessage = (metadata = {}) => ({
  type: "recording_end",
  metadata
});
