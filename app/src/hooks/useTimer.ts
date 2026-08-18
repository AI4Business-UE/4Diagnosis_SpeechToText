import { useCallback, useEffect, useRef, useState } from "react";
import { formatTime } from "../utils/time";

export default function useTimer() {
    const intervalRef = useRef<NodeJS.Timeout | null>(null);
    const [timerState, setTimerState] = useState<string>("00:00");
    const startTimer = useCallback(() => {
        if (intervalRef.current) {
            return; 
        }

        let seconds = 0;
        const intervalId = setInterval(() => {
            seconds++;
            setTimerState(formatTime(seconds));
        }, 1000);

        intervalRef.current = intervalId;
    }, []);

  const stopTimer = useCallback(() => {
    if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
    }
    setTimerState("00:00");
  }, []);

  useEffect(() => {
    return () => {
        if (intervalRef.current) {
            clearInterval(intervalRef.current);
        }
    }
  }, []);

  return { timerState, startTimer, stopTimer };
};