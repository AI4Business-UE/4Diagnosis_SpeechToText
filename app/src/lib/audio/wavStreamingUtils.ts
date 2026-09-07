// Utils for WAV streaming functionality
// Utilities for advanced WAV streaming features

export interface StreamingConfig {
  sampleRate: number;
  channels: number;
  bufferSize: number;
  chunkDuration: number;
}

export const DEFAULT_STREAMING_CONFIG: StreamingConfig = {
  sampleRate: 16000,
  channels: 1,
  bufferSize: 4096,
  chunkDuration: 250
};

export class WAVStreamingMonitor {
  private bytesSent: number = 0;
  private chunksSent: number = 0;
  private startTime: number = 0;
  private lastChunkTime: number = 0;

  start(): void {
    this.startTime = Date.now();
    this.lastChunkTime = this.startTime;
    this.bytesSent = 0;
    this.chunksSent = 0;
  }

  recordChunk(chunkSize: number): void {
    this.bytesSent += chunkSize;
    this.chunksSent++;
    this.lastChunkTime = Date.now();
  }

  getStats() {
    const now = Date.now();
    const duration = now - this.startTime;
    const timeSinceLastChunk = now - this.lastChunkTime;
    
    return {
      bytesSent: this.bytesSent,
      chunksSent: this.chunksSent,
      durationMs: duration,
      avgBytesPerSecond: duration > 0 ? (this.bytesSent / duration) * 1000 : 0,
      avgChunksPerSecond: duration > 0 ? (this.chunksSent / duration) * 1000 : 0,
      timeSinceLastChunkMs: timeSinceLastChunk,
      isActive: timeSinceLastChunk < 1000 // Active if last chunk was sent within the last second
    };
  }

  reset(): void {
    this.bytesSent = 0;
    this.chunksSent = 0;
    this.startTime = 0;
    this.lastChunkTime = 0;
  }
}

// Utility to validate WAV streaming support
export const validateWAVStreamingSupport = (): { 
  supported: boolean; 
  issues: string[] 
} => {
  const issues: string[] = [];
  
  // Check for Web Audio API
  if (typeof AudioContext === 'undefined' && typeof (window as any).webkitAudioContext === 'undefined') {
    issues.push('Web Audio API not supported');
  }
  
  // Check for MediaStream API
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    issues.push('MediaStream API not supported');
  }
  
  // Check for WebSocket support
  if (typeof WebSocket === 'undefined') {
    issues.push('WebSocket API not supported');
  }
  
  // Check for ArrayBuffer support
  if (typeof ArrayBuffer === 'undefined') {
    issues.push('ArrayBuffer not supported');
  }
  
  // Check for DataView support
  if (typeof DataView === 'undefined') {
    issues.push('DataView not supported');
  }

  return {
    supported: issues.length === 0,
    issues
  };
};

// Create optimized WAV header for streaming
export const createStreamingWAVHeader = (config: StreamingConfig): ArrayBuffer => {
  const buffer = new ArrayBuffer(44);
  const view = new DataView(buffer);
  
  // WAV header for streaming (placeholder values for data size)
  const writeString = (offset: number, string: string) => {
    for (let i = 0; i < string.length; i++) {
      view.setUint8(offset + i, string.charCodeAt(i));
    }
  };
  
  writeString(0, 'RIFF');
  view.setUint32(4, 0, true); // Placeholder for file size
  writeString(8, 'WAVE');
  writeString(12, 'fmt ');
  view.setUint32(16, 16, true); // PCM format size
  view.setUint16(20, 1, true);  // PCM format
  view.setUint16(22, config.channels, true);
  view.setUint32(24, config.sampleRate, true);
  view.setUint32(28, config.sampleRate * config.channels * 2, true); // Byte rate
  view.setUint16(32, config.channels * 2, true); // Block align
  view.setUint16(34, 16, true); // Bits per sample
  writeString(36, 'data');
  view.setUint32(40, 0, true); // Placeholder for data size
  
  return buffer;
};

// Log streaming statistics
export const logStreamingStats = (monitor: WAVStreamingMonitor): void => {
  const stats = monitor.getStats();
  console.log('📊 WAV Streaming Stats:', {
    'Bytes sent': `${(stats.bytesSent / 1024).toFixed(2)} KB`,
    'Chunks sent': stats.chunksSent,
    'Duration': `${(stats.durationMs / 1000).toFixed(1)}s`,
    'Avg bytes/sec': `${(stats.avgBytesPerSecond / 1024).toFixed(2)} KB/s`,
    'Avg chunks/sec': stats.avgChunksPerSecond.toFixed(1),
    'Time since last chunk': `${stats.timeSinceLastChunkMs}ms`,
    'Status': stats.isActive ? '🟢 Active' : '🔴 Inactive'
  });
};
