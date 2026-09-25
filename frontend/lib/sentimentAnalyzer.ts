/**
 * Lightweight, language-agnostic text sentiment & gesture analyzer for 3D AI Voice Assistant.
 * Detects emotion, conversational intent, and contextual gesture triggers
 * from AI speech responses using universal emojis, structural punctuation,
 * and high-confidence semantic patterns.
 */

export type AvatarEmotion =
  | "neutral"
  | "happy"
  | "laughing"
  | "dance"
  | "thinking"
  | "enthusiastic"
  | "empathetic"
  | "curious"
  | "surprised"
  | "shy"
  | "angry"
  | "sad";

export type AvatarGestureType =
  | "none"
  | "salute"
  | "wave"
  | "nod"
  | "shake"
  | "think"
  | "joy"
  | "empathy"
  | "explain"
  | "question"
  | "shy"
  | "angry"
  | "angry_pointing"
  | "sad"
  | "facepalm";

export interface SentimentAnalysisResult {
  emotion: AvatarEmotion;
  gesture: AvatarGestureType;
  intensity: number;       // 0.0 – 1.0
  gestureDurationMs: number;
}

// ─────────────────────────────────────────────────────────────────────────────
// Universal Pattern Matchers (Language-Agnostic Emoji & Structural Punctuation)
// ─────────────────────────────────────────────────────────────────────────────

const EMOJI_PATTERNS = [
  { regex: /[\u{1FAE1}]/u, emotion: "enthusiastic", gesture: "salute", intensity: 0.95, duration: 3200 }, // 🫡
  { regex: /[\u{1F44B}]/u, emotion: "happy", gesture: "wave", intensity: 0.9, duration: 2800 },         // 👋
  { regex: /[\u{1F602}\u{1F923}\u{1F606}]/u, emotion: "laughing", gesture: "joy", intensity: 0.95, duration: 4000 }, // 😂 🤣 😆
  { regex: /[\u{1F600}-\u{1F604}\u{1F389}\u{2728}\u{1F44F}\u{1F64C}\u{1F973}]/u, emotion: "happy", gesture: "joy", intensity: 0.85, duration: 2600 },
  { regex: /[\u{1F620}\u{1F621}\u{1F92C}\u{1F4A2}]/u, emotion: "angry", gesture: "angry", intensity: 0.95, duration: 3500 }, // 😠 😡 🤬 💢
  { regex: /[\u{1F622}\u{1F62D}\u{1F494}\u{1F614}]/u, emotion: "sad", gesture: "sad", intensity: 0.85, duration: 3500 }, // 😢 😭 💔 😔
  { regex: /[\u{1F633}\u{1F97A}\u{1F648}\u{1F970}]/u, emotion: "shy", gesture: "shy", intensity: 0.9, duration: 2800 }, // 😳 🥺 🙈 🥰
  { regex: /[\u{1F914}\u{1F9D0}\u{1F4AD}]/u, emotion: "thinking", gesture: "think", intensity: 0.85, duration: 2800 }, // 🤔 🧐 💭
  { regex: /[\u{1F926}\u{1F631}\u{1F92F}]/u, emotion: "surprised", gesture: "facepalm", intensity: 0.8, duration: 2800 }, // 🤦 😱 🤯
] as const;

export function analyzeSpeechSentiment(text: string): SentimentAnalysisResult {
  const cleanText = text.trim();

  if (!cleanText) {
    return { emotion: "neutral", gesture: "none", intensity: 0.5, gestureDurationMs: 2000 };
  }

  // 1. Check universal emojis (works equally across all human languages)
  for (const item of EMOJI_PATTERNS) {
    if (item.regex.test(cleanText)) {
      return {
        emotion: item.emotion as AvatarEmotion,
        gesture: item.gesture as AvatarGestureType,
        intensity: item.intensity,
        gestureDurationMs: item.duration,
      };
    }
  }

  // 2. Interrogative / Question punctuation (universal inquiry signal)
  if (cleanText.includes("?") || cleanText.includes("¿")) {
    return { emotion: "curious", gesture: "question", intensity: 0.75, gestureDurationMs: 2400 };
  }

  // 3. Exclamatory high-energy punctuation
  if (cleanText.includes("!!") || cleanText.includes("!?") || cleanText.includes("?!")) {
    return { emotion: "enthusiastic", gesture: "explain", intensity: 0.85, gestureDurationMs: 2600 };
  }

  // Default fallback: conversational explaining with neutral posture.
  // Specialized animations/gestures are model-driven via tool calling and backend telemetry.
  return { emotion: "neutral", gesture: "explain", intensity: 0.6, gestureDurationMs: 2400 };
}
