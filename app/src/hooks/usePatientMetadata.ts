import { useCallback, useState } from "react";
import { WebSocketOutgoingMessage } from "../types/websocket";
import { PatientMetadata } from "../types/metadata";
import { createMetadataUpdateMessage } from "../utils/messages";
import { wsManager } from "@/lib/managers/WebSocketConnectionManager";

export const createEmptyMetadata = (): PatientMetadata => ({
  organ: "",
  name: "",
  age: "",
  pesel: "",
  description: "",
});

export const updateMetadataField = (
  metadata: PatientMetadata,
  field: keyof PatientMetadata,
  value: string
): PatientMetadata => ({
  ...metadata,
  [field]: value,
});

export const clearDescription = (metadata: PatientMetadata): PatientMetadata =>
  updateMetadataField(metadata, "description", "");

const PATIENT_META_KEY = 'selectedPatient';

const updatePatientStoredMetadata = (metadata: PatientMetadata, value: string) => {
  localStorage.setItem(PATIENT_META_KEY, JSON.stringify(metadata));
}

const clearPatientStoredMetadata = () => {
  localStorage.removeItem(PATIENT_META_KEY);
};

export default function usePatientMetadata() {
  const [metadata, setMetadata] = useState<PatientMetadata>(() => {
    // Pobierz dane pacjenta z localStorage
    const savedPatient = localStorage.getItem(PATIENT_META_KEY);
    if (savedPatient) {
      try {
        const patient = JSON.parse(savedPatient);
        const initialMetadata = {
          organ: patient.organ,
          name: patient.name,
          age: patient.age ?? "",
          pesel: patient.pesel || "",
          description: patient.description,
        };
        return initialMetadata;
      } catch (error) {
        console.error('Error parsing patient data:', error);
      }
    }
    console.log('No patient data found in localStorage, using empty metadata');
    return createEmptyMetadata();
  });

  const sendMessage = useCallback((message: WebSocketOutgoingMessage) => {
    try {
      wsManager.sendMessage(message);
    } catch (e) {
      // intentionall pass through to ignore connection errors;
    }
  }, []);

  const updateField = useCallback(
    (field: keyof PatientMetadata, value: string) => {
      setMetadata((prevMetadata) => {
        const newMetadata = updateMetadataField(prevMetadata, field, value);
        sendMessage(createMetadataUpdateMessage(newMetadata));
        // updatePatientStoredMetadata(newMetadata, value);
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

    //clearPatientStoredMetadata();
  }, [sendMessage]);

  return {
    metadata,
    updateField,
    clearDescriptionField,
    setDescription: (description: string) => updateField("description", description),
  };
};