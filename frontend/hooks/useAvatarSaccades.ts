import { useRef } from "react";
import * as THREE from "three";

export function useAvatarSaccades() {
  const saccadeTimerRef = useRef(0);
  const nextSaccadeRef = useRef(2.0);
  const targetSaccadeRef = useRef({ x: 0, y: 0 });
  const currentSaccadeRef = useRef({ x: 0, y: 0 });

  const updateSaccades = (safeDelta: number): { x: number; y: number } => {
    saccadeTimerRef.current += safeDelta;
    if (saccadeTimerRef.current >= nextSaccadeRef.current) {
      saccadeTimerRef.current = 0;
      nextSaccadeRef.current = Math.random() * 2.8 + 1.2;
      targetSaccadeRef.current = {
        x: (Math.random() - 0.5) * 0.022,
        y: (Math.random() - 0.5) * 0.015,
      };
    }
    currentSaccadeRef.current.x = THREE.MathUtils.lerp(
      currentSaccadeRef.current.x,
      targetSaccadeRef.current.x,
      Math.min(safeDelta * 9, 1.0)
    );
    currentSaccadeRef.current.y = THREE.MathUtils.lerp(
      currentSaccadeRef.current.y,
      targetSaccadeRef.current.y,
      Math.min(safeDelta * 9, 1.0)
    );
    return currentSaccadeRef.current;
  };

  return { updateSaccades };
}
