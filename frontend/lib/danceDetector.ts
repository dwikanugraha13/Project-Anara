/**
 * Shared dance keyword and command detector for Project Anara.
 * Centralizes NLP normalization, regex patterns, and command recognition
 * used by page.tsx and useSpeechKeywordDetector.
 */

export const DANCE_ACTION_WORDS = [
  "nari", "menari", "joget", "dance", "dansa", "rumba",
];

export const COMMAND_MARKERS = [
  "dong", "ayo", "coba", "tolong", "bisa", "yuk", "silakan", "coba kamu", "mohon"
];

export const INFO_QUERY_MARKERS = [
  "apa itu", "apa tarian", "sejarah", "adat", "tradisional", "nama tarian", "jenis tarian", "asal usul", "artinya", "definisi"
];

export const REPEAT_WORDS = [
  "lagi", "sekali lagi", "ulang", "satu lagi", "encore",
];

export const NAME_VARIATIONS = [
  "anara", "hanara", "annara", "anarah", "nara"
];

export function normalizeText(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^\p{L}\p{N}\s]/gu, " ")
    .replace(/\s+/g, " ")
    .trim();
}

export const DANCE_STRICT_PATTERNS = [
  /\b(?:ayo|yuk|coba|tolong|minta|silakan)\s+(?:nari|menari|joget|dansa|dance)\b/,
  /\b(?:nari|menari|joget|dansa|dance)\s+(?:dong|sekarang|lagi|yuk|nih|untukku)\b/,
  /\b(?:anara|nara)\s+(?:ayo|yuk|coba|tolong)?\s*(?:nari|menari|joget|dansa|dance)\b/,
  /\b(?:tunjukkan|tampilkan|mainkan)\s+(?:tarian|dance|joget)\s+(?:rumba|3d|mu|kamu)?\b/,
  /\b(?:hibur|hiburan)\s+(?:aku|kami|saya)\s+(?:dengan|pake|pakai)?\s*(?:tarian|nari|joget|dance)\b/,
  /\b(?:dance|nari)\s+for\s+me\b/,
];

export function isFrontendDanceCommand(text: string): boolean {
  const norm = normalizeText(text);
  if (!norm) return false;

  // Block questions (e.g. "apa tarian...", "kamu bisa nari gak", "apakah kamu bisa...")
  if (
    INFO_QUERY_MARKERS.some((q) => norm.includes(q)) ||
    /\b(?:apa|apakah|bisa\s+nggak|bisa\s+gak|kenapa|mengapa|siapa|sebutkan)\b/.test(norm)
  ) {
    return false;
  }

  const words = norm.split(" ");
  // Strict rule: Require at least 2 words (never trigger on single words like 'nari' or 'rumba')
  if (words.length < 2) {
    return false;
  }

  return DANCE_STRICT_PATTERNS.some((pat) => pat.test(norm));
}

export function isDanceKeyword(text: string): boolean {
  const norm = normalizeText(text);
  if (!norm) return false;

  // Block informational questions
  if (INFO_QUERY_MARKERS.some((q) => norm.includes(q))) {
    return false;
  }

  const words = norm.split(" ");

  // Direct short commands
  if (["nari", "menari", "joget", "dance", "dansa", "anara nari", "anara menari", "anara joget", "anara dance"].includes(norm)) {
    return true;
  }

  // Check if contains explicit dance action verb as a distinct word
  const hasDanceAction = DANCE_ACTION_WORDS.some((action) => words.includes(action));
  if (!hasDanceAction) return false;

  const hasName = NAME_VARIATIONS.some((name) => words.includes(name));
  const hasCommand = COMMAND_MARKERS.some((marker) => words.includes(marker) || norm.includes(marker));

  return hasDanceAction && (hasName || hasCommand);
}

export function getDanceReplyPrompt(text: string): string {
  return "[Info Sistem]: Musik dan tarian 3D Anara sedang diputar di layar pengguna. Sambut tarian ini dengan ceria, antusias, dan alami dalam 1 kalimat singkat!";
}
