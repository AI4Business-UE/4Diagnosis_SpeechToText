// Utility functions for audio processing and WAV conversion

import { WavEncoder } from "./WavEncoder";

export class AudioStreamProcessor {
  private audioContext: AudioContext | null = null;
  private wavEncoder: WavEncoder;
  private onRawAudioData: (b64data: string) => void;

  constructor(
    onRawAudioData: (b64data: string) => void,
  ) {
    this.wavEncoder = new WavEncoder();
    this.onRawAudioData = onRawAudioData;
  }

  async startProcessing(stream: MediaStream): Promise<void> {
    try {
      // Sprawdź czy browser obsługuje wymaganą częstotliwość próbkowania
      const constraints = stream.getTracks()[0].getSettings();
      console.log('Aktualne ustawienia audio:', constraints);

      this.audioContext = new AudioContext({
        sampleRate: constraints.sampleRate
      });
      const source = this.audioContext.createMediaStreamSource(stream);

      console.log('AudioContext sample rate:', this.audioContext.sampleRate);
      const muteNode = this.audioContext.createGain();
      muteNode.gain.value = 0;
      
      await this.audioContext.audioWorklet.addModule('/public/audio_processors/BaseProcessor.js');
      const worklet = new AudioWorkletNode(this.audioContext, 'base-processor');

      worklet.port.onmessage = event => {
        const float32AudioData = event.data as Float32Array[];
        // Combine all buffers in queue
        const totalLength = float32AudioData.reduce((sum, buffer) => sum + buffer.length, 0);
        const combinedBuffer = new Float32Array(totalLength);
      
        let offset = 0;
        for (const buffer of float32AudioData) {
          combinedBuffer.set(buffer, offset);
          offset += buffer.length;
        }
       
        const base64Data = this.wavEncoder.float32ArrayToBase64(combinedBuffer);
        this.onRawAudioData(base64Data);
      };

      source.connect(worklet);
      console.log('✅ WAV Audio streaming rozpoczęty - częstotliwość:', this.audioContext.sampleRate, 'Hz');
    } catch (error) {
      console.error('Error starting audio processing:', error);
      throw error;
    }
  }

  async stopProcessing() {
    // Check out how to graciously end this if any samples are still being processed.
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
