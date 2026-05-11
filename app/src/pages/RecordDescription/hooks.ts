import { useState, useCallback, useEffect } from "react";
import {
  ConnectionState,
  RecordingState,
  PatientMetadata,
  WebSocketMessage,
} from "./types";
import {
  createEmptyMetadata,
  updateMetadataField,
  clearDescription,
  createMetadataUpdateMessage,
} from "./utils";
import { createWebSocketConnection } from "./websocketService";
import { createTimerUtilities } from "./timerService";

export const useWebSocketConnection = (url: string) => {
  const [connectionState, setConnectionState] = useState<ConnectionState>({
    isConnected: false,
    ws: null,
  });

  const wsUtilities = createWebSocketConnection(url);

  const connect = useCallback(async () => {
    try {
      const ws = await wsUtilities.connect(
        () => setConnectionState((prev) => ({ ...prev, isConnected: true })),
        (message) => {
          // Obsługa wiadomości od serwera - przekazywane do Recorder.tsx przez useEffect
        },
        () => setConnectionState({ isConnected: false, ws: null }),
        () => setConnectionState({ isConnected: false, ws: null })
      );

      setConnectionState({ isConnected: true, ws });
    } catch (error) {
      console.error("Failed to connect:", error);
      setConnectionState({ isConnected: false, ws: null });
    }
  }, [url]);

  const disconnect = useCallback(() => {
    wsUtilities.disconnect(connectionState.ws);
    setConnectionState({ isConnected: false, ws: null });
  }, [connectionState.ws]);

  const sendMessage = useCallback(
    (message: WebSocketMessage): boolean => {
      return wsUtilities.send(connectionState.ws, message);
    },
    [connectionState.ws]
  );

  useEffect(() => {
    return () => {
      wsUtilities.disconnect(connectionState.ws);
    };
  }, []);

  return {
    ...connectionState,
    connect,
    disconnect,
    sendMessage,
  };
};

export const useRecordingState = () => {
  const [recordingState, setRecordingState] = useState<RecordingState>({
    isRecording: false,
    time: "00:00",
    intervalId: null,
  });

  const timerUtilities = createTimerUtilities();

  const startRecording = useCallback(() => {
    const intervalId = timerUtilities.startTimer((time) => {
      setRecordingState((prev) => ({ ...prev, time }));
    });

    setRecordingState({
      isRecording: true,
      time: "00:00",
      intervalId,
    });
  }, []);

  const stopRecording = useCallback(() => {
    timerUtilities.stopTimer(recordingState.intervalId);
    setRecordingState({
      isRecording: false,
      time: "00:00",
      intervalId: null,
    });
  }, [recordingState.intervalId]);

  useEffect(() => {
    return () => {
      timerUtilities.stopTimer(recordingState.intervalId);
    };
  }, []);

  return {
    ...recordingState,
    startRecording,
    stopRecording,
  };
};

export const usePatientMetadata = (
  sendMessage: (message: WebSocketMessage) => boolean
) => {

  const calculateAge = (dateOfBirth: string) => {
    const today = new Date();
    const birth = new Date(dateOfBirth);
    let age = today.getFullYear() - birth.getFullYear();
    const monthDiff = today.getMonth() - birth.getMonth();
    if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < birth.getDate())) {
      age--;
    }
    return age.toString();
  };

  const [metadata, setMetadata] = useState<PatientMetadata>(() => {
    // Pobierz dane pacjenta z localStorage
    const savedPatient = localStorage.getItem('selectedPatient');
    if (savedPatient) {
      try {
        const patient = JSON.parse(savedPatient);
        const initialMetadata = {
          organ: "",
          name: `${patient.firstName} ${patient.lastName}`,
          age: patient.dateOfBirth ? calculateAge(patient.dateOfBirth) : "",
          pesel: patient.pesel || "",
          description: "",
        };
        return initialMetadata;
      } catch (error) {
        console.error('Error parsing patient data:', error);
      }
    }
    console.log('No patient data found in localStorage, using empty metadata');
    return createEmptyMetadata();
  });


  const updateField = useCallback(
    (field: keyof PatientMetadata, value: string) => {
      setMetadata((prevMetadata) => {
        const newMetadata = updateMetadataField(prevMetadata, field, value);
        sendMessage(createMetadataUpdateMessage(newMetadata));
        return newMetadata;
      });
    },
    [sendMessage]
  );

  const clearDescriptionField = useCallback(() => {
    setMetadata((prevMetadata) => {
      const newMetadata = clearDescription(prevMetadata);
      sendMessage(createMetadataUpdateMessage(newMetadata));
      return newMetadata;
    });
  }, [sendMessage]);

  return {
    metadata,
    updateField,
    clearDescriptionField,
    setDescription: (description: string) =>
      updateField("description", description),
  };
};
