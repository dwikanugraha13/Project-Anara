"use client";

/**
 * danceMusic.ts
 *
 * Ultra-crisp, zero-latency Latin Rumba & Salsa dance groove synthesizer
 * built natively with the Web Audio API.
 *
 * Generates:
 * - Upbeat Brass / Horn fanfare intro stab
 * - Authentic 3-2 Son Clave percussion pattern
 * - Latin Tumbao syncopated bassline
 * - Salsa / Rumba Piano Montuno chord progression
 * - Crisp Maracas / Shaker 16th note groove
 * - Conga / Bongo acoustic resonant drum taps
 * - Smooth master envelope with auto fade-out
 */

export interface ActiveDanceMusic {
  stop: () => void;
}

/**
 * Synthesizes and plays a rich 6.5s Latin Rumba dance track via Web Audio API.
 */
export function playDanceMusic(audioContext: AudioContext, durationSeconds: number = 7.0): ActiveDanceMusic {
  if (audioContext.state === "suspended") {
    audioContext.resume().catch(() => {});
  }

  const now = audioContext.currentTime + 0.05;
  const masterGain = audioContext.createGain();
  masterGain.gain.setValueAtTime(0.001, now);
  masterGain.gain.exponentialRampToValueAtTime(0.85, now + 0.15);
  // Fade out smoothly at the end
  masterGain.gain.setValueAtTime(0.85, now + durationSeconds - 1.2);
  masterGain.gain.exponentialRampToValueAtTime(0.001, now + durationSeconds);

  masterGain.connect(audioContext.destination);

  const tempo = 124; // BPM (lively Rumba / Salsa tempo)
  const beatSec = 60 / tempo;
  const sixteenth = beatSec / 4;
  const totalBeats = Math.floor(durationSeconds / beatSec);

  // ── 1. Brass / Horn Fanfare Intro ──────────────────────────────────────────
  const fanfareNotes = [523.25, 659.25, 783.99, 880.0]; // C5, E5, G5, A5
  fanfareNotes.forEach((freq, idx) => {
    const osc = audioContext.createOscillator();
    const g = audioContext.createGain();
    osc.type = "sawtooth";
    osc.frequency.setValueAtTime(freq, now + idx * 0.09);

    const fTime = now + idx * 0.09;
    g.gain.setValueAtTime(0.001, fTime);
    g.gain.linearRampToValueAtTime(0.22, fTime + 0.03);
    g.gain.exponentialRampToValueAtTime(0.001, fTime + 0.45);

    // Lowpass filter for warm brass tone
    const filter = audioContext.createBiquadFilter();
    filter.type = "lowpass";
    filter.frequency.setValueAtTime(2800, fTime);
    filter.frequency.exponentialRampToValueAtTime(800, fTime + 0.45);

    osc.connect(filter);
    filter.connect(g);
    g.connect(masterGain);

    osc.start(fTime);
    osc.stop(fTime + 0.5);
  });

  // ── 2. Percussion Helpers ──────────────────────────────────────────────────

  // Conga / Bongo slap & open tone
  function playConga(time: number, isHigh: boolean = false) {
    const osc = audioContext.createOscillator();
    const g = audioContext.createGain();
    const baseFreq = isHigh ? 380 : 210;

    osc.type = "sine";
    osc.frequency.setValueAtTime(baseFreq * 1.5, time);
    osc.frequency.exponentialRampToValueAtTime(baseFreq, time + 0.08);

    g.gain.setValueAtTime(0.35, time);
    g.gain.exponentialRampToValueAtTime(0.001, time + 0.18);

    osc.connect(g);
    g.connect(masterGain);
    osc.start(time);
    osc.stop(time + 0.2);
  }

  // Clave Woodblock click
  function playClave(time: number) {
    const osc = audioContext.createOscillator();
    const g = audioContext.createGain();
    osc.type = "sine";
    osc.frequency.setValueAtTime(2200, time);
    osc.frequency.exponentialRampToValueAtTime(1400, time + 0.04);

    g.gain.setValueAtTime(0.28, time);
    g.gain.exponentialRampToValueAtTime(0.001, time + 0.045);

    osc.connect(g);
    g.connect(masterGain);
    osc.start(time);
    osc.stop(time + 0.05);
  }

  // Shaker / Maracas noise
  const bufferSize = audioContext.sampleRate * 0.06;
  const noiseBuffer = audioContext.createBuffer(1, bufferSize, audioContext.sampleRate);
  const output = noiseBuffer.getChannelData(0);
  for (let i = 0; i < bufferSize; i++) {
    output[i] = Math.random() * 2 - 1;
  }

  function playShaker(time: number, accent: boolean = false) {
    const whiteNoise = audioContext.createBufferSource();
    whiteNoise.buffer = noiseBuffer;

    const filter = audioContext.createBiquadFilter();
    filter.type = "highpass";
    filter.frequency.setValueAtTime(5500, time);

    const g = audioContext.createGain();
    g.gain.setValueAtTime(accent ? 0.25 : 0.12, time);
    g.gain.exponentialRampToValueAtTime(0.001, time + 0.05);

    whiteNoise.connect(filter);
    filter.connect(g);
    g.connect(masterGain);

    whiteNoise.start(time);
    whiteNoise.stop(time + 0.06);
  }

  // ── 3. Bassline (Latin Tumbao) ──────────────────────────────────────────────
  const bassNotes = [
    110.0, // A2
    130.81, // C3
    146.83, // D3
    164.81, // E3
    196.0,  // G3
  ];

  function playBass(time: number, freq: number, dur: number) {
    const osc = audioContext.createOscillator();
    const g = audioContext.createGain();
    osc.type = "triangle";
    osc.frequency.setValueAtTime(freq, time);

    g.gain.setValueAtTime(0.001, time);
    g.gain.linearRampToValueAtTime(0.42, time + 0.02);
    g.gain.exponentialRampToValueAtTime(0.001, time + dur);

    osc.connect(g);
    g.connect(masterGain);
    osc.start(time);
    osc.stop(time + dur + 0.05);
  }

  // ── 4. Piano Montuno Chords ────────────────────────────────────────────────
  const chordSets = [
    [440.0, 523.25, 659.25], // Am
    [392.0, 493.88, 587.33], // G
    [349.23, 440.0, 523.25], // F
    [329.63, 415.3, 493.88],  // E
  ];

  function playPianoChord(time: number, chordIdx: number) {
    const chord = chordSets[chordIdx % chordSets.length];
    chord.forEach((freq) => {
      const osc = audioContext.createOscillator();
      const g = audioContext.createGain();
      osc.type = "sawtooth";
      osc.frequency.setValueAtTime(freq, time);

      const filter = audioContext.createBiquadFilter();
      filter.type = "lowpass";
      filter.frequency.setValueAtTime(2200, time);
      filter.frequency.exponentialRampToValueAtTime(600, time + 0.28);

      g.gain.setValueAtTime(0.001, time);
      g.gain.linearRampToValueAtTime(0.16, time + 0.015);
      g.gain.exponentialRampToValueAtTime(0.001, time + 0.32);

      osc.connect(filter);
      filter.connect(g);
      g.connect(masterGain);

      osc.start(time);
      osc.stop(time + 0.35);
    });
  }

  // ── 5. Sequence the Rhythms over the Duration ──────────────────────────────
  const startGrooveTime = now + 0.35; // start groove right after fanfare

  // Schedule 16th note shakers
  const totalSixteenths = Math.floor((durationSeconds - 0.4) / sixteenth);
  for (let i = 0; i < totalSixteenths; i++) {
    const t = startGrooveTime + i * sixteenth;
    const isAccent = i % 4 === 0 || i % 4 === 2;
    playShaker(t, isAccent);
  }

  // Schedule Clave (3-2 Son Clave pattern in 8-beat cycles)
  const claveSteps = [0, 1.5, 3, 5, 6.5]; // 3-2 clave beats
  for (let measure = 0; measure < Math.ceil(totalBeats / 8); measure++) {
    const measureStart = startGrooveTime + measure * 8 * beatSec;
    claveSteps.forEach((beatOffset) => {
      const t = measureStart + beatOffset * beatSec;
      if (t < now + durationSeconds - 0.5) {
        playClave(t);
      }
    });
  }

  // Schedule Congas and Bass & Piano
  for (let beat = 0; beat < totalBeats; beat++) {
    const bTime = startGrooveTime + beat * beatSec;
    if (bTime >= now + durationSeconds - 0.4) break;

    const measurePos = beat % 8;

    // Conga accents on beats 2 & 4, and and-of-4
    if (measurePos % 2 === 1) {
      playConga(bTime, false);
      playConga(bTime + beatSec * 0.5, true);
    } else {
      playConga(bTime, true);
    }

    // Piano Montuno syncopation (on upbeat offbeats)
    const chordIdx = Math.floor(beat / 2) % chordSets.length;
    playPianoChord(bTime + beatSec * 0.25, chordIdx);
    playPianoChord(bTime + beatSec * 0.75, chordIdx);

    // Tumbao Bassline (anticipates downbeats on the 'and' of beat 2 and beat 4)
    const bassNote = bassNotes[chordIdx % bassNotes.length];
    if (measurePos === 0) {
      playBass(bTime, bassNote, beatSec * 0.7);
    } else if (measurePos === 2) {
      playBass(bTime, bassNote * 1.33, beatSec * 0.7);
    } else if (measurePos === 4) {
      playBass(bTime, bassNote * 1.5, beatSec * 0.8);
    }
  }

  return {
    stop: () => {
      try {
        const stopTime = audioContext.currentTime;
        const currentGain = Math.max(0.001, masterGain.gain.value);
        masterGain.gain.cancelScheduledValues(stopTime);
        masterGain.gain.setValueAtTime(currentGain, stopTime);
        masterGain.gain.exponentialRampToValueAtTime(0.0001, stopTime + 0.4);
        setTimeout(() => {
          try {
            masterGain.disconnect();
          } catch {}
        }, 450);
      } catch {}
    },
  };
}
