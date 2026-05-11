export const createAudioVisualizer = () => {
  const setupVisualizer = (
    stream: MediaStream,
    canvas: HTMLCanvasElement,
    onFrame: () => void
  ): (() => void) => {
    const audioCtx = new AudioContext();
    const analyser = audioCtx.createAnalyser();
    const source = audioCtx.createMediaStreamSource(stream);

    source.connect(analyser);
    analyser.fftSize = 64;

    const dataArray = new Uint8Array(analyser.frequencyBinCount);

    const draw = () => {
      analyser.getByteFrequencyData(dataArray);
      const ctx = canvas.getContext("2d");
      if (!ctx) return;

      ctx.clearRect(0, 0, 200, 50);
      ctx.fillStyle = "#3b82f6";

      const barWidth = 200 / dataArray.length;
      let x = 0;

      for (let i = 0; i < dataArray.length; i++) {
        const barHeight = (dataArray[i] / 255) * 40;
        ctx.fillRect(x, 50 - barHeight, barWidth - 1, barHeight);
        x += barWidth;
      }

      onFrame();
    };

    const animate = () => {
      draw();
      requestAnimationFrame(animate);
    };

    animate();

    return () => {
      audioCtx.close();
    };
  };

  const clearCanvas = (canvas: HTMLCanvasElement | null): void => {
    if (canvas) {
      const ctx = canvas.getContext("2d");
      if (ctx) ctx.clearRect(0, 0, 200, 50);
    }
  };

  return { setupVisualizer, clearCanvas };
};
