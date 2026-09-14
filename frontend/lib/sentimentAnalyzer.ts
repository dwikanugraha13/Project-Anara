/**
 * Real-time text sentiment & gesture analyzer for 3D AI Voice Assistant.
 * Detects emotion, conversational intent, and contextual gesture triggers
 * from Indonesian (and English) AI speech responses and user commands.
 *
 * Emotions & Gestures supported:
 *  - Salute / Hormat → salute (tangan sikap hormat di pelipis)
 *  - Greeting       → wave (tangan melambai)
 *  - Happy/Joy      → joy (tangan terbuka)
 *  - Shy/Malu       → shy (tangan menutupi mulut/wajah)
 *  - Angry/Marah    → angry (ekspresi kesal/marah, tangan tegang)
 *  - Sad            → sad (kepala turun, tangan di dada)
 *  - Empathy        → empathy (tangan di dada)
 *  - Thinking       → think (tangan ke dagu)
 *  - Explain        → explain (gestur luwes menjelaskan)
 *  - Question       → question (tangan terangkat)
 *  - Agree          → nod
 *  - Disagree       → shake
 */

export type AvatarEmotion =
  | "neutral"
  | "happy"
  | "laughing"
  | "dance"     // Menari / hibur / joget
  | "thinking"
  | "enthusiastic"
  | "empathetic"
  | "curious"
  | "surprised"
  | "shy"       // Malu / blush
  | "angry"     // Kesal / marah
  | "sad";      // Sedih / kecewa

export type AvatarGestureType =
  | "none"
  | "salute"         // Sikap hormat di pelipis kanan
  | "wave"           // Melambai — halo/sapaan
  | "nod"            // Angguk — setuju
  | "shake"          // Geleng — tidak setuju
  | "think"          // Tangan ke dagu — berpikir
  | "joy"            // Tangan terbuka — gembira
  | "empathy"        // Tangan di dada — empati
  | "explain"        // Gestur bergantian — menjelaskan
  | "question"       // Tangan terangkat — tanya
  | "shy"            // Tangan tutup mulut — malu
  | "angry"          // Tangan tegang / mengepal — kesal
  | "angry_pointing" // Tangan menunjuk — marah menegaskan (dari backend)
  | "sad"            // Tangan di dada, kepala turun — sedih
  | "facepalm";      // Tangan ke dahi — frustrasi

export interface SentimentAnalysisResult {
  emotion: AvatarEmotion;
  gesture: AvatarGestureType;
  intensity: number;       // 0.0 – 1.0
  gestureDurationMs: number;
}

// ─────────────────────────────────────────────────────────────────────────────
// Keyword Dictionaries (Indonesian & English)
// ─────────────────────────────────────────────────────────────────────────────

// NOTE: a DANCE_KEYWORDS list used to live here containing generic words like
// "musik" and "pesta". It was never consumed by analyzeSpeechSentiment(), but it
// was a trap waiting to be wired up — dancing must only ever be triggered by an
// explicit user command plus confirmation (handled in the backend), never by
// keyword sentiment. Removed deliberately.

const SALUTE_KEYWORDS = [
  "hormat", "sikap hormat", "memberi hormat", "salute", "siap grak", "laksanakan",
  "respek", "grak", "tegak grak", "salam hormat", "hormat senjata", "lapor",
];

const GREETING_KEYWORDS = [
  "halo", "hai", "hay", "hei", "hey", "salam", "selamat pagi", "selamat siang", "selamat sore", "selamat malam",
  "assalamualaikum", "assalamu'alaikum", "assalamu alaikum",
  "senang berkenalan", "senang bertemu", "apa kabar", "gimana kabarnya",
  "welcome", "hello", "hi", "good morning", "good afternoon", "good evening", "greetings",
  "dadah", "bye", "sampai jumpa",
];

const LAUGH_KEYWORDS = [
  "wkwk", "wkwkwk", "haha", "hahaha", "hehe", "hehehe", "hihi", "ngakak", "kocak", "lawak",
  "lelucon", "humor", "lucu banget", "tertawa", "ketawa", "lol", "lmao", "rofl", "hilarious", "joke", "funny",
];

const SHY_KEYWORDS = [
  "malu", "segan", "canggung", "salah tingkah", "kikuk", "tersipu", "blush",
  "cantik", "manis", "pujian", "dipuji", "aduh", "ups", "oops",
  "bisa aja", "kamu bisa aja", "jangan gitu",
  "shy", "embarrassed", "awkward", "flattered", "blushing",
];

const ANGRY_KEYWORDS = [
  "kesal", "marah", "jengkel", "frustrasi", "bosan", "capek", "lelah mendengar",
  "tidak sabar", "mengecewakan", "menyebalkan", "tidak menyenangkan", "ngeselin", "benci",
  "geram", "murka", "emosi", "sebel", "bad mood", "dongkol",
  "angry", "annoyed", "frustrated", "irritated", "upset", "furious", "mad",
  "terrible", "awful", "hate", "marah dong", "coba marah", "ekspresi marah",
];

const SAD_KEYWORDS = [
  "sedih", "kecewa", "menyesal", "kasihan", "duka", "kehilangan", "hancur",
  "terpukul", "sakit hati", "patah hati", "susah", "nangis", "menangis", "tangis", "sayang sekali",
  "sad", "disappointed", "sorry to hear", "unfortunate", "heartbroken", "crying",
  "miss", "lost", "tragedy", "grieving",
];

const FACEPALM_KEYWORDS = [
  "aduh", "astaga", "ya ampun", "masa sih", "tidak mungkin", "tidak percaya",
  "waduh", "duh", "kaget", "terkejut", "takut", "ngeri", "seram", "shock",
  "oh my", "unbelievable", "seriously", "come on", "really?", "no way",
  "ugh", "sigh", "terrified", "spooked",
];

const JOY_KEYWORDS = [
  "bagus", "hebat", "keren", "luar biasa", "mantap", "wah", "suka", "senang",
  "gembira", "fantastis", "sempurna", "menakjubkan", "sukses", "selamat",
  "great", "awesome", "amazing", "wonderful", "excellent", "fantastic", "congratulations",
  "yay", "yes!", "hore", "bahagia", "asik", "asyik",
];

const EMPATHY_KEYWORDS = [
  "maaf", "mohon maaf", "turut berduka", "jangan khawatir", "tenang saja",
  "saya mengerti", "sabar", "jangan bersedih", "tetap semangat",
  "sorry", "apologize", "don't worry", "i understand", "stay strong",
];

const THINKING_KEYWORDS = [
  "menurut saya", "mari kita", "coba kita", "mungkin", "sepertinya", "sebentar",
  "analisis", "pertimbangkan", "hmm", "menarik", "secara umum", "jika dilihat",
  "pikir", "berpikir", "let me think", "perhaps", "maybe", "interesting", "considering", "in my opinion",
];

const AGREEMENT_KEYWORDS = [
  "iya", "ya", "tentu", "betul", "benar", "setuju", "pasti", "bisa", "siap",
  "tepat", "oke", "baik", "tentu saja", "jelas", "sepakat", "sudah pasti",
  "yes", "sure", "absolutely", "correct", "agree", "of course", "definitely", "right",
];

const DISAGREEMENT_KEYWORDS = [
  "tidak", "bukan", "jangan", "belum", "kurang tepat", "tidak bisa", "mustahil",
  "sayangnya tidak", "no", "not", "cannot", "never", "disagree", "incorrect",
];

const EXPLAINING_KEYWORDS = [
  "pertama", "kedua", "ketiga", "karena", "jadi", "contohnya", "adalah",
  "merupakan", "hal ini", "alasannya", "dengan demikian", "fungsinya", "langkah",
  "first", "second", "because", "therefore", "for example", "means", "specifically",
];

const QUESTION_KEYWORDS = [
  "apakah", "mengapa", "bagaimana", "kapan", "siapa", "kenapa", "mana", "adakah",
  "bisa jelaskan", "what", "why", "how", "when", "who", "which", "could you",
];

// ─────────────────────────────────────────────────────────────────────────────
// Main Analyzer
// ─────────────────────────────────────────────────────────────────────────────

export function analyzeSpeechSentiment(text: string): SentimentAnalysisResult {
  const cleanText = text.toLowerCase().trim();

  if (!cleanText) {
    return { emotion: "neutral", gesture: "none", intensity: 0.5, gestureDurationMs: 2000 };
  }

  const has = (keywords: string[]) => keywords.some((kw) => cleanText.includes(kw));

  // Priority 1: Salute / Hormat — sikap hormat di pelipis kanan
  if (has(SALUTE_KEYWORDS)) {
    return { emotion: "enthusiastic", gesture: "salute", intensity: 0.95, gestureDurationMs: 3200 };
  }

  // Priority 3: Laughing / Humor / Lelucon Eksplisit — klip animasi Laughing
  if (has(LAUGH_KEYWORDS)) {
    return { emotion: "laughing", gesture: "joy", intensity: 0.95, gestureDurationMs: 4000 };
  }

  // Priority 3: Angry / Annoyed / Marah — klip animasi Angry
  if (has(ANGRY_KEYWORDS)) {
    return { emotion: "angry", gesture: "angry", intensity: 0.95, gestureDurationMs: 3500 };
  }

  // Priority 4: Sad / Disappointed / Menangis — klip animasi Crying
  if (has(SAD_KEYWORDS)) {
    return { emotion: "sad", gesture: "sad", intensity: 0.85, gestureDurationMs: 3500 };
  }

  // Priority 5: Shy / Embarrassed / Malu / Pujian
  if (has(SHY_KEYWORDS)) {
    return { emotion: "shy", gesture: "shy", intensity: 0.90, gestureDurationMs: 2800 };
  }

  // Priority 6: Facepalm / Disbelief / Kaget — klip animasi Terrified
  if (has(FACEPALM_KEYWORDS)) {
    return { emotion: "surprised", gesture: "facepalm", intensity: 0.8, gestureDurationMs: 2800 };
  }

  // Priority 7: Greeting — sapaan ramah (bicara normal + senyum)
  if (has(GREETING_KEYWORDS)) {
    return { emotion: "happy", gesture: "wave", intensity: 0.90, gestureDurationMs: 2800 };
  }

  // Priority 8: Joy / Mantap / Hebat (bicara normal + senyum)
  if (has(JOY_KEYWORDS)) {
    return { emotion: "happy", gesture: "joy", intensity: 0.85, gestureDurationMs: 2600 };
  }

  // Priority 9: Empathy / Apology
  if (has(EMPATHY_KEYWORDS)) {
    return { emotion: "empathetic", gesture: "empathy", intensity: 0.80, gestureDurationMs: 2800 };
  }

  // Priority 10: Thinking / Analysis
  if (has(THINKING_KEYWORDS)) {
    return { emotion: "thinking", gesture: "think", intensity: 0.85, gestureDurationMs: 2800 };
  }

  // Priority 11: Agreement — angguk (bicara normal)
  if (AGREEMENT_KEYWORDS.some((kw) => cleanText.startsWith(kw) || cleanText.includes(` ${kw}`))) {
    return { emotion: "neutral", gesture: "nod", intensity: 0.8, gestureDurationMs: 2200 };
  }

  // Priority 12: Disagreement — geleng (bicara normal)
  if (has(DISAGREEMENT_KEYWORDS)) {
    return { emotion: "neutral", gesture: "shake", intensity: 0.7, gestureDurationMs: 2200 };
  }

  // Priority 12: Questions
  if (cleanText.includes("?") || has(QUESTION_KEYWORDS)) {
    return { emotion: "curious", gesture: "question", intensity: 0.75, gestureDurationMs: 2400 };
  }

  // Priority 13: Explaining
  if (has(EXPLAINING_KEYWORDS)) {
    return { emotion: "neutral", gesture: "explain", intensity: 0.75, gestureDurationMs: 2600 };
  }

  // Default: conversational explaining
  return { emotion: "neutral", gesture: "explain", intensity: 0.6, gestureDurationMs: 2400 };
}
