import { useRef } from "react";
import useVisualizer from "../hooks/useVisualizer";

export default function AudioVisualizer() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  useVisualizer({ canvasRef });

  return (
    <canvas
        ref={canvasRef}
        width={200}
        height={50}
        className="w-full h-12 bg-gray-50 rounded-lg border"
    />
  );
}