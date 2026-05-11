// Utility functions for audio processing and WAV conversion

export class WavEncoder {
  private sampleRate: number;
  private numChannels: number;
  private bitDepth: number;

  constructor(sampleRate: number = 16000, numChannels: number = 1, bitDepth: number = 16) {
    this.sampleRate = sampleRate;
    this.numChannels = numChannels;
    this.bitDepth = bitDepth;
  }

  // Convert Float32Array audio data to WAV format
  encodeWAV(audioData: Float32Array): ArrayBuffer {
    const length = audioData.length;
    const bytesPerSample = this.bitDepth / 8;
    const buffer = new ArrayBuffer(44 + length * bytesPerSample);
    const view = new DataView(buffer);

    // WAV header
    this.writeString(view, 0, 'RIFF');
    view.setUint32(4, 36 + length * bytesPerSample, true);
    this.writeString(view, 8, 'WAVE');
    this.writeString(view, 12, 'fmt ');
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, this.numChannels, true);
    view.setUint32(24, this.sampleRate, true);
    view.setUint32(28, this.sampleRate * this.numChannels * bytesPerSample, true);
    view.setUint16(32, this.numChannels * bytesPerSample, true);
    view.setUint16(34, this.bitDepth, true);
    this.writeString(view, 36, 'data');
    view.setUint32(40, length * bytesPerSample, true);

    // Convert float samples to PCM
    if (this.bitDepth === 16) {
      this.floatTo16BitPCM(view, 44, audioData);
    } else if (this.bitDepth === 8) {
      this.floatTo8BitPCM(view, 44, audioData);
    }

    return buffer;
  }

  private writeString(view: DataView, offset: number, string: string): void {
    for (let i = 0; i < string.length; i++) {
      view.setUint8(offset + i, string.charCodeAt(i));
    }
  }

  private floatTo16BitPCM(output: DataView, offset: number, input: Float32Array): void {
    for (let i = 0; i < input.length; i++, offset += 2) {
      const s = Math.max(-1, Math.min(1, input[i]));
      output.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
    }
  }

  private floatTo8BitPCM(output: DataView, offset: number, input: Float32Array): void {
    for (let i = 0; i < input.length; i++, offset += 1) {
      const s = Math.max(-1, Math.min(1, input[i]));
      const value = Math.round((s + 1) * 127.5); // Convert to 0-255 range
      output.setUint8(offset, value);
    }
  }

  // Convert ArrayBuffer to base64 string
  arrayBufferToBase64(buffer: ArrayBuffer): string {
    const bytes = new Uint8Array(buffer);
    let binary = '';
    for (let i = 0; i < bytes.byteLength; i++) {
      binary += String.fromCharCode(bytes[i]);
    }
    return btoa(binary);
  }
}

export class AudioStreamProcessor {
  private audioContext: AudioContext | null = null;
  private processor: ScriptProcessorNode | null = null;
  private wavEncoder: WavEncoder;
  private onAudioData: (base64Data: string) => void;
  private bufferQueue: Float32Array[] = [];
  private isProcessing: boolean = false;

  constructor(
    onAudioData: (base64Data: string) => void,
    sampleRate: number = 16000,
    bitDepth: number = 16
  ) {
    this.onAudioData = onAudioData;
    this.wavEncoder = new WavEncoder(sampleRate, 1, bitDepth);
  }

  async startProcessing(stream: MediaStream): Promise<void> {
    try {
      // Sprawdź czy browser obsługuje wymaganą częstotliwość próbkowania
      const constraints = stream.getTracks()[0].getSettings();
      console.log('Aktualne ustawienia audio:', constraints);

      this.audioContext = new AudioContext({ sampleRate: 16000 });
      const source = this.audioContext.createMediaStreamSource(stream);
      
      // Use ScriptProcessorNode for audio processing (deprecated but still works)
      // Alternative: Use AudioWorklet for modern browsers
      this.processor = this.audioContext.createScriptProcessor(4096, 1, 1);
      
      this.processor.onaudioprocess = (event) => {
        if (!this.isProcessing) return;
        
        const inputBuffer = event.inputBuffer;
        const audioData = inputBuffer.getChannelData(0);
        
        // Create a copy of the audio data
        const float32Data = new Float32Array(audioData.length);
        float32Data.set(audioData);
        
        // Add to queue for batch processing
        this.bufferQueue.push(float32Data);
        
        // Process in batches to avoid overwhelming the system
        if (this.bufferQueue.length >= 2) { // Process every 2 buffers (~512ms at 4096 samples)
          this.processBatch();
        }
      };

      source.connect(this.processor);
      this.processor.connect(this.audioContext.destination);
      this.isProcessing = true;
      
      console.log('✅ WAV Audio streaming rozpoczęty - częstotliwość:', this.audioContext.sampleRate, 'Hz');
      
    } catch (error) {
      console.error('Error starting audio processing:', error);
      throw error;
    }
  }

  private processBatch(): void {
    try {
      if (this.bufferQueue.length === 0) return;
      
      // Combine all buffers in queue
      const totalLength = this.bufferQueue.reduce((sum, buffer) => sum + buffer.length, 0);
      const combinedBuffer = new Float32Array(totalLength);
      
      let offset = 0;
      for (const buffer of this.bufferQueue) {
        combinedBuffer.set(buffer, offset);
        offset += buffer.length;
      }
      
      // Clear the queue
      this.bufferQueue = [];
      
      // Convert to WAV and encode to base64
      const wavBuffer = this.wavEncoder.encodeWAV(combinedBuffer);
      const base64Data = this.wavEncoder.arrayBufferToBase64(wavBuffer);
      
      // Send the WAV data
      this.onAudioData(base64Data);
      
    } catch (error) {
      console.error('Error processing audio batch:', error);
    }
  }

  stopProcessing(): void {
    this.isProcessing = false;
    
    // Process any remaining buffers
    if (this.bufferQueue.length > 0) {
      console.log('Processing remaining', this.bufferQueue.length, 'audio buffers');
      this.processBatch();
    }
    
    if (this.processor) {
      this.processor.disconnect();
      this.processor = null;
    }
    
    if (this.audioContext) {
      this.audioContext.close();
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
