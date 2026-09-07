import { useCallback, useEffect, useRef, useSyncExternalStore } from "react";
import useTimer from "./useTimer";
import usePatientMetadata from "./usePatientMetadata";
import { PatientMetadata } from "../types/metadata";

import { recrodingMessageController } from "@/lib/controllers/RecordingMessageController";
import { WebSocketFormData } from "@/types/websocket";

export default function useRecordingState() {
    const state = useSyncExternalStore(
        recrodingMessageController.subscribe, 
        recrodingMessageController.getSnapshot
    );

    const { timerState, startTimer, stopTimer } = useTimer();
    const { metadata, updateField, setDescription } = usePatientMetadata();

    const finalizeTranscription = useCallback(async () => {
        stopTimer();
        await recrodingMessageController.finalizeTranscription();
    }, [stopTimer]);

    const startRecording = useCallback(recrodingMessageController.startRecording, []);

    const handleDisconnect = useCallback(() => {
        stopTimer();
        recrodingMessageController.disconnectFromServer();
    }, [stopTimer]);
    const handleConnect = useCallback(recrodingMessageController.connectToServer, []);

    const handleFieldUpdate = useCallback((fieldName: keyof PatientMetadata, value: string) => {
        updateField(fieldName, value);
    }, [updateField]); 
    const handleFieldRef = useRef(handleFieldUpdate);

    useEffect(() => {
        if (state.recordingState === 'recording') {
            startTimer();
        }

        return () => stopTimer();
    }, [state.recordingState, stopTimer, startTimer]);

    useEffect(() => {
        const handleFormData = (e: CustomEventInit<{ data: WebSocketFormData | undefined; callback: () => void }>) => {
            if (!e.detail?.data) {
                throw new Error('Received corrupted form data from the server');
            }

            const updateCallback = e.detail.callback;
            const { organ, name, age, pesel, description } = e.detail.data;

            if (organ !== undefined) {
                handleFieldRef.current("organ", organ);
            }
            if (name !== undefined) {
                handleFieldRef.current("name", name);
            }
            if (age !== undefined) {
                handleFieldRef.current("age", age);
            }
            if (pesel !== undefined) {
                handleFieldRef.current("pesel", pesel);
            }
            if (description !== undefined) {
                handleFieldRef.current("description", description);
            }

            updateCallback();
        };

        recrodingMessageController.addEventListener('form_data', handleFormData);
        return () => recrodingMessageController.removeEventListener('form_data', handleFormData);
    }, []);

    return { 
        timer: {
            startTimer,
            stopTimer,
            timerState
        }, 
        connectionState: state.connectionState,
        recordingState: state.recordingState,
        metadata,
        handleConnect,
        handleDisconnect,
        startRecording, 
        finalizeTranscription,
        handleFieldUpdate
    };
}