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


export default function usePatientMetadata(sendMessage: (message: WebSocketOutgoingMessage) => boolean) {
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
        wsManager.sendMessage(createMetadataUpdateMessage(newMetadata));
        return newMetadata;
      });
    },
    []
  );

  const clearDescriptionField = useCallback(() => {
    setMetadata((prevMetadata) => {
      const newMetadata = clearDescription(prevMetadata);
      wsManager.sendMessage(createMetadataUpdateMessage(newMetadata));
      return newMetadata;
    });
  }, []);

  return {
    metadata,
    updateField,
    clearDescriptionField,
    setDescription: (description: string) =>
      updateField("description", description),
  };
};