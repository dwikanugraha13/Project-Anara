/**
 * Shared dance keyword and command detector for Project Anara.
 * Centralizes normalization and lightweight intent detection for 3D avatar animation triggers.
 * Primary deliberate animations are model-driven via trigger_avatar_animation.
 */

export const DANCE_ACTION_WORDS = [
  "dance", "dancing", "rumba"
];

export function normalizeText(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^\p{L}\p{N}\s]/gu, " ")
    .replace(/\s+/g, " ")
    .trim();
}

export function isFrontendDanceCommand(text: string): boolean {
  const norm = normalizeText(text);
  if (!norm) return false;

  const words = norm.split(" ");
  // Discard pure questions asking about information or definitions
  if (norm.startsWith("what")) {
    return false;
  }

  return words.some((w) => DANCE_ACTION_WORDS.includes(w));
}

export function isDanceKeyword(text: string): boolean {
  const norm = normalizeText(text);
  if (!norm) return false;

  const words = norm.split(" ");
  return words.some((w) => DANCE_ACTION_WORDS.includes(w));
}

export function getDanceReplyPrompt(text: string): string {
  return "[SYSTEM EVENT: 3D avatar dance animation active on user screen. Acknowledge cheerfully in 1 concise sentence matching the user's active language.]";
}
