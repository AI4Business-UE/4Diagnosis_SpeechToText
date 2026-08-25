import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Mic, Play, Square, Wifi, WifiOff } from "lucide-react";
import SpinnerLoader from "@/components/ui/SpinnerLoader";
import TextareaAutosize from 'react-textarea-autosize';

import AudioVisualizer from "../../components/AudioVisualizer";
import useRecordingState from "../../hooks/useRecordingState";
import usePatientMetadata from "@/hooks/usePatientMetadata";
import ConnectionControl from "@/components/ui/ConnectionControl";

export default function Recorder() { 
  const { 
    timer,
    connectionState,
    recordingState,
    metadata,
    handleConnect, 
    handleDisconnect, 
    startRecording, 
    finalizeTranscription,
    handleFieldUpdate
  } = useRecordingState();

  const time = timer.timerState;
  const patientMetadata = metadata;

  return (
    <div className="bg-gradient-to-br from-blue-50 to-indigo-100 flex flex-col items-center justify-center p-4 min-h-screen w-full">
      <div className="mb-6 p-4 bg-white/90 rounded-lg shadow-md">
        <div className="flex items-center gap-3">
          <ConnectionControl 
            connectionState={connectionState} 
            onConnect={handleConnect}
            onDisconnect={handleDisconnect}
          />
        </div>
      </div>

      <div className="flex flex-col lg:flex-row gap-8 w-full max-w-6xl">
        <Card className="flex-1 p-8 bg-white/90 shadow-xl">
          <div className="flex flex-col items-center gap-6">
            <div
              className={`bg-blue-500 rounded-full p-8 shadow-lg ${recordingState === 'recording' ? "animate-pulse" : ""
                }`}
            >
              <Mic size={48} className="text-white" />
            </div>

            <div className="text-3xl font-mono text-gray-700 font-bold tracking-wider">
              {time}
            </div>

            <div className="w-full max-w-sm">
              <AudioVisualizer />
            </div>

            <div className="flex gap-4">
              <Button
                onClick={startRecording}
                disabled={connectionState !== 'connected' || recordingState !== 'idle'}
                size="lg"
                className="bg-green-500 hover:bg-green-600"
              >
                <Play size={20} className="mr-2" />
                Start
              </Button>

              <Button
                onClick={finalizeTranscription}
                disabled={recordingState !== 'recording'}
                size="lg"
                variant="destructive"
              >
                <Square size={20} className="mr-2" />
                Stop
              </Button>
            </div>

            {recordingState === 'recording' && (
              <div className="flex items-center gap-2 text-red-600">
                <div className="w-3 h-3 bg-red-500 rounded-full animate-pulse"></div>
                <span className="font-medium">Nagrywanie i streaming...</span>
              </div>
            )}
          </div>
        </Card>

        <Card className="relative flex-1 p-6 bg-white/90 shadow-xl">
          {recordingState === 'finalizing' && connectionState === 'connected' ?
            <div className="absolute inset-0 bg-black/50 rounded-xl transition-opacity duration-300">
              <div className="flex flex-col items-center justify-center h-full gap-4">
                <SpinnerLoader />
                <p className="text-white text-lg">Poprawianie transkrypcji...</p>
              </div>
            </div> : null}
          <div className="space-y-4">
            <h3 className="text-xl font-semibold text-gray-800 mb-4">
              Dane pacjenta
            </h3>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Badany narząd
              </label>
              <TextareaAutosize
                value={patientMetadata.organ}
                onChange={(e) => handleFieldUpdate("organ", e.target.value)}
                className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
                minRows={1}
                placeholder="Nazwa narządu"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Imię i nazwisko
              </label>
              <input
                type="text"
                value={patientMetadata.name}
                onChange={(e) => handleFieldUpdate("name", e.target.value)}

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
                  value={patientMetadata.age}
                  onChange={(e) => handleFieldUpdate("age", e.target.value)}
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
                  value={patientMetadata.pesel}
                  onChange={(e) => handleFieldUpdate("pesel", e.target.value)}
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
                value={patientMetadata.description}
                onChange={(e) => handleFieldUpdate("description", e.target.value)}
                className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
                rows={6}
                placeholder="Transkrypcja pojawi się tutaj automatycznie podczas nagrywania..."
              />
            </div>

            <div className="flex gap-2 justify-end">
              <Button onClick={() => {
                handleFieldUpdate("description", "");
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
