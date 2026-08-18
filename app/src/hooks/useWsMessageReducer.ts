import { useCallback } from "react";
import { WebSocketFormData, WebSocketIncomingMessage } from "../types/websocket";

export default function useWsMessageReducer(
    onRecordingStart: () => Promise<void>,
    onError: () => Promise<void>,
    onFormData: (formData: WebSocketFormData) => void
) {
    const reducer = useCallback(async (wsMessage: WebSocketIncomingMessage) => {
        switch(wsMessage.type) {
            case 'recording_start': {
                if (wsMessage.ack) {
                    await onRecordingStart();
                }
            } break;
            case 'error': {
                await onError();
            } break;
            case 'form_data': {
                if (wsMessage.formData) onFormData(wsMessage.formData);
            } break;
        }
    }, [onRecordingStart, onError, onFormData]);

    return reducer;
}