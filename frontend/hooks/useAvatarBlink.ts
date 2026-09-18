import { useRef } from "react";
import * as THREE from "three";

export const BLINK_INTERVAL_MIN = 2.0;
export const BLINK_INTERVAL_MAX = 4.5;
export const BLINK_CLOSE_DURATION = 0.10;
export const BLINK_HOLD_DURATION = 0.03;
export const BLINK_OPEN_DURATION = 0.14;

export function useAvatarBlink() {
  const blinkPhaseRef = useRef<0 | 1 | 2 | 3>(0);
  const blinkPhaseTimerRef = useRef(0);
  const blinkIdleTimerRef = useRef(0);
  const nextBlinkWaitRef = useRef(
    Math.random() * (BLINK_INTERVAL_MAX - BLINK_INTERVAL_MIN) + BLINK_INTERVAL_MIN
  );
  const blinkInfluenceRef = useRef(0);

  const updateBlink = (safeDelta: number): number => {
    blinkPhaseTimerRef.current += safeDelta;
    switch (blinkPhaseRef.current) {
      case 0:
        blinkIdleTimerRef.current += safeDelta;
        if (blinkIdleTimerRef.current >= nextBlinkWaitRef.current) {
          blinkIdleTimerRef.current = 0;
          nextBlinkWaitRef.current =
            Math.random() * (BLINK_INTERVAL_MAX - BLINK_INTERVAL_MIN) + BLINK_INTERVAL_MIN;
          blinkPhaseRef.current = 1;
          blinkPhaseTimerRef.current = 0;
        }
        blinkInfluenceRef.current = THREE.MathUtils.lerp(
          blinkInfluenceRef.current,
          0,
          Math.min(safeDelta * 20, 1.0)
        );
        break;
      case 1: {
        const progress = Math.min(1.0, blinkPhaseTimerRef.current / BLINK_CLOSE_DURATION);
        blinkInfluenceRef.current = Math.sin(progress * (Math.PI / 2));
        if (progress >= 1.0) {
          blinkPhaseRef.current = 2;
          blinkPhaseTimerRef.current = 0;
        }
        break;
      }
      case 2:
        blinkInfluenceRef.current = 1.0;
        if (blinkPhaseTimerRef.current >= BLINK_HOLD_DURATION) {
          blinkPhaseRef.current = 3;
          blinkPhaseTimerRef.current = 0;
        }
        break;
      case 3: {
        const progress = Math.min(1.0, blinkPhaseTimerRef.current / BLINK_OPEN_DURATION);
        blinkInfluenceRef.current = Math.cos(progress * (Math.PI / 2));
        if (progress >= 1.0) {
          blinkInfluenceRef.current = 0;
          blinkPhaseRef.current = 0;
          blinkPhaseTimerRef.current = 0;
          blinkIdleTimerRef.current = 0;
        }
        break;
      }
    }
    return blinkInfluenceRef.current;
  };

  return { updateBlink };
}
