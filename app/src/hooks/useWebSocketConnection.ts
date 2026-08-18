import { useCallback, useEffect, useMemo, useState } from "react";
import { ConnectionState } from "../types/websocket";
import { createWebSocketConnection } from "../utils/websocket";

export default function useWebSocketConnection
    <IncomingMessageType, OutgoingMessageType>(url: string, messageReducer: (wsMessage: IncomingMessageType) => void) {
  const [connectionState, setConnectionState] = useState<ConnectionState>({
    isConnected: false,
    ws: null,
  });

  const wsUtilities = useMemo(
    () => createWebSocketConnection<IncomingMessageType, OutgoingMessageType>(url),
    [url]
  );
  
  const connect = useCallback(async () => {
    try {
      const ws = await wsUtilities.connect(
        () => setConnectionState((prev) => ({ ...prev, isConnected: true })),
        messageReducer,
        () => setConnectionState({ isConnected: false, ws: null }),
        () => setConnectionState({ isConnected: false, ws: null })
      );

      setConnectionState({ isConnected: true, ws });
    } catch (error) {
      console.error("Failed to connect:", error);
      setConnectionState({ isConnected: false, ws: null });
    }
  }, [url, messageReducer]);

  const disconnect = useCallback(() => {
    wsUtilities.disconnect(connectionState.ws);
    setConnectionState({ isConnected: false, ws: null });
  }, [connectionState.ws]);

  const sendMessage = useCallback(
    (message: OutgoingMessageType): boolean => {
      return wsUtilities.send(connectionState.ws, message);
    },
    [connectionState.ws]);

  useEffect(() => {
    return () => {
      wsUtilities.disconnect(connectionState.ws);
    };
  }, [wsUtilities, connectionState.ws]);

  return {
    ...connectionState,
    connect,
    disconnect,
    sendMessage,
  };
};