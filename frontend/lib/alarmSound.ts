"use client";

/**
 * alarmSound.ts
 *
 * Zero-latency alarm / timer chime synthesizer built natively with the Web Audio API.
 * No external audio files needed — everything is generated on the fly.
 *
 * Variants:
 * - "gentle" : soft ascending marimba-like bells (wake-up alarms)
 * - "urgent" : bright triple beep bursts with a hint of dissonance (cooking timers)
 * - "notify" : single short two-tone ping (reminders)
 */

export type AlarmVariant = "gentle" | "urgent" | "notify";

export interface ActiveAlarm {
  stop: () => void;
  variant: AlarmVariant;
}

interface BellOptions {
  freq: number;
  start: number;
  duration: number;
  gain: number;
  type?: OscillatorType;
  detuneCents?: number;
}

/** Schedules a single resonant bell tone (fundamental + shimmer partial). */
function scheduleBell(ctx: AudioContext, master: GainNode, opts: BellOptions) {
  const { freq, start, duration, gain, type = "sine", detuneCents = 0 } = opts;

  const env = ctx.createGain();
  env.gain.setValueAtTime(0.0001, start);
  env.gain.exponentialRampToValueAtTime(gain, start + 0.012);
  env.gain.exponentialRampToValueAtTime(0.0001, start + duration);
  env.connect(master);

  const osc = ctx.createOscillator();
  osc.type = type;
  osc.frequency.setValueAtTime(freq, start);
  if (detuneCents) osc.detune.setValueAtTime(detuneCents, start);
  osc.connect(env);
  osc.start(start);
  osc.stop(start + duration + 0.05);

  // Shimmer partial (2 octaves up) gives the metallic bell character
  const partialEnv = ctx.createGain();
  partialEnv.gain.setValueAtTime(0.0001, start);
  partialEnv.gain.exponentialRampToValueAtTime(gain * 0.22, start + 0.008);
  partialEnv.gain.exponentialRampToValueAtTime(0.0001, start + duration * 0.55);
  partialEnv.connect(master);

  const partial = ctx.createOscillator();
  partial.type = "triangle";
  partial.frequency.setValueAtTime(freq * 4, start);
  partial.connect(partialEnv);
  partial.start(start);
  partial.stop(start + duration * 0.6 + 0.05);
}

/**
 * Plays an alarm chime. Returns a handle so the caller can stop it early
 * (e.g. when the user presses "Hentikan").
 */
export function playAlarmChime(
  audioContext: AudioContext,
  variant: AlarmVariant = "urgent",
  onEnded?: () => void
): ActiveAlarm {
  if (audioContext.state === "suspended") {
    audioContext.resume().catch(() => {});
  }

  const master = audioContext.createGain();
  master.gain.setValueAtTime(0.0001, audioContext.currentTime);
  master.gain.linearRampToValueAtTime(1.0, audioContext.currentTime + 0.02);
  master.connect(audioContext.destination);

  const t0 = audioContext.currentTime + 0.04;
  let totalDuration = 0;

  if (variant === "notify") {
    // Short two-tone ping (C6 -> G6)
    scheduleBell(audioContext, master, { freq: 1046.5, start: t0, duration: 0.35, gain: 0.5 });
    scheduleBell(audioContext, master, { freq: 1568.0, start: t0 + 0.16, duration: 0.5, gain: 0.42 });
    totalDuration = 0.9;
  } else if (variant === "gentle") {
    // Soft ascending marimba arpeggio, repeated 3x with breathing room
    const notes = [523.25, 659.25, 783.99, 1046.5]; // C5 E5 G5 C6
    const cycle = 2.2;
    const repeats = 3;
    for (let r = 0; r < repeats; r++) {
      const base = t0 + r * cycle;
      notes.forEach((f, i) => {
        scheduleBell(audioContext, master, {
          freq: f,
          start: base + i * 0.22,
          duration: 1.1,
          gain: 0.34,
          type: "sine",
        });
      });
    }
    totalDuration = repeats * cycle;
  } else {
    // "urgent": triple beep burst (C6/E6/G6 stab) repeated 3x — classic timer alert
    const cycle = 1.9;
    const repeats = 3;
    for (let r = 0; r < repeats; r++) {
      const base = t0 + r * cycle;
      for (let b = 0; b < 3; b++) {
        const bt = base + b * 0.2;
        scheduleBell(audioContext, master, { freq: 1046.5, start: bt, duration: 0.18, gain: 0.55, type: "square" });
        scheduleBell(audioContext, master, { freq: 1318.5, start: bt, duration: 0.16, gain: 0.3, type: "sine" });
      }
      // Resolving bell tail after the burst
      scheduleBell(audioContext, master, {
        freq: 1568.0,
        start: base + 0.68,
        duration: 0.85,
        gain: 0.4,
        type: "sine",
      });
    }
    totalDuration = repeats * cycle;
  }

  let stopped = false;
  const endTimer = setTimeout(() => {
    if (!stopped) onEnded?.();
  }, Math.ceil(totalDuration * 1000) + 120);

  const stop = () => {
    if (stopped) return;
    stopped = true;
    clearTimeout(endTimer);
    const now = audioContext.currentTime;
    try {
      master.gain.cancelScheduledValues(now);
      master.gain.setValueAtTime(Math.max(master.gain.value, 0.0001), now);
      master.gain.exponentialRampToValueAtTime(0.0001, now + 0.08);
      setTimeout(() => {
        try {
          master.disconnect();
        } catch {
          /* already disconnected */
        }
      }, 140);
    } catch {
      /* context may be closing */
    }
    onEnded?.();
  };

  return { stop, variant };
}
