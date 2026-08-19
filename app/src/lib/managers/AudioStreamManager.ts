import { AUDIO_CONFIG, AUDIO_WORKLET_URL } from "@/config";
import { GenericManager } from "./GenericManager";
import { WavEncoder } from "../audio/WavEncoder";

export class AudioStreamManager extends EventTarget implements GenericManager {
    private stream: MediaStream | null = null;
    private audioContext: AudioContext | null = null;
    private wavEncoder: WavEncoder;
    private callbacks: Set<() => void> = new Set();

    public constructor() {
        super();

        this.wavEncoder = new WavEncoder(
            AUDIO_CONFIG.sampleRate,
            AUDIO_CONFIG.channelCount
        );
    }

    public startStream = async () => {
        if (this.stream) {
            console.warn("`startStream` called, but stream is already open!");
            return;
        }

        try {
            this.stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    sampleRate: { ideal: AUDIO_CONFIG.sampleRate },
                    channelCount: { exact: AUDIO_CONFIG.channelCount },
                    echoCancellation: { ideal: AUDIO_CONFIG.echoCancellation },
                    noiseSuppression: { ideal: AUDIO_CONFIG.noiseSuppression },
                },
            });
            await this.startProcessing(this.stream);
            this.emitChange();
            this.dispatchEvent(new CustomEvent('stream_open'));
        } catch (e) {
            console.log("Error occurred during creation of AudioStreamProcessor");
            await this.stopProcessing();
            await this.stopStream();
            this.emitChange();
            this.dispatchEvent(new CustomEvent('stream_error'));
        }
    }

    public stopStream = async () => {
        await this.stopProcessing();
        if (this.stream) {
            this.stream.getTracks().forEach(track => track.stop());
            this.stream = null;
        }
        this.dispatchEvent(new CustomEvent('stream_closed'));
        this.emitChange();
    }

    public subscribe = (callback: () => void) => {
        this.callbacks.add(callback);

        return () => this.callbacks.delete(callback);
    }

    public getSnapshot = () => {
        return this.stream;
    }

    private emitChange = () => {
        this.callbacks.forEach(callback => callback());
    }

    private startProcessing = async (stream: MediaStream): Promise<void> => {
        try {
            // Sprawdź czy browser obsługuje wymaganą częstotliwość próbkowania
            const constraints = stream.getTracks()[0].getSettings();
            console.log('Aktualne ustawienia audio:', constraints);

            this.audioContext = new AudioContext();
            const source = this.audioContext.createMediaStreamSource(stream);

            console.log('AudioContext sample rate:', this.audioContext.sampleRate);
            
            await this.audioContext.audioWorklet.addModule(AUDIO_WORKLET_URL);
            const worklet = new AudioWorkletNode(this.audioContext, 'base-processor', {
                numberOfInputs: 1,
                numberOfOutputs: 1,
                outputChannelCount: [1],
                processorOptions: {
                    outputSampleRate: AUDIO_CONFIG.sampleRate
                }
            });

            worklet.port.onmessage = event => {
                const resampledAudio = event.data as Float32Array;
                if (!(resampledAudio instanceof Float32Array)) {
                    throw new Error("Resampler returned an invalid audio buffer!");
                }

                const base64Data = this.wavEncoder.float32ArrayToBase64(resampledAudio);
                this.dispatchEvent(new CustomEvent('audio_data', { detail: base64Data }));
            };

            const muteNode = this.audioContext.createGain();
            muteNode.gain.value = 0;

            source.connect(worklet);
            worklet.connect(muteNode);
            muteNode.connect(this.audioContext.destination);

            console.log('✅ WAV Audio streaming rozpoczęty - częstotliwość:', this.audioContext.sampleRate, 'Hz');
        } catch (error) {
            console.error('Error starting audio processing:', error);
            throw error;
        }
    }

    private stopProcessing = async () => {
        // This instantly closes audio input so no processing should occur during cleanup.
        // Dereferencing happens after awaiting close status so GB should not interupt anything.
        if (this.audioContext) {
            await this.audioContext.close();
            this.audioContext = null;
        }
    
        console.log('🛑 WAV Audio streaming zakończony');
    }
}

export const audioStreamManager = new AudioStreamManager();