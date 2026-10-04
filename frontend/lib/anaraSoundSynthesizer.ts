"use client";

/**
 * anaraSoundSynthesizer.ts — Anara Native Web Audio Procedural Sound Synthesizer
 *
 * Provides zero-asset, zero-latency auditory feedback for:
 * - Task Completion Chime: Warm, comforting harmonic chime when agent finishes turn.
 * - Alert Chime: Gentle notification ding when approval or attention is required.
 * - Sound preferences management (mute toggle, volume).
 */

let sharedAudioCtx: AudioContext | null = null;

function getAudioContext(): AudioContext | null {
  if (typeof window === "undefined") return null;
  const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
  if (!AudioContextClass) return null;

  if (!sharedAudioCtx || sharedAudioCtx.state === "closed") {
    sharedAudioCtx = new AudioContextClass();
  }
  if (sharedAudioCtx.state === "suspended") {
    sharedAudioCtx.resume().catch(() => {});
  }
  return sharedAudioCtx;
}

export function isAnaraSoundMuted(): boolean {
  if (typeof window === "undefined") return false;
  return localStorage.getItem("anara_sound_muted") === "true";
}

export function setAnaraSoundMuted(muted: boolean): void {
  if (typeof window === "undefined") return;
  localStorage.setItem("anara_sound_muted", muted ? "true" : "false");
}

export function getAnaraSoundVolume(): number {
  if (typeof window === "undefined") return 0.5;
  const stored = localStorage.getItem("anara_sound_volume");
  if (!stored) return 0.5;
  const val = parseFloat(stored);
  return isNaN(val) ? 0.5 : Math.max(0, Math.min(1, val));
}

export function setAnaraSoundVolume(vol: number): void {
  if (typeof window === "undefined") return;
  localStorage.setItem("anara_sound_volume", String(Math.max(0, Math.min(1, vol))));
}

/**
 * Plays a procedural warm 2-note harmonic chime when agent completes a turn.
 * Note frequencies: E4 (329.63Hz) glide to C5 (523.25Hz) with harmonic shimmer.
 */
export function playAnaraCompletionChime(): void {
  if (isAnaraSoundMuted()) return;
  const ctx = getAudioContext();
  if (!ctx) return;

  const now = ctx.currentTime;
  const volume = getAnaraSoundVolume();

  const master = ctx.createGain();
  master.gain.setValueAtTime(volume * 0.45, now);
  master.connect(ctx.destination);

  // Note 1: E4 (329.63 Hz) at t = 0
  const env1 = ctx.createGain();
  env1.gain.setValueAtTime(0.0001, now);
  env1.gain.exponentialRampToValueAtTime(0.8, now + 0.015);
  env1.gain.exponentialRampToValueAtTime(0.0001, now + 0.35);
  env1.connect(master);

  const osc1 = ctx.createOscillator();
  osc1.type = "sine";
  osc1.frequency.setValueAtTime(329.63, now);
  osc1.connect(env1);
  osc1.start(now);
  osc1.stop(now + 0.4);

  // Note 2: C5 (523.25 Hz) at t = 0.12s with warm sub-bass C4 (261.63 Hz)
  const t2 = now + 0.12;
  const env2 = ctx.createGain();
  env2.gain.setValueAtTime(0.0001, t2);
  env2.gain.exponentialRampToValueAtTime(1.0, t2 + 0.015);
  env2.gain.exponentialRampToValueAtTime(0.0001, t2 + 0.65);
  env2.connect(master);

  const osc2 = ctx.createOscillator();
  osc2.type = "triangle";
  osc2.frequency.setValueAtTime(523.25, t2);
  osc2.connect(env2);
  osc2.start(t2);
  osc2.stop(t2 + 0.7);

  // Sub fundamental warmth
  const envSub = ctx.createGain();
  envSub.gain.setValueAtTime(0.0001, t2);
  envSub.gain.exponentialRampToValueAtTime(0.4, t2 + 0.02);
  envSub.gain.exponentialRampToValueAtTime(0.0001, t2 + 0.5);
  envSub.connect(master);

  const oscSub = ctx.createOscillator();
  oscSub.type = "sine";
  oscSub.frequency.setValueAtTime(261.63, t2);
  oscSub.connect(envSub);
  oscSub.start(t2);
  oscSub.stop(t2 + 0.55);
}

/**
 * Plays a soft attention alert chime (when action requires approval or attention).
 * Ascending interval G5 (783.99 Hz) to C6 (1046.5 Hz).
 */
export function playAnaraAlertChime(): void {
  if (isAnaraSoundMuted()) return;
  const ctx = getAudioContext();
  if (!ctx) return;

  const now = ctx.currentTime;
  const volume = getAnaraSoundVolume();

  const master = ctx.createGain();
  master.gain.setValueAtTime(volume * 0.4, now);
  master.connect(ctx.destination);

  // Tone 1
  const env1 = ctx.createGain();
  env1.gain.setValueAtTime(0.0001, now);
  env1.gain.exponentialRampToValueAtTime(0.7, now + 0.01);
  env1.gain.exponentialRampToValueAtTime(0.0001, now + 0.2);
  env1.connect(master);

  const osc1 = ctx.createOscillator();
  osc1.type = "sine";
  osc1.frequency.setValueAtTime(783.99, now);
  osc1.connect(env1);
  osc1.start(now);
  osc1.stop(now + 0.25);

  // Tone 2
  const t2 = now + 0.08;
  const env2 = ctx.createGain();
  env2.gain.setValueAtTime(0.0001, t2);
  env2.gain.exponentialRampToValueAtTime(0.9, t2 + 0.01);
  env2.gain.exponentialRampToValueAtTime(0.0001, t2 + 0.35);
  env2.connect(master);

  const osc2 = ctx.createOscillator();
  osc2.type = "sine";
  osc2.frequency.setValueAtTime(1046.5, t2);
  osc2.connect(env2);
  osc2.start(t2);
  osc2.stop(t2 + 0.4);
}
