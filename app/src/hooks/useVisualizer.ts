import { AudioStreamProcessor } from "@/lib/audio/AudioStreamProcessor";
import { audioStreamManager } from "@/lib/managers/AudioStreamManager";
import React, { useEffect, useSyncExternalStore } from "react";

export default function useVisualizer(
    { canvasRef }: { canvasRef: React.RefObject<HTMLCanvasElement | null> }
) {
    const stream = useSyncExternalStore(audioStreamManager.subscribe, audioStreamManager.getSnapshot);

    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas || !stream) return;
        
        const ctx = canvas.getContext("2d");
        if (!ctx) return;
    
        const audioCtx = new AudioContext();
        const analyser = audioCtx.createAnalyser();
        const source = audioCtx.createMediaStreamSource(stream);

        source.connect(analyser);
        analyser.fftSize = 64;

        const dataArray = new Uint8Array(analyser.frequencyBinCount);

        let rafId: number;
        const draw = () => {
            if (canvas) {
                analyser.getByteFrequencyData(dataArray);

                ctx.clearRect(0, 0, 200, 50);
                ctx.fillStyle = "#3b82f6";

                const barWidth = 200 / dataArray.length;
                let x = 0;

                for (let i = 0; i < dataArray.length; i++) {
                    const barHeight = (dataArray[i] / 255) * 40;
                    ctx.fillRect(x, 50 - barHeight, barWidth - 1, barHeight);
                    x += barWidth;
                }

                rafId = requestAnimationFrame(draw);
            } 
        };

        draw();

        return () => {
            cancelAnimationFrame(rafId);
            ctx.clearRect(0, 0, 200, 50);
            audioCtx.close();
        };
    }, [canvasRef.current, stream]);
}