import { useRef, useEffect, useCallback, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Mic, Play, Square, Wifi, WifiOff } from "lucide-react";


import { WebSocketMessage } from "./types";
import { WEBSOCKET_URL, AUDIO_CONFIG } from "./config";
import {
  createAudioChunkMessage,
  createRecordingStartMessage,
  createRecordingEndMessage,
} from "./utils";
import {
  useWebSocketConnection,
  useRecordingState,
  usePatientMetadata,
} from "./hooks";
import { createAudioUtilities } from "./audioService";
import { createAudioVisualizer } from "./visualizerService";
import { AudioStreamProcessor } from "@/lib/audioUtils_fixed";

export default function Recorder() {
  const { isConnected, ws, connect, disconnect, sendMessage } =
    useWebSocketConnection(WEBSOCKET_URL);
  const { isRecording, time, startRecording, stopRecording } =
    useRecordingState();
  const { metadata, updateField, clearDescriptionField, setDescription } =
    usePatientMetadata(sendMessage);
  const [extractedData, setExtractedData] = useState<{
    //organ?: string;
    fullName?: string;
    age?: string;
    pesel?: string;
  }>({});

  const [isTranscriptionFinalizing, setTranscriptionFinalizing] = useState(false);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const audioProcessorRef = useRef<AudioStreamProcessor | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const cleanupVisualizerRef = useRef<(() => void) | null>(null);

  const audioUtilities = createAudioUtilities(AUDIO_CONFIG);

  const visualizer = createAudioVisualizer();

  useEffect(() => {
    if (!ws) return;

    const handleMessage = (event: MessageEvent) => {
      try {
        console.log(`WS Event: ${event.name}`);
        const parsedData = JSON.parse(event.data) as {
          type: string;
          text?: string;
          transcription?: string;
          formData?: {
            //organ?: string;
            name?: string;
            age?: string;
            pesel?: string;
            description?: string;
          };
        };
        
        console.log("📨 Parsed WebSocket message:", parsedData);
        
        /*if ((parsedData.type === "transcription" || parsedData.type === "transcript") && (parsedData.text || parsedData.transcription)) {
          const newText = parsedData.text || parsedData.transcription;
          const trimmedNewText = newText.trim();

          if (trimmedNewText) {
            if (!metadata.description || !metadata.description.includes(trimmedNewText)) {
              const combinedText = metadata.description
                ? metadata.description + " " + trimmedNewText
                : trimmedNewText;
              setDescription(combinedText);
            }
          }
        }*/

        if (parsedData.type === "error") {
          setTranscriptionFinalizing(false);
        }
        
        // Obsługa wypełnionego formularza od backendu
        if (parsedData.type === "form_data" && parsedData.formData) {
          const { formData } = parsedData;
          
          // Wypełnij wszystkie pola niezależnie od tego czy są puste czy nie
          /*if (formData.organ !== undefined) {
            updateField("organ", formData.organ);
          }*/
          if (formData.name !== undefined) {
            updateField("name", formData.name);
          }
          if (formData.age !== undefined) {
            updateField("age", formData.age);
          }
          if (formData.pesel !== undefined) {
            updateField("pesel", formData.pesel);
          }
          if (formData.description !== undefined) {
            setDescription(formData.description);
          }

          setExtractedData({
            //organ: formData.organ,
            fullName: formData.name,
            age: formData.age,
            pesel: formData.pesel,
          });
          setTranscriptionFinalizing(false);
        } else if (parsedData.type === "form_data") {
          console.log("⚠️ Received form_data message but no formData field:", parsedData);

        }
      } catch (error) {
        console.error("❌ Error parsing WebSocket message:", error);
        console.error("Raw message:", event.data);
        setTranscriptionFinalizing(false);
      }
    };

    ws.addEventListener("message", handleMessage);
    return () => ws.removeEventListener("message", handleMessage);
  }, [ws, setDescription, updateField]);


  const handleStartRecording = useCallback(async () => {
    if (!isConnected) {
      alert("Najpierw połącz się z serwerem!");
      return;
    }

    try {
      const stream = await audioUtilities.getUserMedia();
      streamRef.current = stream;

      const handleAudioData = (base64Data: string) => {
        const audioMessage = createAudioChunkMessage(base64Data, metadata);
        sendMessage(audioMessage);
      };

      const audioProcessor = audioUtilities.createAudioStreamProcessor(
        stream,
        handleAudioData
      );
      audioProcessorRef.current = audioProcessor;

      await audioProcessor.startProcessing(stream);
      startRecording();
      sendMessage(createRecordingStartMessage(metadata));

      if (canvasRef.current) {
        cleanupVisualizerRef.current = visualizer.setupVisualizer(
          stream,
          canvasRef.current,
          () => { }
        );
      }
    } catch (error) {
      console.error("Error starting recording:", error);
      alert("Błąd podczas rozpoczynania nagrywania: " + error);
    }
  }, [isConnected, metadata, startRecording, sendMessage]);

  const handleStopRecording = useCallback(() => {
    if (audioProcessorRef.current && isRecording) {
      // Cast the message to your WebSocketMessage type
      sendMessage({ control: "stop_recording" } as WebSocketMessage);
      console.log("Sent stop_recording signal to server");

      // Then send the recording end message with metadata
      sendMessage(createRecordingEndMessage(metadata));

      // Finally stop the local recording
      audioProcessorRef.current.stopProcessing();
      audioUtilities.stopStream(streamRef.current);
      if (cleanupVisualizerRef.current) {
        cleanupVisualizerRef.current();
        cleanupVisualizerRef.current = null;
      }
      stopRecording();

      setTranscriptionFinalizing(true); 
    }
  }, [isRecording, stopRecording, sendMessage, metadata, audioUtilities]);

  useEffect(() => {
    return () => {
      if (audioProcessorRef.current) {
        audioProcessorRef.current.stopProcessing();
      }
      audioUtilities.stopStream(streamRef.current);
      if (cleanupVisualizerRef.current) {
        cleanupVisualizerRef.current();
      }
    };
  }, []);

  useEffect(() => {
    if (!isRecording) {
      visualizer.clearCanvas(canvasRef.current);
    }
  }, [isRecording]);

  return (
    <div className="bg-gradient-to-br from-blue-50 to-indigo-100 flex flex-col items-center justify-center p-4 min-h-screen w-full">
      <div className="mb-6 p-4 bg-white/90 rounded-lg shadow-md">
        <div className="flex items-center gap-3">
          {isConnected ? (
            <>
              <Wifi className="text-green-600" size={20} />
              <span className="text-green-600 font-medium">
                Połączono z serwerem
              </span>
              <Button
                onClick={disconnect}
                variant="outline"
                size="sm"
                className="ml-4"
              >
                Rozłącz
              </Button>
            </>
          ) : (
            <>
              <WifiOff className="text-red-600" size={20} />
              <span className="text-red-600 font-medium">Brak połączenia</span>
              <Button onClick={connect} size="sm" className="ml-4">
                Połącz
              </Button>
            </>
          )}
        </div>
      </div>

      <div className="flex flex-col lg:flex-row gap-8 w-full max-w-6xl">
        <Card className="flex-1 p-8 bg-white/90 shadow-xl">
          <div className="flex flex-col items-center gap-6">
            <div
              className={`bg-blue-500 rounded-full p-8 shadow-lg ${isRecording ? "animate-pulse" : ""
                }`}
            >
              <Mic size={48} className="text-white" />
            </div>

            <div className="text-3xl font-mono text-gray-700 font-bold tracking-wider">
              {time}
            </div>

            <div className="w-full max-w-sm">
              <canvas
                ref={canvasRef}
                width={200}
                height={50}
                className="w-full h-12 bg-gray-50 rounded-lg border"
              />
            </div>

            <div className="flex gap-4">
              <Button
                onClick={handleStartRecording}
                disabled={!isConnected || isRecording || isTranscriptionFinalizing}
                size="lg"
                className="bg-green-500 hover:bg-green-600"
              >
                <Play size={20} className="mr-2" />
                Start
              </Button>

              <Button
                onClick={handleStopRecording}
                disabled={!isRecording}
                size="lg"
                variant="destructive"
              >
                <Square size={20} className="mr-2" />
                Stop
              </Button>
            </div>

            {isRecording && (
              <div className="flex items-center gap-2 text-red-600">
                <div className="w-3 h-3 bg-red-500 rounded-full animate-pulse"></div>
                <span className="font-medium">Nagrywanie i streaming...</span>
              </div>
            )}
          </div>
        </Card>

        <Card className="relative flex-1 p-6 bg-white/90 shadow-xl">
          {isTranscriptionFinalizing ?
            <div className="absolute inset-0 bg-black/50 rounded-xl transition-opacity duration-300">
              <div className="flex flex-col items-center justify-center h-full gap-4">
                <svg aria-hidden="true" className="w-15 h-15 text-gray-400 animate-spin fill-brand" viewBox="0 0 100 101" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M100 50.5908C100 78.2051 77.6142 100.591 50 100.591C22.3858 100.591 0 78.2051 0 50.5908C0 22.9766 22.3858 0.59082 50 0.59082C77.6142 0.59082 100 22.9766 100 50.5908ZM9.08144 50.5908C9.08144 73.1895 27.4013 91.5094 50 91.5094C72.5987 91.5094 90.9186 73.1895 90.9186 50.5908C90.9186 27.9921 72.5987 9.67226 50 9.67226C27.4013 9.67226 9.08144 27.9921 9.08144 50.5908Z" fill="currentColor"/>
                  <path d="M93.9676 39.0409C96.393 38.4038 97.8624 35.9116 97.0079 33.5539C95.2932 28.8227 92.871 24.3692 89.8167 20.348C85.8452 15.1192 80.8826 10.7238 75.2124 7.41289C69.5422 4.10194 63.2754 1.94025 56.7698 1.05124C51.7666 0.367541 46.6976 0.446843 41.7345 1.27873C39.2613 1.69328 37.813 4.19778 38.4501 6.62326C39.0873 9.04874 41.5694 10.4717 44.0505 10.1071C47.8511 9.54855 51.7191 9.52689 55.5402 10.0491C60.8642 10.7766 65.9928 12.5457 70.6331 15.2552C75.2735 17.9648 79.3347 21.5619 82.5849 25.841C84.9175 28.9121 86.7997 32.2913 88.1811 35.8758C89.083 38.2158 91.5421 39.6781 93.9676 39.0409Z" fill="white"/>
                </svg>
                <p className="text-white text-lg">Poprawianie transkrypcji...</p>
              </div>
            </div> : null}
          <div className="space-y-4">
            <h3 className="text-xl font-semibold text-gray-800 mb-4">
              Dane pacjenta
            </h3>

            {/* Wskaźnik automatycznie wypełnionych danych */}
            {extractedData.fullName && (
              <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-lg">
                <h4 className="font-medium text-green-800 mb-2 flex items-center gap-2">
                  <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                  Dane automatycznie wyodrębnione z AI
                </h4>
                <div className="text-sm text-green-700 space-y-1">
                  {/*extractedData.organ && <p><strong>Narząd:</strong> {extractedData.organ}</p>*/}
                  {extractedData.fullName && <p><strong>Pacjent:</strong> {extractedData.fullName}</p>}
                  {extractedData.age && <p><strong>Wiek:</strong> {extractedData.age} lat</p>}
                  {extractedData.pesel && <p><strong>PESEL:</strong> {extractedData.pesel}</p>}
                </div>
              </div>
            )}

            {/*<div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Badany narząd
              </label>
              <input
                type="text"
                value={metadata.organ}
                onChange={(e) => updateField("organ", e.target.value)}
                className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="Nazwa narządu"
              />
            </div>*/}

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Imię i nazwisko
              </label>
              <input
                type="text"
                value={metadata.name}
                onChange={(e) => updateField("name", e.target.value)}

                className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="Imię i nazwisko pacjenta"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Wiek
                </label>
                <input
                  type="number"
                  value={metadata.age}
                  onChange={(e) => updateField("age", e.target.value)}
                  className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  placeholder="Wiek"
                  min="0"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  PESEL
                </label>
                <input
                  type="text"
                  value={metadata.pesel}
                  onChange={(e) => updateField("pesel", e.target.value)}
                  className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  placeholder="PESEL"
                  maxLength={11}
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Opis badania
              </label>
              <textarea
                value={metadata.description}
                onChange={(e) => updateField("description", e.target.value)}
                className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
                rows={6}
                placeholder="Transkrypcja pojawi się tutaj automatycznie podczas nagrywania..."
              />
            </div>

            <div className="flex gap-2 justify-end">
              <Button onClick={() => {
                clearDescriptionField();
                setExtractedData({});
              }} variant="outline">
                Wyczyść opis
              </Button>
              <Button className="bg-blue-500 hover:bg-blue-600">Zapisz</Button>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}
