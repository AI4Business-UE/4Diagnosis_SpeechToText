import { WEBSOCKET_URL } from "@/config";
import { WebSocketIncomingMessage, WebSocketOutgoingMessage } from "@/types/websocket";
import { createMessage } from "@/utils/messages";
import { GenericManager } from "./GenericManager";

type WebSocketEventType = 'open' | 'close' | 'error' | 'message';
type WebSocketEventCallback = (() => Promise<void>) | ((message: CustomEventInit<WebSocketIncomingMessage>) => Promise<void>);

class WebSocketConnectionManager extends EventTarget implements GenericManager {
    private state = {
        isConnected: false
    }
    private ws: WebSocket | null = null;
    private callbacks: Set<() => void> = new Set();

    public getSnapshot = () => {
        return this.state;
    }

    public subscribe = (callback: () => void) => {
        this.callbacks.add(callback);
        return () => this.callbacks.delete(callback);
    }

    private onOpen = (e: Event) => {
        this.dispatchEvent(new CustomEvent('open'));
        this.state = { isConnected: true };
        this.emitChange();
    }

    private onClose = (e: Event) => {
        this.dispatchEvent(new CustomEvent('close'));
        this.state = { isConnected: false };
        this.emitChange();

        this.cleanup();
    }

    private onError = (e: Event) => {
        this.dispatchEvent(new CustomEvent('error'));
        this.state = { isConnected: false };
        this.emitChange();

        this.cleanup();
    }

    private onMessage = (e: MessageEvent) => {
        try {
            const incommingMessage: WebSocketIncomingMessage = JSON.parse(e.data);
            this.dispatchEvent(new CustomEvent('message', { detail: incommingMessage }));
        } catch (e) {
            console.error("Error parsing WebSocket message.");
        }
    }

    private cleanup = () => {
        if (this.ws) {
            this.ws.removeEventListener('open', this.onOpen);
            this.ws.removeEventListener('close', this.onClose);
            this.ws.removeEventListener('error', this.onError);
            this.ws.removeEventListener('message', this.onMessage);

            this.ws = null;
        }
    }

    public sendMessage = (message: WebSocketOutgoingMessage) => {
        if (this.ws?.readyState === WebSocket.OPEN) { 
            this.ws?.send(
                JSON.stringify(message)
            );
            return;
        }

        throw new Error('Trying to send websocket message without connection established');
    }

    public connect = () => {
        if (!this.ws) {
            this.ws = new WebSocket(WEBSOCKET_URL);

            this.ws.addEventListener('open', this.onOpen);
            this.ws.addEventListener('close', this.onClose);
            this.ws.addEventListener('error', this.onError);
            this.ws.addEventListener('message', this.onMessage);
        }
    }

    public subscribeToClass = (type: WebSocketEventType, callback: WebSocketEventCallback) => {
        this.addEventListener(type, callback);
    }

    public deleteSubscriptionToClass = (type: WebSocketEventType, callback: WebSocketEventCallback) => {
        this.removeEventListener(type, callback);
    }

    public disconnect = () => { 
        if (this.ws) {
            this.ws.close();
        }
    }

    private emitChange = () => {
        this.callbacks.forEach(callback => callback());
    }
}

export const wsManager = new WebSocketConnectionManager();