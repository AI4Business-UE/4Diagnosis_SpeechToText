
export const createWebSocketConnection = <IncomingMessageType, OutgoingMessageType>(url: string) => {
    const connect = (
        onOpen: () => void,
        onMessage: (message: IncomingMessageType) => void,
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
                onOpen();
                resolve(ws);
            };

            const handleMessage = (event: MessageEvent) => {
                try {
                    const message: IncomingMessageType = JSON.parse(event.data);
                    onMessage(message);
                } catch (error) {
                    console.error("Error parsing WebSocket message:", error);
                }
            };

            const handleError = (error: Event) => {
                onError(error);
                cleanup();
                reject(error);
            };

            const handleClose = () => {
                onClose();
                cleanup()
            };

            ws.addEventListener("open", handleOpen);
            ws.addEventListener("message", handleMessage);
            ws.addEventListener("error", handleError);
            ws.addEventListener("close", handleClose);
        });
    };

    const send = (ws: WebSocket | null, message: OutgoingMessageType): boolean => {
        if (ws?.readyState === WebSocket.OPEN) {
            console.log('WS READY');
            ws.send(JSON.stringify(message));
            return true;
        }
        console.log('WS NOT READY');
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