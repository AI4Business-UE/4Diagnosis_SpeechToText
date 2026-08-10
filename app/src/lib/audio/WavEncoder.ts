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

  // Convert Float32Array to base64 string
  float32ArrayToBase64(array: Float32Array): string {
    const buffer = new ArrayBuffer(array.length * 4); // 4 bytes per float32
    const view = new Float32Array(buffer);
    view.set(array);
    return this.arrayBufferToBase64(buffer);
  }
}