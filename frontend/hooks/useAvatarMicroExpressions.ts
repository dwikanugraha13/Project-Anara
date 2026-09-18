import { useRef } from "react";
import * as THREE from "three";

export const MICRO_EXPR_POOL: Array<Record<string, number>> = [
  { browInnerUp: 0.10, browDownLeft: 0.06 },
  { mouthSmileLeft: 0.14, cheekSquintLeft: 0.10 },
  { mouthSmileRight: 0.14, cheekSquintRight: 0.10 },
  { browInnerUp: 0.12, browOuterUpLeft: 0.09, browOuterUpRight: 0.09 },
  { noseSneerLeft: 0.06 },
  { mouthPressLeft: 0.07, mouthPressRight: 0.07 },
  { cheekSquintLeft: 0.12, cheekSquintRight: 0.10 },
  { mouthDimpleLeft: 0.10 },
  { mouthDimpleRight: 0.10 },
  {},
  {},
  {},
];

const ALL_MICRO_KEYS = [
  "browInnerUp",
  "browDownLeft",
  "browOuterUpLeft",
  "browOuterUpRight",
  "mouthSmileLeft",
  "mouthSmileRight",
  "cheekSquintLeft",
  "cheekSquintRight",
  "noseSneerLeft",
  "mouthPressLeft",
  "mouthPressRight",
  "mouthDimpleLeft",
  "mouthDimpleRight",
] as const;

export function useAvatarMicroExpressions() {
  const timerRef = useRef(0);
  const nextChangeRef = useRef(3.0 + Math.random() * 4.0);
  const targetRef = useRef<Record<string, number>>({});
  const currentRef = useRef<Record<string, number>>({
    browInnerUp: 0,
    browDownLeft: 0,
    browOuterUpLeft: 0,
    browOuterUpRight: 0,
    mouthSmileLeft: 0,
    mouthSmileRight: 0,
    cheekSquintLeft: 0,
    cheekSquintRight: 0,
    noseSneerLeft: 0,
    mouthPressLeft: 0,
    mouthPressRight: 0,
    mouthDimpleLeft: 0,
    mouthDimpleRight: 0,
  });

  const updateMicroExpressions = (safeDelta: number): Record<string, number> => {
    timerRef.current += safeDelta;
    if (timerRef.current >= nextChangeRef.current) {
      timerRef.current = 0;
      nextChangeRef.current = 2.5 + Math.random() * 4.5;
      const pick = MICRO_EXPR_POOL[Math.floor(Math.random() * MICRO_EXPR_POOL.length)];
      targetRef.current = pick;
    }

    const lerpSpeed = Math.min(safeDelta * 3.0, 1.0);
    const cur = currentRef.current;
    const tgt = targetRef.current;

    for (let i = 0; i < ALL_MICRO_KEYS.length; i++) {
      const k = ALL_MICRO_KEYS[i];
      const c = cur[k] ?? 0;
      const t = tgt[k] ?? 0;
      cur[k] = THREE.MathUtils.lerp(c, t, lerpSpeed);
    }
    return cur;
  };

  return { updateMicroExpressions };
}
