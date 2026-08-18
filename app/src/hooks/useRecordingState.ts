import React, { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";
import useTimer from "./useTimer";
import usePatientMetadata from "./usePatientMetadata";
import { createAudioChunkMessage, createRecordingStartMessage } from "../utils/messages";
import { WebSocketFormData, WebSocketIncomingMessage } from "../types/websocket";
import { PatientMetadata } from "../types/metadata";

import useWsMessageReducer from "./useWsMessageReducer";
import { wsManager } from "@/lib/managers/WebSocketConnectionManager";
import { audioStreamManager } from "@/lib/managers/AudioStreamManager";

export default function useRecordingState() {
    const wsState = useSyncExternalStore(wsManager.subscribe, wsManager.getSnapshot);

    const { timerState, startTimer, stopTimer } = useTimer();
    const { metadata, updateField, setDescription } =
        usePatientMetadata(wsManager.sendMessage);
    const [recordingState, setRecordingState] = useState({
        isFinalizingTranscription: false,
        isRecording: false,
    });

    const wsMessageStartAck = useCallback(async () => {
        console.log('ACK Received');
        await audioStreamManager.startStream();
    }, []);
    const wsMessageError = useCallback(async () => {
        await cleanupRef.current();
        setRecordingState({ isRecording: false, isFinalizingTranscription: false });
    }, []);
    const wsMessageFormData = useCallback((data: WebSocketFormData) => {
        if (data) {
          const { organ, name, age, pesel, description } = data;
          
          if (organ !== undefined) {
            updateField("organ", organ);
          }
          if (name !== undefined) {
            updateField("name", name);
          }
          if (age !== undefined) {
            updateField("age", age);
          }
          if (pesel !== undefined) {
            updateField("pesel", pesel);
          }
          if (description !== undefined) {
            setDescription(description);
          }
          setRecordingState({
            isRecording: false,
            isFinalizingTranscription: false
          });
        }
    }, []);
    const wsMessageReducer = useWsMessageReducer(wsMessageStartAck, wsMessageError, wsMessageFormData);

    const onAudioCallback = useCallback((b64data: string) => {
        const message = createAudioChunkMessage(b64data, metadata);
        wsManager.sendMessage(message);
    }, [metadata]); 
    const cleanupRecording = useCallback(async () => {
        await audioStreamManager.stopStream();
        stopTimer();
    }, [stopTimer]);

    // Ref is required here to ensure that audio processor has always
    // access to the fresh reference of the callback.
    const onAudioRef = useRef(onAudioCallback);
    const cleanupRef = useRef(cleanupRecording);

    const finalizeTranscription = useCallback(async () => {
        if (recordingState.isRecording) {
            await cleanupRef.current();
            wsManager.sendMessage({ type: 'stop_recording' });
            setRecordingState({
                isFinalizingTranscription: true,
                isRecording: false
            });
        }
    }, [recordingState.isRecording]);

    const startRecording = useCallback(async () => {
        wsManager.sendMessage(createRecordingStartMessage(metadata));
    }, [metadata]);

    const handleDisconnect = useCallback(async () => {
        await cleanupRef.current();
        wsManager.disconnect();
        setRecordingState({
            isRecording: false,
            isFinalizingTranscription: false,
        });
    }, []);
    const handleConnect = useCallback(() => {
        wsManager.connect();
    }, []);
    const handleFieldUpdate = useCallback((fieldName: keyof PatientMetadata, value: string) => {
        updateField(fieldName, value);
    }, [updateField]);

    useEffect(() => {
        onAudioRef.current = onAudioCallback;
    }, [onAudioCallback]);

    useEffect(() => {
        cleanupRef.current = cleanupRecording;
    }, [cleanupRecording]);
    

    useEffect(() => {
        const onWsMessage = async (e: CustomEventInit<WebSocketIncomingMessage>) => { 
            await wsMessageReducer(e.detail!);
        };
        const cleanupCallback = async () => {
            await cleanupRef.current();
            setRecordingState({
                isRecording: false,
                isFinalizingTranscription: false
            });
        };
        const audioDataCallback = (e: CustomEventInit<string>) => {
            onAudioRef.current(e.detail!);
        };
        const streamOpenCallback = () => {
            startTimer();
            setRecordingState({
                isRecording: true,
                isFinalizingTranscription: false
            });
        };

        wsManager.addEventListener('message', onWsMessage);
        wsManager.addEventListener('close', cleanupCallback);
        wsManager.addEventListener('error', cleanupCallback);

        audioStreamManager.addEventListener('stream_error', cleanupCallback);
        audioStreamManager.addEventListener('stream_open', streamOpenCallback);
        audioStreamManager.addEventListener('audio_data', audioDataCallback);

        return () => {
            wsManager.removeEventListener('message', onWsMessage);
            wsManager.removeEventListener('close', cleanupCallback);
            wsManager.removeEventListener('error', cleanupCallback);
            audioStreamManager.removeEventListener('stream_error', cleanupCallback);
            audioStreamManager.removeEventListener('stream_open', streamOpenCallback);
            audioStreamManager.removeEventListener('audio_data', audioDataCallback);
            cleanupRef.current();
        }
    }, []);

    return { 
        timer: {
            startTimer,
            stopTimer,
            timerState
        }, 
        isConnected: wsState.isConnected,
        metadata,
        recordingState,
        handleConnect,
        handleDisconnect,
        startRecording, 
        finalizeTranscription,
        handleFieldUpdate
    };
}