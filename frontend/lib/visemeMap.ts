/**
 * Natural, subtle ARKit & Oculus blendshape viseme mapping for human avatars.
 * Calibrated with gentle weights to ensure graceful, realistic speech without exaggeration.
 */

export type VisemeName =
  | "viseme_sil"    // Silence
  | "viseme_PP"     // p, b, m
  | "viseme_FF"     // f, v
  | "viseme_TH"     // th (dental)
  | "viseme_DD"     // d, t, n, l
  | "viseme_kk"     // k, g
  | "viseme_CH"     // ch, j, sh, zh
  | "viseme_SS"     // s, z
  | "viseme_nn"     // n, ng
  | "viseme_RR"     // r
  | "viseme_aa"     // a (open)
  | "viseme_E"      // e
  | "viseme_I"      // i
  | "viseme_O"      // o
  | "viseme_U";     // u

export interface VisemeBlendshapeEntry {
  morphTargets: { name: string; weight: number }[];
}

export const VISEME_MAP: Record<VisemeName, VisemeBlendshapeEntry> = {
  viseme_sil: { morphTargets: [] },
  viseme_PP: {
    morphTargets: [
      { name: "mouthClose", weight: 0.35 },
      { name: "jawOpen", weight: 0.02 },
    ],
  },
  viseme_FF: {
    morphTargets: [
      { name: "mouthFunnel", weight: 0.10 },
      { name: "mouthLowerDownLeft", weight: 0.12 },
      { name: "mouthLowerDownRight", weight: 0.12 },
      { name: "jawOpen", weight: 0.06 },
    ],
  },
  viseme_TH: {
    morphTargets: [
      { name: "jawOpen", weight: 0.10 },
      { name: "mouthLowerDownLeft", weight: 0.08 },
      { name: "mouthLowerDownRight", weight: 0.08 },
    ],
  },
  viseme_DD: {
    morphTargets: [
      { name: "jawOpen", weight: 0.12 },
      { name: "mouthLowerDownLeft", weight: 0.06 },
      { name: "mouthLowerDownRight", weight: 0.06 },
    ],
  },
  viseme_kk: {
    morphTargets: [
      { name: "jawOpen", weight: 0.14 },
      { name: "mouthLowerDownLeft", weight: 0.08 },
      { name: "mouthLowerDownRight", weight: 0.08 },
    ],
  },
  viseme_CH: {
    morphTargets: [
      { name: "mouthFunnel", weight: 0.12 },
      { name: "jawOpen", weight: 0.08 },
    ],
  },
  viseme_SS: {
    morphTargets: [
      { name: "mouthStretchLeft", weight: 0.10 },
      { name: "mouthStretchRight", weight: 0.10 },
      { name: "jawOpen", weight: 0.06 },
    ],
  },
  viseme_nn: {
    morphTargets: [
      { name: "jawOpen", weight: 0.08 },
      { name: "mouthLowerDownLeft", weight: 0.05 },
      { name: "mouthLowerDownRight", weight: 0.05 },
    ],
  },
  viseme_RR: {
    morphTargets: [
      { name: "mouthFunnel", weight: 0.10 },
      { name: "jawOpen", weight: 0.10 },
    ],
  },
  viseme_aa: {
    morphTargets: [
      { name: "jawOpen", weight: 0.22 },
      { name: "mouthLowerDownLeft", weight: 0.10 },
      { name: "mouthLowerDownRight", weight: 0.10 },
    ],
  },
  viseme_E: {
    morphTargets: [
      { name: "jawOpen", weight: 0.14 },
      { name: "mouthSmileLeft", weight: 0.08 },
      { name: "mouthSmileRight", weight: 0.08 },
    ],
  },
  viseme_I: {
    morphTargets: [
      { name: "jawOpen", weight: 0.10 },
      { name: "mouthSmileLeft", weight: 0.10 },
      { name: "mouthSmileRight", weight: 0.10 },
    ],
  },
  viseme_O: {
    morphTargets: [
      { name: "jawOpen", weight: 0.16 },
      { name: "mouthFunnel", weight: 0.15 },
    ],
  },
  viseme_U: {
    morphTargets: [
      { name: "mouthFunnel", weight: 0.18 },
      { name: "mouthPucker", weight: 0.12 },
      { name: "jawOpen", weight: 0.08 },
    ],
  },
};

const CHAR_TO_VISEME: Record<string, VisemeName> = {
  a: "viseme_aa",
  i: "viseme_I",
  u: "viseme_U",
  e: "viseme_E",
  o: "viseme_O",
  b: "viseme_PP",
  p: "viseme_PP",
  m: "viseme_PP",
  f: "viseme_FF",
  v: "viseme_FF",
  d: "viseme_DD",
  t: "viseme_DD",
  n: "viseme_nn",
  l: "viseme_DD",
  r: "viseme_RR",
  k: "viseme_kk",
  g: "viseme_kk",
  c: "viseme_CH",
  j: "viseme_CH",
  s: "viseme_SS",
  z: "viseme_SS",
  w: "viseme_U",
  y: "viseme_I",
  h: "viseme_aa",
};

export function textToVisemeSequence(
  text: string,
  totalDurationMs: number = 3000
): { viseme: VisemeName; timeMs: number }[] {
  const letters = text.toLowerCase().replace(/[^a-z]/g, "");
  if (letters.length === 0) return [];

  const msPerChar = totalDurationMs / letters.length;
  const sequence: { viseme: VisemeName; timeMs: number }[] = [];

  for (let i = 0; i < letters.length; i++) {
    const char = letters[i];
    const viseme = CHAR_TO_VISEME[char] ?? "viseme_aa";
    sequence.push({
      viseme,
      timeMs: Math.round(i * msPerChar),
    });
  }

  return sequence;
}
