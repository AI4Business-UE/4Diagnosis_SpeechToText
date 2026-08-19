import { WebSocketIncomingMessage } from "@/types/websocket";
import { GenericManager } from "../managers/GenericManager";
import { wsManager } from "../managers/WebSocketConnectionManager";
import { audioStreamManager } from "../managers/AudioStreamManager";
import { RecordingControllerState, ConnectionState, RecordingState } from "@/types/recordingState";

class RecordingMessageController extends EventTarget implements GenericManager {
    private state: RecordingControllerState = {
        connectionState: 'disconnected',
        recordingState: 'idle'
    };
    private callbacks: Set<() => void> = new Set();

    public constructor() {
        super();

        wsManager.subscribeToClass('open', this.handleConnectionOpen);
        wsManager.subscribeToClass('close', this.handleConnectionClose);
        wsManager.subscribeToClass('message', this.handleWebSocketMessage);
        wsManager.subscribeToClass('error', this.handleConnectionError);

        audioStreamManager.addEventListener('audio_data', this.onAudioData);
        audioStreamManager.addEventListener('stream_error', this.onAudioProcessingError);
        audioStreamManager.addEventListener('stream_open', this.onAudioStreamOpen);
    }

    public subscribe = (callback: () => void) => {
        this.callbacks.add(callback);

        return () => this.callbacks.delete(callback);
    }

    public getSnapshot = () => {
        return this.state;
    }

    private emitChanges = () => {
        this.callbacks.forEach(callback => callback());
    }

    private updateConnectionState = (newState: ConnectionState) => {
        this.state = { ...this.state, connectionState: newState };
        this.emitChanges();
    }

    private updateRecordingState = (newState: RecordingState) => {
        this.state = { ...this.state, recordingState: newState };
        this.emitChanges();
    }
    
    private handleConnectionOpen = async () => {
        this.updateConnectionState('connected');
    }

    private handleConnectionClose = async () => {
        await audioStreamManager.stopStream();
        this.updateConnectionState('disconnected');
        this.updateRecordingState('idle');
    }

    private handleConnectionError = async () => {
        await audioStreamManager.stopStream();
        this.updateConnectionState('disconnected');
        this.updateRecordingState('idle');
    }

    private onWebSocketProcessingError = async () => {
        wsManager.disconnect();
        await audioStreamManager.stopStream();
        this.updateConnectionState('disconnected');
        this.updateRecordingState('idle');
    }

    private onAudioProcessingError = async () => {
        await audioStreamManager.stopStream();
        wsManager.sendMessage({ type: 'error' });
        this.updateRecordingState('idle');
    }

    private onAudioData = (e: CustomEventInit<string>) => {
        if (!e.detail) {
            throw new Error('No audio data received in callback');
        }

        wsManager.sendMessage({ type: 'audio_chunk', data: e.detail });
    }

    private onAudioStreamOpen = () => {
        this.updateRecordingState('recording');
    }

    private handleWebSocketMessage = async (message: CustomEventInit<WebSocketIncomingMessage>) => {
        const detail = message.detail;

        if (!detail) {
            throw new Error("WebSocket message received in an unexpected format!");
        }

        try {   
            switch(detail.type) {
                case 'recording_start': {
                    if (detail.ack) {
                        await audioStreamManager.startStream();
                    }
                } break;
                case 'error': {
                    console.error("Server error occurred during processing");
                    await audioStreamManager.stopStream();
                    this.updateRecordingState('idle');
                } break;
                case 'form_data': {
                    this.dispatchEvent(new CustomEvent('form_data', { 
                        detail: { 
                            data: detail.formData, 
                            callback: () => this.updateRecordingState('idle')
                        } 
                    }));
                } break;
            }
        } catch (e) {
            console.error("Error occurred during handling of websocket message event.");
            await this.onWebSocketProcessingError();
        }
    };

    public connectToServer = () => {
        if (this.state.connectionState === 'disconnected') {
            wsManager.connect();
            return;
        }

        throw new Error('WebSocket is already connected');
    };

    public disconnectFromServer = () => {
        if (this.state.connectionState === 'connected') {
            wsManager.disconnect();
            return;
        }

        throw new Error('WebSocket is not connected');
    }

    public finalizeTranscription = async () => {
        if (this.state.recordingState === 'recording') {
            await audioStreamManager.stopStream();
            wsManager.sendMessage({ type: 'stop_recording' });
            this.updateRecordingState('finalizing');
            return;
        }
    }

    public startRecording = () => {
        if (this.state.recordingState === 'idle' && this.state.connectionState === 'connected') {
            wsManager.sendMessage({ type: 'recording_start' });
            return;
        }

        throw new Error(`Trying to start recording with invalid controller state: 
            recordingState: ${this.state.recordingState}; connectionState: ${this.state.connectionState}`);
    }
};

export const recrodingMessageController = new RecordingMessageController();