"use client";

/**
 * useLipSync.ts
 *
 * Natural, Graceful Human Speech & Lip-Sync Engine:
 * - Subtle, realistic mouth opening range (Max 0.22).
 * - Gentle syllable cadence articulation without grotesque over-opening.
 * - Smooth lerping for elegant, beautiful human talking expression.
 */

import { useRef, useCallback, useState } from "react";
import { VISEME_MAP, textToVisemeSequence, type VisemeName } from "@/lib/visemeMap";
import * as THREE from "three";

export interface LipSyncState {
  intensity: number;
  isSpeaking: boolean;
}

interface UseLipSyncOptions {
  meshesRef: React.RefObject<THREE.SkinnedMesh[]>;
}

// List of morph targets strictly dedicated to speech & mouth movements
const SPEECH_MORPH_TARGETS = new Set([
  "jawOpen",
  "mouthOpen",
  "mouthClose",
  "mouthFunnel",
  "mouthPucker",
  "mouthStretchLeft",
  "mouthStretchRight",
  "mouthLowerDownLeft",
  "mouthLowerDownRight",
  "mouthShrugUpper",
  "mouthShrugLower",
  "mouthRollLower",
  "mouthRollUpper",
]);

const GENTLE_PHONEMES: VisemeName[] = [
  "viseme_aa",
  "viseme_PP",
  "viseme_E",
  "viseme_DD",
  "viseme_O",
  "viseme_SS",
  "viseme_aa",
  "viseme_I",
  "viseme_RR",
  "viseme_U",
  "viseme_FF",
  "viseme_E",
];

export function useLipSync({ meshesRef }: UseLipSyncOptions) {
  const [isSpeaking, setIsSpeaking] = useState(false);
  const intensityRef = useRef(0);
  const targetMorphsRef = useRef<Record<string, number>>({});
  const currentMorphsRef = useRef<Record<string, number>>({});
  const visemeQueueRef = useRef<{ viseme: VisemeName; timeMs: number }[]>([]);
  const sessionStartRef = useRef<number>(0);
  const isSpeakingRef = useRef(false);
  const speechClockRef = useRef(0);

  const applyViseme = useCallback((viseme: VisemeName, intensityScale: number = 1) => {
    const entry = VISEME_MAP[viseme];
    if (!entry) return;

    const scale = Math.min(1.0, Math.max(0.3, intensityScale));
    for (const { name, weight } of entry.morphTargets) {
      if (SPEECH_MORPH_TARGETS.has(name)) {
        targetMorphsRef.current[name] = Math.min(weight * scale, 0.28);
      }
    }
  }, []);

  /**
   * Called each frame from Avatar3D useFrame.
   * Updates only speech/mouth morphs smoothly across all facial meshes.
   */
  const updateMorphTargets = useCallback((delta: number) => {
    const meshes = meshesRef.current;
    if (!meshes || meshes.length === 0) return;

    const safeDelta = Math.min(Math.max(delta, 0.0001), 0.033);
    const now = performance.now();
    const elapsed = sessionStartRef.current > 0 ? now - sessionStartRef.current : 0;
    const audioEnergy = intensityRef.current;

    // Process queued transcript visemes
    let hadQueuedViseme = false;
    while (visemeQueueRef.current.length > 0) {
      const nextViseme = visemeQueueRef.current[0];
      if (elapsed >= nextViseme.timeMs) {
        visemeQueueRef.current.shift();
        applyViseme(nextViseme.viseme, audioEnergy);
        hadQueuedViseme = true;
      } else {
        break;
      }
    }

    // Natural subtle conversational articulation while speaking
    if (audioEnergy > 0.02) {
      speechClockRef.current += safeDelta * (3.5 + audioEnergy * 1.5);
      const cadence = speechClockRef.current;

      if (!hadQueuedViseme) {
        const cycleIdx = Math.floor(cadence) % GENTLE_PHONEMES.length;
        applyViseme(GENTLE_PHONEMES[cycleIdx], audioEnergy);
      }

      // Gentle, subtle jaw movement (Strict ceiling max 0.20 - never wide open)
      const jawSyllablePulse = (Math.sin(cadence * Math.PI * 2) * 0.5 + 0.5);
      const targetJaw = Math.min(0.20, (audioEnergy * 0.14 + jawSyllablePulse * 0.08 * audioEnergy));

      targetMorphsRef.current["jawOpen"] = Math.max(targetMorphsRef.current["jawOpen"] ?? 0, targetJaw);
    } else {
      // Idle silence
      targetMorphsRef.current = {};
    }

    // Smoothly lerp current speech morphs toward target morphs
    const lerpSpeed = safeDelta * 14;
    for (const [morphName, targetVal] of Object.entries(targetMorphsRef.current)) {
      const current = currentMorphsRef.current[morphName] ?? 0;
      const newVal = THREE.MathUtils.lerp(current, targetVal, Math.min(lerpSpeed, 1));
      currentMorphsRef.current[morphName] = newVal;

      for (const mesh of meshes) {
        if (!mesh.morphTargetDictionary || !mesh.morphTargetInfluences) continue;
        const idx = mesh.morphTargetDictionary[morphName];
        if (idx !== undefined) {
          mesh.morphTargetInfluences[idx] = newVal;
        }
      }
    }

    // Decay unmentioned SPEECH morphs toward 0 smoothly
    for (const morphName of SPEECH_MORPH_TARGETS) {
      if (!(morphName in targetMorphsRef.current)) {
        const current = currentMorphsRef.current[morphName] ?? 0;
        if (current > 0.0001) {
          const newVal = THREE.MathUtils.lerp(current, 0, Math.min(lerpSpeed, 1));
          const finalVal = newVal < 0.001 ? 0 : newVal;
          currentMorphsRef.current[morphName] = finalVal;

          for (const mesh of meshes) {
            if (!mesh.morphTargetDictionary || !mesh.morphTargetInfluences) continue;
            const idx = mesh.morphTargetDictionary[morphName];
            if (idx !== undefined) {
              mesh.morphTargetInfluences[idx] = finalVal;
            }
          }
        }
      }
    }
  }, [meshesRef, applyViseme]);

  /** Set lip sync intensity from audio analysis (0-1 range) */
  const setAudioIntensity = useCallback((intensity: number) => {
    intensityRef.current = Math.min(intensity, 1.0);

    const speaking = intensity > 0.03;
    if (speaking !== isSpeakingRef.current) {
      isSpeakingRef.current = speaking;
      setIsSpeaking(speaking);
    }

    if (!speaking) {
      targetMorphsRef.current = {};
    }
  }, []);

  /** Queue transcript-based viseme sequence for lip-sync approximation */
  const queueTranscriptVisemes = useCallback((text: string, durationMs: number = 3000) => {
    sessionStartRef.current = performance.now();
    visemeQueueRef.current = textToVisemeSequence(text, durationMs);
  }, []);

  /** Reset all lip-sync state and immediately close mouth back to rest */
  const reset = useCallback(() => {
    visemeQueueRef.current = [];
    targetMorphsRef.current = {};
    currentMorphsRef.current = {};
    intensityRef.current = 0;
    isSpeakingRef.current = false;
    setIsSpeaking(false);

    // Immediately zero out all speech morph targets across all meshes
    const meshes = meshesRef.current;
    if (meshes) {
      for (const mesh of meshes) {
        if (!mesh.morphTargetDictionary || !mesh.morphTargetInfluences) continue;
        for (const morphName of SPEECH_MORPH_TARGETS) {
          const idx = mesh.morphTargetDictionary[morphName];
          if (idx !== undefined) {
            mesh.morphTargetInfluences[idx] = 0;
          }
        }
      }
    }
  }, [meshesRef]);

  return {
    isSpeaking,
    updateMorphTargets,
    setAudioIntensity,
    queueTranscriptVisemes,
    applyViseme,
    reset,
  };
}
