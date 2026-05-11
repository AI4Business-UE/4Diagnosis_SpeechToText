import { WebSocketMessage } from "./types";

export const createWebSocketConnection = (url: string) => {
    const connect = (
        onOpen: () => void,
        onMessage: (message: WebSocketMessage) => void,
        onError: (error: Event) => void,
        onClose: () => void
    ): Promise<WebSocket> => {
        return new Promise((resolve, reject) => {
            const ws = new WebSocket(url);

            const cleanup = () => {
                ws.removeEventListener("open", handleOpen);
                ws.removeEventListener("message", handleMessage);
                ws.removeEventListener("error", handleError);
                ws.removeEventListener("close", handleClose);
            };

            const handleOpen = () => {
                cleanup();
                onOpen();
                resolve(ws);
            };

            const handleMessage = (event: MessageEvent) => {
                try {
                    const message: WebSocketMessage = JSON.parse(event.data);
                    onMessage(message);
                } catch (error) {
                    console.error("Error parsing WebSocket message:", error);
                }
            };

            const handleError = (error: Event) => {
                cleanup();
                onError(error);
                reject(error);
            };

            const handleClose = () => {
                onClose();
            };

            ws.addEventListener("open", handleOpen);
            ws.addEventListener("message", handleMessage);
            ws.addEventListener("error", handleError);
            ws.addEventListener("close", handleClose);
        });
    };

    const send = (ws: WebSocket | null, message: WebSocketMessage): boolean => {
        if (ws?.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify(message));
            return true;
        }
        return false;
    };

    const disconnect = (ws: WebSocket | null): void => {
        if (ws) {
            ws.close();
        }
    };

    const isConnected = (ws: WebSocket | null): boolean =>
        ws?.readyState === WebSocket.OPEN || false;

    return { connect, send, disconnect, isConnected };
};
