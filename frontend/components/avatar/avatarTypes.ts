import * as THREE from "three";
import type { AvatarEmotion, AvatarGestureType } from "@/lib/sentimentAnalyzer";

export interface Avatar3DProps {
  url: string;
  idleAnimationUrl?: string;
  talkingAnimationUrl?: string;
  isSpeaking: boolean;
  audioIntensity: number;
  onLoad?: () => void;
  onDanceStart?: () => void;
  onDanceEnd?: () => void;
  backendEmotion?: string;
  backendGesture?: string;
  isVoiceMode?: boolean;
}

export interface Avatar3DHandle {
  setAudioIntensity: (intensity: number) => void;
  resetLipSync: () => void;
  queueTranscriptVisemes: (text: string, durationMs?: number) => void;
  triggerTextMotion: (text: string) => void;
  setEmotion: (emotion: AvatarEmotion) => void;
  triggerGesture: (gesture: AvatarGestureType, durationMs?: number) => void;
  applyBackendEmotion: (emotion: string, gesture: string) => void;
  stopDance: () => void;
  playAnimation: (name: "idle" | "angry" | "laugh" | string, duration?: number) => void;
  registerClips: (clips: THREE.AnimationClip[], autoPlayPrefix?: string) => void;
}

export interface BoneMap {
  head?: THREE.Bone;
  neck?: THREE.Bone;
  spine?: THREE.Bone;
  spine1?: THREE.Bone;
  spine2?: THREE.Bone;
  hips?: THREE.Bone;
  leftShoulder?: THREE.Bone;
  rightShoulder?: THREE.Bone;
  leftArm?: THREE.Bone;
  rightArm?: THREE.Bone;
  leftForeArm?: THREE.Bone;
  rightForeArm?: THREE.Bone;
  leftHand?: THREE.Bone;
  rightHand?: THREE.Bone;
  leftFingers: THREE.Bone[];
  rightFingers: THREE.Bone[];
}

export interface CachedMorphMesh {
  mesh: THREE.SkinnedMesh;
  influences: number[];
  dict: Record<string, number>;
  blinkL?: number;
  blinkR?: number;
  eyesClosed?: number;
  eyeLookUpLeft?: number;
  eyeLookDownLeft?: number;
  eyeLookUpRight?: number;
  eyeLookDownRight?: number;
  eyeLookInLeft?: number;
  eyeLookOutLeft?: number;
  eyeLookInRight?: number;
  eyeLookOutRight?: number;
}

// ─────────────────────────────────────────────────────────────────────────────
// Animation & Procedural Constants
// ─────────────────────────────────────────────────────────────────────────────

export const BLINK_CLOSE_DURATION = 0.1;
export const BLINK_HOLD_DURATION = 0.03;
export const BLINK_OPEN_DURATION = 0.14;
export const BLINK_INTERVAL_MIN = 2.0;
export const BLINK_INTERVAL_MAX = 4.5;

export const BREATH_SPINE_AMP = 0.007;
export const BREATH_SHOULDER_AMP = 0.004;
export const BREATH_RATE = 0.25;
export const CROSSFADE_DURATION = 0.4;

export const _qGaze = new THREE.Quaternion();
export const _eGaze = new THREE.Euler(0, 0, 0, "YXZ");
export const _qNeckGaze = new THREE.Quaternion();
export const _eNeckGaze = new THREE.Euler(0, 0, 0, "YXZ");

/** Strip Mixamo "mixamorig" prefix from track names so clips match Avaturn rig */
export function retargetClips(clips: THREE.AnimationClip[], prefix: string): THREE.AnimationClip[] {
  return (clips ?? []).map((clip) => {
    const r = clip.clone();
    r.name = `${prefix}${clip.name}`;
    r.tracks = r.tracks.map((track) => {
      const f = track.clone();
      f.name = f.name
        .replace(/mixamorig[:/]?/gi, "")
        .replace(/^([A-Za-z])/, (_, c: string) => c.toUpperCase());
      return f;
    });
    return r;
  });
}
