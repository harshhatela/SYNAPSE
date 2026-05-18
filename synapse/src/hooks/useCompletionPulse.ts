import { useCallback, useRef, useState } from 'react';

export function useCompletionPulse(durationMs = 600): {
  isPulsing: boolean;
  pulse: () => void;
} {
  const [isPulsing, setIsPulsing] = useState(false);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const pulse = useCallback(() => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    setIsPulsing(false);
    // Re-enable on the next tick so the class actually re-applies.
    requestAnimationFrame(() => {
      setIsPulsing(true);
      timeoutRef.current = setTimeout(() => setIsPulsing(false), durationMs);
    });
  }, [durationMs]);

  return { isPulsing, pulse };
}
