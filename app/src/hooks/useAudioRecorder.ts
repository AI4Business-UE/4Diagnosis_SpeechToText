import { useState, useRef, useCallback, useEffect } from 'react';
import { AudioStreamProcessor, createStopRecordingMessage, createRecordingEndMessage, checkWAVSupport } from '@/lib/audioUtils_fixed';
import { WAVStreamingMonitor, validateWAVStreamingSupport, logStreamingStats, DEFAULT_STREAMING_CONFIG } from '@/lib/wavStreamingUtils';

interface AudioRecorderConfig {
    websocketUrl?: string;
    chunkInterval?: number; // w milisekundach
}

interface AudioRecorderState {
    isRecording: boolean;
    isPaused: boolean;
    transcript: string;
    interimTranscript: string;
    isConnected: boolean;
    error: string | null;
    recordingTime: number;
    extractedData: {
        organ: string;
        fullName: string;
        age: number;
        pesel: string;
    } | null;
}

export const useAudioRecorder = (config: AudioRecorderConfig = {}) => {
    const {
        websocketUrl = 'ws://localhost:8010/ws/audio/',
        chunkInterval = 250
    } = config;

    // State
    const [state, setState] = useState<AudioRecorderState>({
        isRecording: false,
        isPaused: false,
        transcript: '',
        interimTranscript: '',
        isConnected: false,
        error: null,
        recordingTime: 0,
        extractedData: null
    });    // Refs
    const wsRef = useRef<WebSocket | null>(null);
    const mediaRecorderRef = useRef<MediaRecorder | null>(null);
    const streamRef = useRef<MediaStream | null>(null);
    const timerRef = useRef<any>(null);
    const audioChunksRef = useRef<Blob[]>([]);
    const audioProcessorRef = useRef<AudioStreamProcessor | null>(null);
    const wavMonitorRef = useRef<WAVStreamingMonitor | null>(null);

    // Funkcja kodowania audio do base64 (nie jest już używana dla WAV streamingu)
    const blobToBase64 = useCallback((blob: Blob): Promise<string> => {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => {
                const result = reader.result as string;
                // Usuń prefix "data:audio/wav;base64," jeśli istnieje
                const base64 = result.split(',')[1] || result;
                resolve(base64);
            };
            reader.onerror = reject;
            reader.readAsDataURL(blob);
        });
    }, []);

    // Inicjalizacja WebSocket
    const initializeWebSocket = useCallback(() => {
        try {
            const ws = new WebSocket(websocketUrl);

            ws.onopen = () => {
                console.log('WebSocket połączony');
                setState(prev => ({ ...prev, isConnected: true, error: null }));
            };

            ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    console.log('🔍 Received WebSocket message:', data); // Dodane logowanie

                    if (data.type === 'transcript') {

    setState(prev => ({
        ...prev,
        transcript: data.text || data.transcription || '', // Najpierw sprawdź text, potem transcription
        interimTranscript: data.interim || data.interim_transcript || '' // Najpierw sprawdź interim, potem interim_transcript
    }));
} else if (data.type === 'error') {
                        setState(prev => ({ ...prev, error: data.message }));
                    }
                } catch (error) {
                    console.error('Błąd parsowania wiadomości WebSocket:', error);
                }
            };

            ws.onclose = () => {
                console.log('WebSocket rozłączony');
                setState(prev => ({ ...prev, isConnected: false }));
            };

            ws.onerror = (error) => {
                console.error('Błąd WebSocket:', error);
                setState(prev => ({
                    ...prev,
                    isConnected: false,
                    error: 'Błąd połączenia WebSocket'
                }));
            };

            wsRef.current = ws;
        } catch (error) {
            console.error('Błąd inicjalizacji WebSocket:', error);
            setState(prev => ({
                ...prev,
                error: 'Nie można nawiązać połączenia WebSocket'
            }));
        }
    }, [websocketUrl]);

    // Zamknięcie WebSocket
    const closeWebSocket = useCallback(() => {
        if (wsRef.current) {
            wsRef.current.close();
            wsRef.current = null;
        }
    }, []);

    // Timer nagrywania
    const startTimer = useCallback(() => {
        if (timerRef.current) {
            clearInterval(timerRef.current);
        }

        let seconds = 0;
        timerRef.current = setInterval(() => {
            seconds++;
            setState(prev => ({ ...prev, recordingTime: seconds }));
        }, 1000);
    }, []);

    const stopTimer = useCallback(() => {
        if (timerRef.current) {
            clearInterval(timerRef.current);
            timerRef.current = null;
        }
    }, []);    // Rozpoczęcie nagrywania
    const startRecording = useCallback(async () => {
        try {
            // Reset stanu
            setState(prev => ({
                ...prev,
                transcript: '',
                interimTranscript: '',
                error: null,
                recordingTime: 0,
                extractedData: null
            }));

            // Reset audio chunks
            audioChunksRef.current = [];

            // Inicjalizuj WebSocket
            initializeWebSocket();

            // Uzyskaj dostęp do mikrofonu
            const stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true,
                    sampleRate: 16000,  // Preferowana częstotliwość próbkowania dla WAV
                    channelCount: 1     // Mono audio
                }
            });
            streamRef.current = stream;            // Tylko WAV streaming
            console.log('Używam WAV streamingu');
            
            // Sprawdź wsparcie dla WAV streamingu
            const supportCheck = validateWAVStreamingSupport();
            if (!supportCheck.supported) {
                console.warn('WAV streaming issues:', supportCheck.issues);
            }
            
            // Inicjalizuj monitor
            const monitor = new WAVStreamingMonitor();
            wavMonitorRef.current = monitor;
            monitor.start();
            
            // Użyj WAV streamingu
            const processor = new AudioStreamProcessor(
                (base64WavData) => {
                    if (wsRef.current?.readyState === WebSocket.OPEN) {
                        try {
                            // Zapisz statystyki
                            const chunkSize = Math.ceil(base64WavData.length * 0.75); // Przybliżony rozmiar po dekodowaniu base64
                            monitor.recordChunk(chunkSize);
                            
                            wsRef.current.send(JSON.stringify({
                                type: 'audio_chunk',
                                data: base64WavData,
                                timestamp: Date.now(),
                                format: 'wav'
                            }));
                            
                            // Loguj statystyki co 10 sekund
                            const stats = monitor.getStats();
                            if (stats.chunksSent % 40 === 0) { // Co ~10 sekund przy 250ms chunks
                                logStreamingStats(monitor);
                            }
                        } catch (error) {
                            console.error('Błąd wysyłania WAV chunk:', error);
                        }
                    }
                },
                DEFAULT_STREAMING_CONFIG.sampleRate
            );

            await processor.startProcessing(stream);
            audioProcessorRef.current = processor;

            // Uruchom timer
            startTimer();

            setState(prev => ({
                ...prev,
                isRecording: true,
                isPaused: false
            }));

        } catch (error) {
            console.error('Błąd rozpoczynania nagrywania:', error);
            setState(prev => ({
                ...prev,
                error: 'Nie można uzyskać dostępu do mikrofonu'
            }));
        }
    }, [initializeWebSocket, chunkInterval, startTimer]);    // Zatrzymanie nagrywania
    const stopRecording = useCallback(() => {
        // Get any metadata to send with recording end
        const metadata = {
            organ: '',
            name: '',
            age: '',
            pesel: '',
            description: ''
        };
        
        // Wyślij sygnał stop_recording do backend przez WebSocket
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            try {
                // Send both messages to ensure backend catches at least one
                wsRef.current.send(JSON.stringify(createStopRecordingMessage()));
                console.log('Wysłano sygnał stop_recording do serwera');
                
                // Also send recording_end message
                if (typeof createRecordingEndMessage === 'function') {
                    wsRef.current.send(JSON.stringify(createRecordingEndMessage(metadata)));
                    console.log('Wysłano sygnał recording_end do serwera');
                }
            } catch (error) {
                console.error('Błąd wysyłania sygnału zatrzymania nagrywania:', error);
            }
        }        // Zatrzymaj audio processor (WAV streaming)
        if (audioProcessorRef.current) {
            audioProcessorRef.current.stopProcessing();
            audioProcessorRef.current = null;
            console.log('Zatrzymano WAV processor');
        }

        // Zatrzymaj i zresetuj monitor
        if (wavMonitorRef.current) {
            logStreamingStats(wavMonitorRef.current);
            wavMonitorRef.current.reset();
            wavMonitorRef.current = null;
            console.log('Zatrzymano WAV monitor');
        }

        // Zatrzymaj MediaRecorder (nie używany już)
        // mediaRecorderRef nie jest używany przy WAV streaming

        // Zatrzymaj stream
        if (streamRef.current) {
            streamRef.current.getTracks().forEach(track => track.stop());
            streamRef.current = null;
        }

        // Zamknij WebSocket
        closeWebSocket();

        // Zatrzymaj timer
        stopTimer();

        setState(prev => ({
            ...prev,
            isRecording: false,
            isPaused: false
        }));
    }, [closeWebSocket, stopTimer]);

    // Pauzowanie nagrywania (nie obsługiwane dla WAV streaming)
    const pauseRecording = useCallback(() => {
        console.warn('Pause nie jest obsługiwane dla WAV streaming');
    }, []);

    // Wznowienie nagrywania (nie obsługiwane dla WAV streaming)  
    const resumeRecording = useCallback(() => {
        console.warn('Resume nie jest obsługiwane dla WAV streaming');
    }, []);

    // Czyszczenie zasobów przy unmount
    useEffect(() => {
        return () => {
            stopRecording();
        };
    }, [stopRecording]);

    return {
        // State
        ...state,

        // Actions
        startRecording,
        stopRecording,
        pauseRecording,
        resumeRecording,

        // Helpers
        clearTranscript: useCallback(() => {
            setState(prev => ({
                ...prev,
                transcript: '',
                interimTranscript: '',
                extractedData: null
            }));
        }, []),

        clearError: useCallback(() => {
            setState(prev => ({ ...prev, error: null }));
        }, []),

        // WAV streaming monitor for stats display
        wavMonitor: wavMonitorRef.current
    };
};
