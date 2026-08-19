export type ConnectionState = 
  'disconnected' |
  'connected';

export type RecordingState = 
  'idle' |
  'recording' |
  'finalizing';

export type RecordingControllerState = {
  connectionState: ConnectionState;
  recordingState: RecordingState;
}