"use client";

/**
 * Avatar3D.tsx
 *
 * Avaturn Photorealistic Humanoid Engine:
 * - Rich Emotional Facial Expressions (Happy, Shy/Blush, Curious, Think, Empathy, Joy).
 * - Ultra-Luwes & Organic Conversational Hand & Body Kinematics (Elliptical speech gesture arcs, wrist lag).
 * - Photorealistic Speech Articulation (Continuous phonetic co-articulation, jaw and cheek prosody).
 * - Natural Ngapurancang Adat Jawa rest posture in front of lower abdomen.
 * - 72 ARKit + Oculus Viseme Morph Targets.
 */

import React, {
  useRef,
  useEffect,
  useState,
  useCallback,
  useMemo,
  forwardRef,
  useImperativeHandle,
} from "react";
import { useGLTF, useAnimations } from "@react-three/drei";
import { useFrame, useThree } from "@react-three/fiber";
import * as THREE from "three";
import { useLipSync } from "@/hooks/useLipSync";
import { useAvatarBlink } from "@/hooks/useAvatarBlink";
import { useAvatarSaccades } from "@/hooks/useAvatarSaccades";
import { useAvatarMicroExpressions } from "@/hooks/useAvatarMicroExpressions";
import { useAvatarGestures } from "@/hooks/useAvatarGestures";
import {
  analyzeSpeechSentiment,
  type AvatarEmotion,
  type AvatarGestureType,
} from "@/lib/sentimentAnalyzer";

// ─────────────────────────────────────────────────────────────────────────────
// Types & Interfaces
// ─────────────────────────────────────────────────────────────────────────────

interface Avatar3DProps {
  url: string;
  idleAnimationUrl?: string;
  talkingAnimationUrl?: string;
  isSpeaking: boolean;
  audioIntensity: number;
  onLoad?: () => void;
  /** Called when Rumba dance animation starts */
  onDanceStart?: () => void;
  /** Called when Rumba dance animation finishes — lets page.tsx clear any queued audio */
  onDanceEnd?: () => void;
  /** Emotion pushed from backend emotion engine */
  backendEmotion?: string;
  /** Gesture pushed from backend emotion engine */
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
  /** Apply emotion + gesture received from backend WebSocket */
  applyBackendEmotion: (emotion: string, gesture: string) => void;
  /** Smoothly stop dance and crossfade back to conversation */
  stopDance: () => void;
  /**
   * playAnimation — crossfade to any named animation.
   * name: 'idle' | 'angry' | 'laugh' (or full clip key like 'idle_ext_...')
   * duration: crossfade duration in seconds (default 0.4)
   */
  playAnimation: (name: "idle" | "angry" | "laugh" | string, duration?: number) => void;
  /**
   * registerClips — called by external animation loaders (IdleLayer etc.)
   * to inject retargeted clips into the avatar's mixer.
   * autoPlayPrefix: if set and no animation is currently playing, auto-plays
   * the first clip matching that prefix.
   */
  registerClips: (clips: THREE.AnimationClip[], autoPlayPrefix?: string) => void;
}

interface BoneMap {
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

// ─────────────────────────────────────────────────────────────────────────────
// Constants
// ─────────────────────────────────────────────────────────────────────────────

const BLINK_CLOSE_DURATION = 0.10;
const BLINK_HOLD_DURATION = 0.03;
const BLINK_OPEN_DURATION = 0.14;
const BLINK_INTERVAL_MIN = 2.0;
const BLINK_INTERVAL_MAX = 4.5;

const BREATH_SPINE_AMP = 0.007;
const BREATH_SHOULDER_AMP = 0.004;
const BREATH_RATE = 0.25;
const CROSSFADE_DURATION = 0.4;

// Reusable Quaternions for zero-allocation additive head gaze tracking
const _qGaze = new THREE.Quaternion();
const _eGaze = new THREE.Euler(0, 0, 0, "YXZ");
const _qNeckGaze = new THREE.Quaternion();
const _eNeckGaze = new THREE.Euler(0, 0, 0, "YXZ");

// ─────────────────────────────────────────────────────────────────────────────
// Animation Utilities — External GLB Loader (Safe, per-file Suspense)
// ─────────────────────────────────────────────────────────────────────────────

/** Strip Mixamo "mixamorig" prefix from track names so clips match Avaturn rig */
function retargetClips(clips: THREE.AnimationClip[], prefix: string): THREE.AnimationClip[] {
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

// ─────────────────────────────────────────────────────────────────────────────
// Component
// ─────────────────────────────────────────────────────────────────────────────

interface CachedMorphMesh {
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

const Avatar3D = forwardRef<Avatar3DHandle, Avatar3DProps>(
  ({ url, idleAnimationUrl, talkingAnimationUrl, isSpeaking, audioIntensity, onLoad, onDanceStart, onDanceEnd, backendEmotion, backendGesture, isVoiceMode = true }, ref) => {
    const group = useRef<THREE.Group>(null!);
    const morphMeshesRef = useRef<THREE.SkinnedMesh[]>([]);
    const cachedMorphMeshesRef = useRef<CachedMorphMesh[]>([]);
    const frameThrottleRef = useRef(0);

    // Load avatar model and lightweight GLTF animations (false = no external Draco CDN download needed)
    const { scene, animations: gltfAnimations } = useGLTF(url, false);
    const { animations: externalAnimations } = useGLTF('/animations.glb', false);
    const dancePhaseRef = useRef<"idle" | "awaiting_intro" | "speaking_intro" | "dancing">("idle");
    const isDancingRef = useRef(false);
    const danceSafetyTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    // Clean animations: Use built-in Idle animation from avatar.glb & Talking_0 + Emotion + HipHopDancing from animations.glb
    const cleanAnimations = useMemo(() => {
      const anims: THREE.AnimationClip[] = [];

      // 1. ONLY use Built-in Animation (Internal avatar.glb) for Idle
      if (gltfAnimations && gltfAnimations.length > 0) {
        const builtinIdle = gltfAnimations[0].clone();
        builtinIdle.name = "Idle";
        builtinIdle.tracks = builtinIdle.tracks.filter((t: any) => {
          const lower = t.name.toLowerCase();
          if (lower.includes(".morphtargetinfluences")) return false; // Don't override ARKit morphs
          if (lower.includes("jaw")) return false;
          return true;
        });
        anims.push(builtinIdle);
      }

      // 2. Use Talking_0, emotion, & HipHopDancing animations from animations.glb when AI is speaking / expressing
      if (externalAnimations) {
        externalAnimations.forEach((clip) => {
          const newClip = clip.clone();

          // Map Talking_0 from public/animations.glb as main Talking clip
          if (newClip.name === "Talking_0") newClip.name = "Talking";
          if (newClip.name === "Talking_1") newClip.name = "TalkingAlternative0";
          if (newClip.name === "Talking_2") newClip.name = "TalkingAlternative1";

          // Don't override built-in Idle from avatar.glb
          if (newClip.name === "Idle" && anims.find((a) => a.name === "Idle")) {
            return;
          }

          // Clean only non-rotation tracks that break camera framing or face morph
          newClip.tracks = newClip.tracks.filter((t: any) => {
            const lower = t.name.toLowerCase();
            if (lower.includes("lefteye") || lower.includes("righteye")) return false;
            if (lower.endsWith(".scale")) return false;
            if (lower.endsWith(".position") && !lower.startsWith("hips")) return false;
            if (lower.includes(".morphtargetinfluences")) return false;
            if (lower.includes("jaw")) return false;
            return true;
          });

          anims.push(newClip);
        });
      }

      return anims;
    }, [gltfAnimations, externalAnimations]);

    // useAnimations binds clean clips to the avatar group
    const { actions: _actions, mixer } = useAnimations(cleanAnimations, group);
    const actions = _actions as Record<string, THREE.AnimationAction | null>;

    // State & Crossfading silky smooth
    const [animation, setAnimation] = useState('Idle');
    const prevAnimRef = useRef<string | null>(null);

    /** True once idle is playing */
    const idleAnimPlayingRef = useRef(true); // default true so procedural arm lerp is not stiff
    const [isLoaded, setIsLoaded] = useState(false);
    const { mouse, gl } = useThree();

    const bonesRef = useRef<BoneMap>({
      leftFingers: [],
      rightFingers: [],
    });
    const baseRotationsRef = useRef<Map<THREE.Bone, THREE.Euler>>(new Map());

    const clockRef = useRef(0);
    const smoothHeadPitchRef = useRef(0);
    const smoothHeadYawRef = useRef(0);
    const smoothHeadRollRef = useRef(0);

    // ── Modular Subsystems (Anara Standard Modular Hooks) ────────────────────
    const { updateBlink } = useAvatarBlink();
    const { updateSaccades } = useAvatarSaccades();
    const { updateMicroExpressions } = useAvatarMicroExpressions();
    const { speechCadenceRef, applyProceduralGestures } = useAvatarGestures();

    // ── Rich Emotion Morph State ──────────────────────────────────────────────
    const currentEmotionRef = useRef<AvatarEmotion>("neutral");
    const targetEmotionMorphsRef = useRef<Record<string, number>>({});
    const currentEmotionMorphsRef = useRef<Record<string, number>>({});
    const emotionDecayTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    // ── Gesture State ─────────────────────────────────────────────────────────
    const activeGestureRef = useRef<AvatarGestureType>("none");
    const gestureTimerRef = useRef(0);
    const gestureDurationRef = useRef(2800);
    const backendGestureActiveRef = useRef(false);
    const emotionAnimResetTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    const currentActionNameRef = useRef<string | null>(null);
    const cuteIdleCycleRef = useRef(0);
    const externalActionsRef = useRef<Record<string, THREE.AnimationAction>>({});

    // ── Lip Sync Hook ─────────────────────────────────────────────────────────
    const {
      updateMorphTargets,
      setAudioIntensity,
      queueTranscriptVisemes,
      reset: resetLipSync,
    } = useLipSync({ meshesRef: morphMeshesRef });

    // ─────────────────────────────────────────────────────────────────────────
    // Emotion Morph Presets (Refined, Natural & Harmonious ARKit Blendshapes)
    // ─────────────────────────────────────────────────────────────────────────

    const applyEmotionTargets = useCallback((emotion: AvatarEmotion, autoDecay = true) => {
      if (emotionDecayTimerRef.current) {
        clearTimeout(emotionDecayTimerRef.current);
        emotionDecayTimerRef.current = null;
      }

      currentEmotionRef.current = emotion;
      let t: Record<string, number> = {};

      switch (emotion) {
        case "happy":
        case "enthusiastic":
          t = {
            mouthSmileLeft: 0.22,
            mouthSmileRight: 0.22,
            cheekSquintLeft: 0.12,
            cheekSquintRight: 0.12,
            browInnerUp: 0.08,
            browOuterUpLeft: 0.06,
            browOuterUpRight: 0.06,
          };
          break;

        case "shy":
          t = {
            mouthSmileLeft: 0.18,
            mouthSmileRight: 0.18,
            cheekSquintLeft: 0.14,
            cheekSquintRight: 0.14,
            browInnerUp: 0.10,
            mouthDimpleLeft: 0.08,
            mouthDimpleRight: 0.08,
          };
          break;

        case "angry":
          t = {
            browDownLeft: 0.38,
            browDownRight: 0.38,
            mouthFrownLeft: 0.20,
            mouthFrownRight: 0.20,
            noseSneerLeft: 0.14,
            noseSneerRight: 0.14,
          };
          break;

        case "sad":
          t = {
            browInnerUp: 0.24,
            mouthFrownLeft: 0.18,
            mouthFrownRight: 0.18,
          };
          break;

        case "thinking":
          t = {
            browInnerUp: 0.16,
            browOuterUpRight: 0.16,
            browDownLeft: 0.08,
            mouthSmileRight: 0.08,
          };
          break;

        case "empathetic":
          t = {
            browInnerUp: 0.14,
            mouthSmileLeft: 0.14,
            mouthSmileRight: 0.14,
            cheekSquintLeft: 0.08,
            cheekSquintRight: 0.08,
          };
          break;

        case "curious":
        case "surprised":
          t = {
            browInnerUp: 0.20,
            browOuterUpLeft: 0.12,
            browOuterUpRight: 0.12,
            mouthSmileLeft: 0.08,
            mouthSmileRight: 0.08,
          };
          break;

        case "neutral":
        default:
          t = {
            mouthSmileLeft: 0.08,
            mouthSmileRight: 0.08,
            cheekSquintLeft: 0.04,
            cheekSquintRight: 0.04,
            browInnerUp: 0.0,
            jawOpen: 0.0,
            mouthOpen: 0.0,
          };
          break;
      }

      targetEmotionMorphsRef.current = t;

      // Auto-relax back to serene neutral after expressive moment (4.2 seconds)
      if (autoDecay && emotion !== "neutral") {
        emotionDecayTimerRef.current = setTimeout(() => {
          applyEmotionTargets("neutral", false);
        }, 4200);
      }
    }, []);

    useEffect(() => {
      if (prevAnimRef.current === animation) return;
      const nextAction = actions[animation] || actions['Idle'];
      if (!nextAction) return;

      const prevName = prevAnimRef.current;
      const prevAction = prevName ? actions[prevName] : null;

      if (prevAction && prevAction !== nextAction) {
        prevAction.fadeOut(0.45);
        nextAction.reset().setEffectiveTimeScale(1).setEffectiveWeight(1).fadeIn(0.45).play();
      } else {
        nextAction.reset().setEffectiveTimeScale(1).setEffectiveWeight(1).play();
      }
      prevAnimRef.current = animation;
    }, [animation, actions]);

    // Automatically switch between Talking, Dance, and Idle based on real-time speech state
    const isSpeakingRef = useRef(false);
    useEffect(() => {
      isSpeakingRef.current = isSpeaking;
      if (isSpeaking) {
        // If currently dancing, don't cancel the dance!
        if (dancePhaseRef.current === "dancing") {
          return;
        }

        // If previously waiting for Gemini intro audio, now the intro voice started playing!
        if (dancePhaseRef.current === "awaiting_intro") {
          if (danceSafetyTimerRef.current) clearTimeout(danceSafetyTimerRef.current);
          dancePhaseRef.current = "speaking_intro";
          console.log("[Avatar3D] 🎙️ Gemini intro speech started playing with lip-sync!");
        }

        setAnimation((prev) => {
          // If playing special emotion expression (including Rumba), keep it
          if (["Laughing", "Angry", "Crying", "Terrified", "Rumba"].includes(prev)) {
            return prev;
          }
          return "Talking";
        });
      } else {
        // isSpeaking is false:
        // Check if intro audio just finished ("speaking_intro")
        if (dancePhaseRef.current === "speaking_intro") {
          if (danceSafetyTimerRef.current) clearTimeout(danceSafetyTimerRef.current);
          dancePhaseRef.current = "dancing";
          isDancingRef.current = true;
          if (actions["Rumba"]) {
            if (emotionAnimResetTimerRef.current) clearTimeout(emotionAnimResetTimerRef.current);
            setAnimation("Rumba");
            console.log("[Avatar3D] 💃 Gemini finished speaking intro — start Rumba dance & music!");
            onDanceStart?.();
            emotionAnimResetTimerRef.current = setTimeout(() => {
              dancePhaseRef.current = "idle";
              isDancingRef.current = false;
              setAnimation("Idle");
              resetLipSync();
              applyEmotionTargets("neutral");
              emotionAnimResetTimerRef.current = null;
              onDanceEnd?.();  // notify page.tsx dance finished
            }, 6500);
            return;
          }
        }

        // If still waiting for Gemini audio ("awaiting_intro"), DON'T start dance yet!
        if (dancePhaseRef.current === "awaiting_intro") {
          return;
        }

        // If currently dancing, don't force Idle
        if (dancePhaseRef.current === "dancing" || isDancingRef.current) {
          return;
        }

        // If emotion animation is active, don't cut
        if (emotionAnimResetTimerRef.current) {
          return;
        }

        resetLipSync();
        applyEmotionTargets("neutral");
        setAnimation("Idle");
      }
    }, [isSpeaking, actions, resetLipSync, applyEmotionTargets, onDanceStart, onDanceEnd]);


    // ─────────────────────────────────────────────────────────────────────────
    // Sentiment & Gesture Triggers
    // ─────────────────────────────────────────────────────────────────────────

    const triggerEmotionAnimation = useCallback((emotion: AvatarEmotion) => {
      // If currently dancing, ignore all other emotion triggers until dance finishes
      if (isDancingRef.current) {
        return;
      }

      if (emotion === "dance") {
        dancePhaseRef.current = "awaiting_intro";
        console.log("[Avatar3D] 💃 Dance queued — awaiting Gemini intro speech to start");
        if (danceSafetyTimerRef.current) clearTimeout(danceSafetyTimerRef.current);
        danceSafetyTimerRef.current = setTimeout(() => {
          if (dancePhaseRef.current === "awaiting_intro") {
            console.log("[Avatar3D] 💃 Safety fallback triggered — starting Rumba directly");
            dancePhaseRef.current = "dancing";
            isDancingRef.current = true;
            if (actions["Rumba"]) {
              setAnimation("Rumba");
              onDanceStart?.();
              emotionAnimResetTimerRef.current = setTimeout(() => {
                dancePhaseRef.current = "idle";
                isDancingRef.current = false;
                setAnimation("Idle");
                resetLipSync();
                applyEmotionTargets("neutral");
                emotionAnimResetTimerRef.current = null;
                onDanceEnd?.();
              }, 6500);
            }
          }
        }, 9000);
        return;
      }

      const EMOTION_ANIM_MAP: Partial<Record<AvatarEmotion, { key: string; durationMs: number }>> = {
        angry: { key: "Angry", durationMs: 4000 },
        laughing: { key: "Laughing", durationMs: 4000 },
        surprised: { key: "Terrified", durationMs: 3200 },
        sad: { key: "Crying", durationMs: 4000 },
      };

      const cfg = EMOTION_ANIM_MAP[emotion];

      if (cfg && actions[cfg.key]) {
        // If this emotion animation is already running, let it run smoothly without resetting
        if (emotionAnimResetTimerRef.current && prevAnimRef.current === cfg.key) {
          return;
        }

        if (emotionAnimResetTimerRef.current) clearTimeout(emotionAnimResetTimerRef.current);
        setAnimation(cfg.key);

        emotionAnimResetTimerRef.current = setTimeout(() => {
          setAnimation(isSpeakingRef.current ? "Talking" : "Idle");
          emotionAnimResetTimerRef.current = null;
        }, cfg.durationMs);
      } else {
        // DON'T cut ongoing emotion animation with neutral status!
        if (emotionAnimResetTimerRef.current) {
          return;
        }

        if (isSpeakingRef.current) {
          setAnimation("Talking");
        } else {
          setAnimation("Idle");
        }
      }
    }, [actions]);

    const triggerTextMotion = useCallback((text: string) => {
      // If currently dancing, don't change expression or cut dance
      if (isDancingRef.current) return;

      // Skip: backend gesture is active and has priority
      if (backendGestureActiveRef.current) return;

      // Only use client-side sentiment as fallback when no backend emotion is active
      const { emotion, gesture, gestureDurationMs } = analyzeSpeechSentiment(text);

      // If emotion animation is running, don't reset facial expression by neutral word mid-sentence
      if (emotion === "neutral" && emotionAnimResetTimerRef.current) {
        return;
      }

      applyEmotionTargets(emotion);

      if (gesture !== "none") {
        activeGestureRef.current = gesture;
        gestureTimerRef.current = 0;
        gestureDurationRef.current = gestureDurationMs;
      }

      // ── Trigger emotion body animation (angry.glb / laughing.glb / idle.glb) ─
      if (isLoaded) triggerEmotionAnimation(emotion);
    }, [applyEmotionTargets, triggerEmotionAnimation, isLoaded]);

    const triggerGesture = useCallback((gesture: AvatarGestureType, durationMs = 2800) => {
      if (isDancingRef.current) return;
      activeGestureRef.current = gesture;
      gestureTimerRef.current = 0;
      gestureDurationRef.current = durationMs;
    }, []);

    /**
     * applyBackendEmotion — called by page.tsx when WebSocket receives emotion_update.
     * Maps backend string names → AvatarEmotion / AvatarGestureType and activates them
     * with higher priority (longer duration) than client-side sentiment analysis.
     */
    const applyBackendEmotion = useCallback((emotion: string, gesture: string) => {
      if (isDancingRef.current) return;

      // ── Emotion mapping ─────────────────────────────────────────────────────
      const emotionMap: Record<string, AvatarEmotion> = {
        neutral: "neutral",
        happy: "happy",
        dance: "dance",
        angry: "angry",
        sad: "sad",
        shy: "shy",
        thinking: "thinking",
        empathetic: "empathetic",
        curious: "curious",
        enthusiastic: "enthusiastic",
      };
      const mappedEmotion: AvatarEmotion = emotionMap[emotion] ?? "neutral";
      applyEmotionTargets(mappedEmotion);

      // ── Trigger emotion body animation (angry.glb / laughing.glb / idle.glb) ──
      if (isLoaded) triggerEmotionAnimation(mappedEmotion);

      // ── Gesture mapping (backend name → AvatarGestureType) ──────────────────
      const gestureMap: Record<string, AvatarGestureType> = {
        idle: "none",
        talking: "none",
        explaining: "explain",
        shy_movement: "shy",
        angry_pointing: "angry_pointing",
        think: "think",
        joy: "joy",
        empathy: "empathy",
        nod: "nod",
        shake: "shake",
        salute: "salute",
        question: "question",
        sad: "sad",
        wave: "wave",
      };
      const mappedGesture: AvatarGestureType = gestureMap[gesture] ?? "none";
      if (mappedGesture !== "none") {
        activeGestureRef.current = mappedGesture;
        gestureTimerRef.current = 0;
        gestureDurationRef.current = 3500;
        backendGestureActiveRef.current = true;

        setTimeout(() => {
          backendGestureActiveRef.current = false;
        }, 3600);
      }
    }, [applyEmotionTargets, triggerEmotionAnimation, isLoaded]);

    useImperativeHandle(ref, () => ({
      setAudioIntensity,
      resetLipSync: () => {
        resetLipSync();
        if (!isDancingRef.current) {
          activeGestureRef.current = "none";
          applyEmotionTargets("neutral");
        }
      },
      queueTranscriptVisemes,
      triggerTextMotion,
      setEmotion: (emotion: AvatarEmotion) => {
        if (isDancingRef.current) return;
        applyEmotionTargets(emotion);
      },
      triggerGesture,
      applyBackendEmotion,
      stopDance: () => {
        if (danceSafetyTimerRef.current) clearTimeout(danceSafetyTimerRef.current);
        if (emotionAnimResetTimerRef.current) clearTimeout(emotionAnimResetTimerRef.current);
        danceSafetyTimerRef.current = null;
        emotionAnimResetTimerRef.current = null;
        dancePhaseRef.current = "idle";
        isDancingRef.current = false;
        const nextTarget = isSpeakingRef.current ? "Talking" : "Idle";
        setAnimation(nextTarget);
        applyEmotionTargets("neutral", false);
        resetLipSync();
        console.log("[Avatar3D] 💃 Stop dance executed — smoothly blended to", nextTarget);
      },
      playAnimation: (name: string) => {
        setAnimation(name);
      },
      registerClips: (clips: THREE.AnimationClip[], autoPlayPrefix?: string) => { },
    }), [setAudioIntensity, resetLipSync, queueTranscriptVisemes, triggerTextMotion, applyEmotionTargets, triggerGesture, applyBackendEmotion]);

    // ─────────────────────────────────────────────────────────────────────────
    // Setup Model & Default Photorealistic Avaturn Materials
    // ─────────────────────────────────────────────────────────────────────────

    const onLoadRef = useRef(onLoad);
    useEffect(() => { onLoadRef.current = onLoad; });

    useEffect(() => {
      if (!scene) return;

      const bones: BoneMap = {
        leftFingers: [],
        rightFingers: [],
      };
      const morphMeshes: THREE.SkinnedMesh[] = [];
      const cachedMorphs: CachedMorphMesh[] = [];
      baseRotationsRef.current.clear();

      // Use built-in avatar.glb materials & textures + dewy skin glow on face
      scene.traverse((child) => {
        if (child instanceof THREE.Mesh) {
          child.frustumCulled = false;

          const meshName = (child.name || "").toLowerCase();
          if (meshName.includes("head") && child.material) {
            const mats = Array.isArray(child.material) ? child.material : [child.material];
            mats.forEach((mat) => {
              if (mat instanceof THREE.MeshStandardMaterial) {
                mat.roughness = 0.62; // More natural, not too shiny
                mat.envMapIntensity = 0.85; // Pantulan cahaya lembut
              }
            });
          }

          if (child instanceof THREE.SkinnedMesh && child.morphTargetDictionary && Object.keys(child.morphTargetDictionary).length > 0) {
            const meshName = (child.name || "").toLowerCase();
            if (meshName.includes("head") || meshName.includes("teeth") || meshName.includes("eye") || meshName.includes("mouth") || meshName.includes("avaturn")) {
              morphMeshes.push(child);
              const dict = child.morphTargetDictionary;
              cachedMorphs.push({
                mesh: child,
                influences: child.morphTargetInfluences || [],
                dict,
                blinkL: dict["eyeBlinkLeft"],
                blinkR: dict["eyeBlinkRight"],
                eyesClosed: dict["eyesClosed"],
                eyeLookUpLeft: dict["eyeLookUpLeft"],
                eyeLookDownLeft: dict["eyeLookDownLeft"],
                eyeLookUpRight: dict["eyeLookUpRight"],
                eyeLookDownRight: dict["eyeLookDownRight"],
                eyeLookInLeft: dict["eyeLookInLeft"],
                eyeLookOutLeft: dict["eyeLookOutLeft"],
                eyeLookInRight: dict["eyeLookInRight"],
                eyeLookOutRight: dict["eyeLookOutRight"],
              });
            }
          }
        }

        if (child instanceof THREE.Bone) {
          const n = child.name;
          if (/^Head$/i.test(n) || (n.includes("Head") && !n.includes("Top") && !n.includes("End"))) bones.head = child;
          else if (/^Neck$/i.test(n)) bones.neck = child;
          else if (/Spine2/i.test(n)) bones.spine2 = child;
          else if (/Spine1/i.test(n)) bones.spine1 = child;
          else if (/^Spine$/i.test(n) || /Chest/i.test(n)) bones.spine = child;
          else if (/Hips?/i.test(n)) bones.hips = child;
          else if (/LeftShoulder/i.test(n)) bones.leftShoulder = child;
          else if (/RightShoulder/i.test(n)) bones.rightShoulder = child;
          else if (/^LeftArm$/i.test(n)) bones.leftArm = child;
          else if (/^RightArm$/i.test(n)) bones.rightArm = child;
          else if (/LeftForeArm/i.test(n)) bones.leftForeArm = child;
          else if (/RightForeArm/i.test(n)) bones.rightForeArm = child;
          else if (/^LeftHand$/i.test(n)) bones.leftHand = child;
          else if (/^RightHand$/i.test(n)) bones.rightHand = child;
          else if (/LeftHand(Thumb|Index|Middle|Ring|Pinky)/i.test(n)) {
            bones.leftFingers.push(child);
          } else if (/RightHand(Thumb|Index|Middle|Ring|Pinky)/i.test(n)) {
            bones.rightFingers.push(child);
          }

          baseRotationsRef.current.set(child, child.rotation.clone());
        }
      });

      bonesRef.current = bones;
      morphMeshesRef.current = morphMeshes;
      cachedMorphMeshesRef.current = cachedMorphs;
      applyEmotionTargets("neutral");
      setIsLoaded(true);
      onLoadRef.current?.();

      // Debug: print all bones found + arm bind-pose rotations
      const foundBones = Object.entries(bones)
        .filter(([k, v]) => k !== 'leftFingers' && k !== 'rightFingers' && v != null)
        .map(([k]) => k);
      console.log("[AvatarBones] Found:", foundBones.join(", "));
      if (bones.leftArm && bones.rightArm) {
        const la = bones.leftArm.rotation;
        const ra = bones.rightArm.rotation;
        console.log("[AvatarBones] LeftArm  bind:", la.x.toFixed(3), la.y.toFixed(3), la.z.toFixed(3));
        console.log("[AvatarBones] RightArm bind:", ra.x.toFixed(3), ra.y.toFixed(3), ra.z.toFixed(3));
      } else {
        console.warn("[AvatarBones] ⚠️ LeftArm or RightArm NOT FOUND — arm procedural disabled");
      }

      return () => {
        mixer.stopAllAction();
        if (danceSafetyTimerRef.current) clearTimeout(danceSafetyTimerRef.current);
        if (emotionDecayTimerRef.current) clearTimeout(emotionDecayTimerRef.current);
        if (emotionAnimResetTimerRef.current) clearTimeout(emotionAnimResetTimerRef.current);
      };
    }, [scene, actions, mixer, applyEmotionTargets, gl]);

    const _scratchEuler = useMemo(() => new THREE.Euler(), []);
    const getBase = (bone: THREE.Bone | undefined): THREE.Euler => {
      if (!bone) return _scratchEuler.set(0, 0, 0);
      return baseRotationsRef.current.get(bone) ?? bone.rotation;
    };

    // ─────────────────────────────────────────────────────────────────────────
    // Animation Frame Loop (Priority 1 ensures it executes AFTER AnimationMixer updates at Priority 0)
    // ─────────────────────────────────────────────────────────────────────────

    useFrame((state, delta) => {
      if (!isLoaded || !isVoiceMode) return;

      // Clamp delta to prevent erratic frame-time spikes (crucial for Firefox WebGL stability)
      const safeDelta = Math.min(Math.max(delta, 0.0001), 0.033);

      clockRef.current += safeDelta;
      const t = clockRef.current;
      const bones = bonesRef.current;
      const meshes = morphMeshesRef.current;

      // ── [1] LIVELY CUTE IDLE PROGRESSION (Saat AI Diam) ─────────────────────
      if (!isSpeaking) {
        cuteIdleCycleRef.current += safeDelta * 0.75;
      }
      const cuteCycle = cuteIdleCycleRef.current;

      // ── [2] PROCEDURAL BREATHING & SKELETAL DYNAMICS (Only if no animation playing & not dancing) ─
      const animDriven = idleAnimPlayingRef.current;
      const isGesturing = activeGestureRef.current !== "none";
      const isDancing = isDancingRef.current;

      if (!animDriven && !isDancing) {
        const breathPhase = t * (Math.PI * 2) * BREATH_RATE;
        const breathCycle = Math.sin(breathPhase);
        const breathCyclePos = (breathCycle + 1) * 0.5;
        const breathDepth = isSpeaking ? 1.35 : 1.0;

        const spineBase = getBase(bones.spine);
        const spine2Base = getBase(bones.spine2);

        let spineEngage = isSpeaking ? 0.02 : 0.0;
        if (activeGestureRef.current === "angry") spineEngage += 0.05;

        // Smooth compound body weight shift
        const weightShift = Math.sin(cuteCycle * 0.4) * 0.008;

        if (bones.spine) {
          const targetX = spineBase.x + breathCyclePos * BREATH_SPINE_AMP * breathDepth + spineEngage;
          const targetY = spineBase.y + weightShift * 0.6;
          bones.spine.rotation.x = THREE.MathUtils.lerp(bones.spine.rotation.x, targetX, Math.min(safeDelta * 4, 1));
          bones.spine.rotation.y = THREE.MathUtils.lerp(bones.spine.rotation.y, targetY, Math.min(safeDelta * 2.5, 1));
        }
        if (bones.spine2) {
          const targetX = spine2Base.x + breathCyclePos * BREATH_SPINE_AMP * 0.6 * breathDepth;
          const targetZ = spine2Base.z + weightShift * 0.4;
          bones.spine2.rotation.x = THREE.MathUtils.lerp(bones.spine2.rotation.x, targetX, Math.min(safeDelta * 4, 1));
          bones.spine2.rotation.z = THREE.MathUtils.lerp(bones.spine2.rotation.z, targetZ, Math.min(safeDelta * 2.5, 1));
        }

        // Shoulders: Organic breathing with soft sway (only during Idle mode so Talking stays 100% smooth)
        if (animation === "Idle") {
          const lShoulderBase = getBase(bones.leftShoulder);
          const rShoulderBase = getBase(bones.rightShoulder);
          const shoulderDrop = activeGestureRef.current === "sad" ? 0.04 : 0.0;

          if (bones.leftShoulder) {
            const targetZ = lShoulderBase.z + breathCyclePos * BREATH_SHOULDER_AMP - shoulderDrop + weightShift;
            bones.leftShoulder.rotation.z = THREE.MathUtils.lerp(bones.leftShoulder.rotation.z, targetZ, Math.min(safeDelta * 4, 1));
          }
          if (bones.rightShoulder) {
            const targetZ = rShoulderBase.z - breathCyclePos * BREATH_SHOULDER_AMP + shoulderDrop - weightShift;
            bones.rightShoulder.rotation.z = THREE.MathUtils.lerp(bones.rightShoulder.rotation.z, targetZ, Math.min(safeDelta * 4, 1));
          }
        }
      }




      // ── [3] PROCEDURAL GESTURES & FINGER REST KINEMATICS (Anara Standard Hook) ─
      if (isGesturing) gestureTimerRef.current += safeDelta * 1000;
      const gestureProgress = gestureDurationRef.current > 0 ? gestureTimerRef.current / gestureDurationRef.current : 1.0;

      applyProceduralGestures({
        safeDelta,
        t,
        isGesturing,
        isSpeaking,
        isDancing,
        animDriven,
        audioIntensity,
        activeGesture: activeGestureRef.current,
        gestureProgress,
        bones,
        getBase,
        onGestureComplete: () => {
          activeGestureRef.current = "none";
        },
      });

      // ── [4] LIVING GAZE & SPEAKING DYNAMICS (Applied gracefully at root level) ─
      const gazePitch = THREE.MathUtils.clamp(-mouse.y * 0.08, -0.08, 0.08);
      const gazeYaw = THREE.MathUtils.clamp(mouse.x * 0.12, -0.12, 0.12);
      const speakingNod = isSpeaking ? Math.sin(speechCadenceRef.current * 0.85) * 0.015 * (1 + audioIntensity * 0.5) : 0;

      smoothHeadPitchRef.current = THREE.MathUtils.lerp(smoothHeadPitchRef.current, gazePitch + speakingNod, Math.min(safeDelta * 3.5, 1.0));
      smoothHeadYawRef.current = THREE.MathUtils.lerp(smoothHeadYawRef.current, gazeYaw, Math.min(safeDelta * 3.5, 1.0));

      const targetGroupRotX = smoothHeadPitchRef.current;
      const targetGroupRotY = smoothHeadYawRef.current + Math.sin(t * 0.35) * 0.006;
      const targetGroupPosY = -1.46 + Math.sin(t * 1.5) * 0.003;

      if (group.current) {
        group.current.rotation.x = THREE.MathUtils.lerp(group.current.rotation.x, targetGroupRotX, Math.min(safeDelta * 3.5, 1));
        group.current.rotation.y = THREE.MathUtils.lerp(group.current.rotation.y, targetGroupRotY, Math.min(safeDelta * 3.5, 1));
        group.current.position.y = THREE.MathUtils.lerp(group.current.position.y, targetGroupPosY, Math.min(safeDelta * 2.0, 1));
      }

      // ── [5] EYE SACCADES & BLINKING (Modular Subsystems - Anara Standard) ────
      const saccade = updateSaccades(safeDelta);
      const blinkW = updateBlink(safeDelta);

      // ── [6] FACIAL EXPRESSION LERP (WITH VIBRANT PROSODY EMOTION) ───────────
      // Gentle, subtle conversational eyebrow & cheek prosody
      const browSpeechProsody = isSpeaking ? (Math.sin(speechCadenceRef.current * 1.8) * 0.5 + 0.5) * 0.06 : 0;
      const cheekSpeechBounce = isSpeaking ? (Math.sin(speechCadenceRef.current * 2.2) * 0.5 + 0.5) * 0.05 : 0;
      const idleSmileWarmth = !isSpeaking ? (Math.sin(cuteCycle * 0.7) * 0.5 + 0.5) * 0.05 : 0;

      const exprSpeed = Math.min(safeDelta * 5.0, 1.0);

      for (const [morphName, target] of Object.entries(targetEmotionMorphsRef.current)) {
        let eff = target;
        if (morphName.includes("brow")) eff += browSpeechProsody;
        if (morphName.includes("cheek")) eff += cheekSpeechBounce;
        if (morphName.includes("mouthSmile")) eff += idleSmileWarmth;

        const cur = currentEmotionMorphsRef.current[morphName] ?? 0;
        currentEmotionMorphsRef.current[morphName] = THREE.MathUtils.lerp(cur, eff, exprSpeed);
      }

      for (const morphName of Object.keys(currentEmotionMorphsRef.current)) {
        if (!(morphName in targetEmotionMorphsRef.current)) {
          const cur = currentEmotionMorphsRef.current[morphName] ?? 0;
          currentEmotionMorphsRef.current[morphName] = THREE.MathUtils.lerp(cur, 0, exprSpeed);
        }
      }

      // ── [7] APPLY MORPHS TO ALL FACIAL MESHES (Avaturn ARKit) ───────────────
      const sx = saccade.x;
      const sy = saccade.y;
      const eyeLookUp = Math.max(0, Math.min(1, sy));
      const eyeLookDown = Math.max(0, Math.min(1, -sy));
      const eyeLookInL = Math.max(0, Math.min(1, sx));
      const eyeLookOutL = Math.max(0, Math.min(1, -sx));
      const eyeLookInR = Math.max(0, Math.min(1, -sx));
      const eyeLookOutR = Math.max(0, Math.min(1, sx));

      const microExprCurrent = updateMicroExpressions(safeDelta);
      const cachedMorphs = cachedMorphMeshesRef.current;
      const curEmotions = currentEmotionMorphsRef.current;

      for (let i = 0; i < cachedMorphs.length; i++) {
        const item = cachedMorphs[i];
        const infl = item.influences;
        const dict = item.dict;

        // Blinking
        if (item.blinkL !== undefined) infl[item.blinkL] = blinkW;
        if (item.blinkR !== undefined) infl[item.blinkR] = blinkW;
        if (item.eyesClosed !== undefined) infl[item.eyesClosed] = blinkW;

        // Saccades
        if (item.eyeLookUpLeft !== undefined) infl[item.eyeLookUpLeft] = eyeLookUp;
        if (item.eyeLookDownLeft !== undefined) infl[item.eyeLookDownLeft] = eyeLookDown;
        if (item.eyeLookUpRight !== undefined) infl[item.eyeLookUpRight] = eyeLookUp;
        if (item.eyeLookDownRight !== undefined) infl[item.eyeLookDownRight] = eyeLookDown;
        if (item.eyeLookInLeft !== undefined) infl[item.eyeLookInLeft] = eyeLookInL;
        if (item.eyeLookOutLeft !== undefined) infl[item.eyeLookOutLeft] = eyeLookOutL;
        if (item.eyeLookInRight !== undefined) infl[item.eyeLookInRight] = eyeLookInR;
        if (item.eyeLookOutRight !== undefined) infl[item.eyeLookOutRight] = eyeLookOutR;

        // Emotional blendshapes (emotion layer + micro-expression layer combined)
        for (const morphName in curEmotions) {
          const idx = dict[morphName];
          if (idx !== undefined) {
            const val = curEmotions[morphName];
            const microVal = microExprCurrent[morphName] ?? 0;
            infl[idx] = Math.min(Math.max(val + microVal, 0), 1);
          }
        }

        // Apply micro-expression morphs that aren't in the emotion layer
        for (const morphName in microExprCurrent) {
          if (morphName in curEmotions) continue;
          const idx = dict[morphName];
          if (idx !== undefined) {
            infl[idx] = Math.min(Math.max(microExprCurrent[morphName], 0), 1);
          }
        }
      }

      // ── [8] PHONETIC SPEECH LIP-SYNC ───────────────────────────────────────
      updateMorphTargets(safeDelta);
    });

    return (
      <group ref={group} position={[0, -1.46, 0]} scale={[0.91, 1.0, 0.93]}>
        <primitive object={scene} />
      </group>
    );
  }
);

Avatar3D.displayName = "Avatar3D";
export default Avatar3D;

// Preload avatar model and animations locally without Draco CDN dependencies
useGLTF.preload('/avatar.glb', false);
useGLTF.preload('/animations.glb', false);
