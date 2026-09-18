import { useRef } from "react";
import * as THREE from "three";
import type { AvatarGestureType } from "@/lib/sentimentAnalyzer";

export interface BoneMap {
  spine?: THREE.Bone;
  spine1?: THREE.Bone;
  spine2?: THREE.Bone;
  neck?: THREE.Bone;
  head?: THREE.Bone;
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

export function useAvatarGestures() {
  const speechCadenceRef = useRef(0);

  const applyProceduralGestures = (params: {
    safeDelta: number;
    t: number;
    isGesturing: boolean;
    isSpeaking: boolean;
    isDancing: boolean;
    animDriven: boolean;
    audioIntensity: number;
    activeGesture: AvatarGestureType;
    gestureProgress: number;
    bones: BoneMap;
    getBase: (bone?: THREE.Bone) => THREE.Euler;
    onGestureComplete?: () => void;
  }) => {
    const {
      safeDelta,
      t,
      isGesturing,
      isSpeaking,
      isDancing,
      animDriven,
      audioIntensity,
      activeGesture,
      gestureProgress,
      bones,
      getBase,
      onGestureComplete,
    } = params;

    if (isSpeaking && !isGesturing) {
      speechCadenceRef.current += safeDelta * 2.4;
    }

    const armSpeed = animDriven ? 0.0 : safeDelta * (isGesturing ? 10.0 : isSpeaking ? 6.0 : 4.0);

    const lerpB = (bone: THREE.Bone | undefined, tx: number, ty: number, tz: number) => {
      if (!bone || armSpeed === 0) return;
      const s = Math.min(armSpeed, 1);
      bone.rotation.x = THREE.MathUtils.lerp(bone.rotation.x, tx, s);
      bone.rotation.y = THREE.MathUtils.lerp(bone.rotation.y, ty, s);
      bone.rotation.z = THREE.MathUtils.lerp(bone.rotation.z, tz, s);
    };

    if (!isDancing && (isGesturing || !animDriven)) {
      const lArmBase = getBase(bones.leftArm);
      const rArmBase = getBase(bones.rightArm);
      const lForeBase = getBase(bones.leftForeArm);
      const rForeBase = getBase(bones.rightForeArm);
      const lHandBase = getBase(bones.leftHand);
      const rHandBase = getBase(bones.rightHand);

      const lArmRot = animDriven && bones.leftArm ? bones.leftArm.rotation : lArmBase;
      const rArmRot = animDriven && bones.rightArm ? bones.rightArm.rotation : rArmBase;
      const lForeRot = animDriven && bones.leftForeArm ? bones.leftForeArm.rotation : lForeBase;
      const rForeRot = animDriven && bones.rightForeArm ? bones.rightForeArm.rotation : rForeBase;
      const lHandRot = animDriven && bones.leftHand ? bones.leftHand.rotation : lHandBase;
      const rHandRot = animDriven && bones.rightHand ? bones.rightHand.rotation : rHandBase;

      let tLArmX = animDriven ? lArmRot.x : lArmBase.x;
      let tLArmY = animDriven ? lArmRot.y : lArmBase.y;
      let tLArmZ = animDriven ? lArmRot.z : lArmBase.z + 1.35;
      let tRArmX = animDriven ? rArmRot.x : rArmBase.x;
      let tRArmY = animDriven ? rArmRot.y : rArmBase.y;
      let tRArmZ = animDriven ? rArmRot.z : rArmBase.z - 1.35;
      let tLForeX = animDriven ? lForeRot.x : lForeBase.x;
      let tLForeY = animDriven ? lForeRot.y : lForeBase.y;
      let tLForeZ = animDriven ? lForeRot.z : lForeBase.z;
      let tRForeX = animDriven ? rForeRot.x : rForeBase.x;
      let tRForeY = animDriven ? rForeRot.y : rForeBase.y;
      let tRForeZ = animDriven ? rForeRot.z : rForeBase.z;
      let tLHandX = animDriven ? lHandRot.x : lHandBase.x;
      let tLHandY = animDriven ? lHandRot.y : lHandBase.y;
      let tLHandZ = animDriven ? lHandRot.z : lHandBase.z;
      let tRHandX = animDriven ? rHandRot.x : rHandBase.x;
      let tRHandY = animDriven ? rHandRot.y : rHandBase.y;
      let tRHandZ = animDriven ? rHandRot.z : rHandBase.z;

      // Speaking accent
      if (isSpeaking && !isGesturing) {
        const cad = speechCadenceRef.current;
        const vol = Math.min(1.0, audioIntensity * 2.5);
        const liftR = (Math.sin(cad * 0.9) * 0.5 + 0.5) * (0.10 + vol * 0.06);
        const microBeat = Math.sin(cad * 2.1) * (0.04 + vol * 0.03);
        tRForeX += liftR * 0.20 + microBeat;
        tRForeY += liftR * 0.08;
        tRHandX += microBeat * 0.4;
      }

      // Gesture offsets
      if (isGesturing) {
        const prog = Math.min(1.0, gestureProgress);
        const ease = Math.sin(prog * Math.PI);
        const easeC = ease * ease * (3 - 2 * ease);

        switch (activeGesture) {
          case "salute":
            tRArmX += 0.40 * easeC; tRArmZ -= 0.55 * easeC;
            tRForeX += 0.85 * easeC; tRForeY += 0.35 * easeC;
            tRHandX += 0.25 * easeC; tRHandZ += 0.20 * easeC;
            break;
          case "wave": {
            const wOsc = Math.sin(t * 8.5) * 0.40 * ease;
            tRArmX += 0.45 * easeC; tRArmZ -= 0.60 * easeC;
            tRForeX += 0.55 * easeC; tRForeZ += wOsc * 0.38;
            tRHandZ += wOsc * 0.50;
            break;
          }
          case "shy":
            tRArmX += 0.50 * easeC; tRArmZ -= 0.30 * easeC;
            tRForeX += 0.75 * easeC; tRForeY += 0.25 * easeC;
            tRHandX += 0.35 * easeC;
            break;
          case "angry":
          case "angry_pointing": {
            const tr = Math.sin(t * 18) * 0.012 * ease;
            tRArmX += 0.35 * easeC; tRArmZ -= 0.55 * easeC;
            tRForeX += 0.55 * easeC + tr; tRForeY += 0.15 * easeC;
            tRHandX += 0.25 * easeC + tr;
            break;
          }
          case "think":
            tRArmX += 0.38 * easeC; tRArmZ -= 0.45 * easeC;
            tRForeX += 0.65 * easeC; tRHandX += 0.25 * easeC;
            break;
          case "joy": {
            const jB = Math.sin(t * 5.0) * 0.08 * ease;
            tLArmZ += 0.28 * easeC; tRArmZ -= 0.28 * easeC;
            tLForeX += (0.22 + jB) * easeC; tRForeX += (0.22 + jB) * easeC;
            break;
          }
          case "empathy":
            tRArmX += 0.28 * easeC; tRArmZ -= 0.30 * easeC;
            tRForeX += 0.40 * easeC; tRHandX += 0.20 * easeC;
            break;
          case "sad":
            tLForeX -= 0.12 * easeC; tRForeX -= 0.12 * easeC;
            break;
          case "nod":
          case "shake":
            break;
          case "explain": {
            const rDom = (Math.sin(t * 3.0) + 1) * 0.5;
            tRArmZ -= 0.25 * easeC;
            tRForeX += (0.35 + 0.15 * rDom) * easeC;
            tRForeY += 0.08 * easeC * rDom;
            break;
          }
          case "question":
            tRArmZ -= 0.30 * easeC;
            tRForeX += 0.35 * easeC; tRHandX += 0.12 * easeC;
            break;
        }

        if (prog >= 1.0) {
          onGestureComplete?.();
        }
      }

      lerpB(bones.leftArm, tLArmX, tLArmY, tLArmZ);
      lerpB(bones.rightArm, tRArmX, tRArmY, tRArmZ);
      lerpB(bones.leftForeArm, tLForeX, tLForeY, tLForeZ);
      lerpB(bones.rightForeArm, tRForeX, tRForeY, tRForeZ);
      lerpB(bones.leftHand, tLHandX, tLHandY, tLHandZ);
      lerpB(bones.rightHand, tRHandX, tRHandY, tRHandZ);
    }

    if (!isDancing) {
      for (const finger of bones.leftFingers) {
        const base = getBase(finger);
        finger.rotation.x = THREE.MathUtils.lerp(finger.rotation.x, base.x, armSpeed);
        finger.rotation.y = THREE.MathUtils.lerp(finger.rotation.y, base.y, armSpeed);
        finger.rotation.z = THREE.MathUtils.lerp(finger.rotation.z, base.z, armSpeed);
      }
      for (const finger of bones.rightFingers) {
        const base = getBase(finger);
        finger.rotation.x = THREE.MathUtils.lerp(finger.rotation.x, base.x, armSpeed);
        finger.rotation.y = THREE.MathUtils.lerp(finger.rotation.y, base.y, armSpeed);
        finger.rotation.z = THREE.MathUtils.lerp(finger.rotation.z, base.z, armSpeed);
      }
    }
  };

  return {
    speechCadenceRef,
    applyProceduralGestures,
  };
}
