import { formatTime } from "./utils";

export const createTimerUtilities = () => {
  const startTimer = (onTick: (time: string) => void): NodeJS.Timeout => {
    let seconds = 0;
    return setInterval(() => {
      seconds++;
      onTick(formatTime(seconds));
    }, 1000);
  };

  const stopTimer = (intervalId: NodeJS.Timeout | null): void => {
    if (intervalId) {
      clearInterval(intervalId);
    }
  };

  return { startTimer, stopTimer };
};
