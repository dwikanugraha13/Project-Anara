"use client";

import { useRef, useCallback, useState, useEffect } from "react";

export type MicrophoneStatus = "idle" | "requesting" | "active" | "error" | "denied";

// AudioWorklet processor code (inlined as string, loaded via Blob URL)
const WORKLET_CODE = `
class PCMProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this._inputSampleRate = sampleRate;
    this._targetSampleRate = 16000;
    this._ratio = this._inputSampleRate / this._targetSampleRate;
    this._chunkSize = 1600; // 100ms at 16kHz output (optimal for Gemini VAD)
    this._outputBuffer = new Int16Array(this._chunkSize);
    this._outputIndex = 0;
    this._fraction = 0;
    this._lastSample = 0;
  }

  process(inputs) {
    const input = inputs[0];
    if (!input || !input[0]) return true;

    const inputSamples = input[0];
    const len = inputSamples.length;

    // 1:1 direct conversion when native AudioContext runs at 16kHz
    if (Math.abs(this._ratio - 1.0) < 0.001) {
      for (let i = 0; i < len; i++) {
        const s = Math.max(-1, Math.min(1, inputSamples[i]));
        this._outputBuffer[this._outputIndex++] = s < 0 ? s * 32768 : s * 32767;

        if (this._outputIndex >= this._chunkSize) {
          const sendBuf = this._outputBuffer.slice().buffer;
          this.port.postMessage(sendBuf, [sendBuf]);
          this._outputIndex = 0;
        }
      }
    } else {
      // High-precision linear resampling fallback
      for (let i = 0; i < len; i++) {
        const current = inputSamples[i];
        this._fraction += 1.0;

        while (this._fraction >= this._ratio) {
          const alpha = Math.max(0, Math.min(1, 1.0 - (this._fraction - this._ratio)));
          const interpolated = this._lastSample + (current - this._lastSample) * alpha;

          const clamped = Math.max(-1, Math.min(1, interpolated));
          this._outputBuffer[this._outputIndex++] = clamped < 0 ? clamped * 32768 : clamped * 32767;

          if (this._outputIndex >= this._chunkSize) {
            const sendBuf = this._outputBuffer.slice().buffer;
            this.port.postMessage(sendBuf, [sendBuf]);
            this._outputIndex = 0;
          }

          this._fraction -= this._ratio;
        }

        this._lastSample = current;
      }
    }
    return true;
  }
}

registerProcessor('pcm-processor', PCMProcessor);
`;

interface UseMicrophoneOptions {
  onAudioChunk: (pcm16Buffer: ArrayBuffer) => void;
  onIntensityChange?: (intensity: number) => void;
  targetSampleRate?: number;
}

export function useMicrophone({
  onAudioChunk,
  onIntensityChange,
  targetSampleRate = 16000,
}: UseMicrophoneOptions) {
  const [status, setStatus] = useState<MicrophoneStatus>("idle");
  const [isMuted, setIsMuted] = useState(false);
  const isMutedRef = useRef(false);
  const streamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const workletNodeRef = useRef<AudioWorkletNode | null>(null);
  const sourceNodeRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const highPassNodeRef = useRef<BiquadFilterNode | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const animFrameRef = useRef<number | null>(null);

  const onIntensityChangeRef = useRef(onIntensityChange);
  useEffect(() => {
    onIntensityChangeRef.current = onIntensityChange;
  });

  const startListening = useCallback(async () => {
    if (status === "active") return;
    setStatus("requesting");

    try {
      // Request high-fidelity microphone access with browser speech enhancements
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });

      streamRef.current = stream;

      // Prefer native 16kHz AudioContext for pristine, uncompressed STT speech clarity
      let audioContext: AudioContext;
      try {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
        audioContext = new AudioCtx({ sampleRate: 16000 });
      } catch {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
        audioContext = new AudioCtx();
      }
      audioContextRef.current = audioContext;

      // Load AudioWorklet from Blob URL
      const blob = new Blob([WORKLET_CODE], { type: "application/javascript" });
      const workletUrl = URL.createObjectURL(blob);

      await audioContext.audioWorklet.addModule(workletUrl);
      URL.revokeObjectURL(workletUrl);

      // Create DSP audio processing nodes for clean STT
      const source = audioContext.createMediaStreamSource(stream);
      
      // Gentle Highpass filter (cuts sub-80Hz room rumble & desk thumps without altering speech formants)
      const highPass = audioContext.createBiquadFilter();
      highPass.type = "highpass";
      highPass.frequency.value = 80;
      highPass.Q.value = 0.707;

      const workletNode = new AudioWorkletNode(audioContext, "pcm-processor");
      const analyser = audioContext.createAnalyser();
      analyser.fftSize = 256;

      sourceNodeRef.current = source;
      highPassNodeRef.current = highPass;
      workletNodeRef.current = workletNode;
      analyserRef.current = analyser;

      // Ensure AudioContext is actively running
      if (audioContext.state === "suspended") {
        await audioContext.resume();
      }

      // Connect clean signal chain: source -> highPass -> workletNode -> silentGain -> destination
      // Connecting to destination via zero-gain node is CRITICAL in Chromium so the browser doesn't garbage-collect or pause the AudioWorklet!
      const silentGain = audioContext.createGain();
      silentGain.gain.value = 0;

      source.connect(highPass);
      highPass.connect(workletNode);
      workletNode.connect(silentGain);
      silentGain.connect(audioContext.destination);

      // Connect analyser for visual UI waveform feedback
      highPass.connect(analyser);

      const bufferLength = analyser.frequencyBinCount;
      const dataArray = new Uint8Array(bufferLength);
      let lastCheck = 0;
      let lastAverage = 0;

      const checkIntensity = (time: number) => {
        if (!analyserRef.current) return;

        // Throttle to every 60ms for smooth UI feedback
        if (time - lastCheck >= 60) {
          analyserRef.current.getByteFrequencyData(dataArray);
          let sum = 0;
          for (let i = 0; i < bufferLength; i++) {
            sum += dataArray[i];
          }
          const average = sum / bufferLength / 255;
          if (Math.abs(average - lastAverage) > 0.01 || (average === 0 && lastAverage > 0)) {
            lastAverage = average;
            onIntensityChangeRef.current?.(average);
          }
          lastCheck = time;
        }

        animFrameRef.current = requestAnimationFrame(checkIntensity);
      };
      animFrameRef.current = requestAnimationFrame(checkIntensity);

      // Receive PCM chunks from worklet with high-sensitivity speech detection
      const preRollBuffer: ArrayBuffer[] = [];
      let isSpeechActive = false;
      let lastSpeechTimestamp = 0;

      workletNode.port.onmessage = (event) => {
        if (isMutedRef.current) return;
        if (event.data instanceof ArrayBuffer) {
          const int16 = new Int16Array(event.data);
          let sumSq = 0;
          for (let i = 0; i < int16.length; i++) {
            const norm = int16[i] / 32768.0;
            sumSq += norm * norm;
          }
          const rms = Math.sqrt(sumSq / int16.length);
          const now = Date.now();

          // High sensitivity threshold (0.005) to catch all microphone types, whispered voices & quiet speakers
          if (rms >= 0.005) {
            if (!isSpeechActive) {
              isSpeechActive = true;
              // Flush pre-roll buffer so initial consonants are never cut off
              while (preRollBuffer.length > 0) {
                const pre = preRollBuffer.shift();
                if (pre) onAudioChunk(pre);
              }
            }
            lastSpeechTimestamp = now;
            onAudioChunk(event.data);
          } else if (isSpeechActive) {
            // Keep sending for 800ms hangover to preserve natural speech pauses
            if (now - lastSpeechTimestamp < 800) {
              onAudioChunk(event.data);
            } else {
              isSpeechActive = false;
            }
          } else {
            // Maintain rolling pre-roll buffer when silent
            preRollBuffer.push(event.data);
            if (preRollBuffer.length > 3) {
              preRollBuffer.shift();
            }
          }
        }
      };

      setStatus("active");
      console.log("[Microphone] Enhanced voice audio pipeline active at", targetSampleRate, "Hz");
    } catch (err) {
      console.error("[Microphone] Error:", err);
      if (err instanceof DOMException && err.name === "NotAllowedError") {
        setStatus("denied");
      } else {
        setStatus("error");
      }
    }
  }, [status, targetSampleRate, onAudioChunk, onIntensityChange]);

  const stopListening = useCallback(() => {
    if (animFrameRef.current) {
      cancelAnimationFrame(animFrameRef.current);
    }
    workletNodeRef.current?.disconnect();
    sourceNodeRef.current?.disconnect();
    analyserRef.current?.disconnect();

    streamRef.current?.getTracks().forEach((track) => track.stop());
    audioContextRef.current?.close();

    workletNodeRef.current = null;
    sourceNodeRef.current = null;
    analyserRef.current = null;
    streamRef.current = null;
    audioContextRef.current = null;

    setStatus("idle");
    onIntensityChange?.(0);
    console.log("[Microphone] Stopped");
  }, [onIntensityChange]);

  const toggleMute = useCallback(() => {
    setIsMuted((prev) => {
      const next = !prev;
      isMutedRef.current = next;
      return next;
    });
  }, []);

  const toggleListening = useCallback(() => {
    if (status === "active") {
      stopListening();
    } else {
      startListening();
    }
  }, [status, startListening, stopListening]);

  return { status, isMuted, startListening, stopListening, toggleListening, toggleMute };
}
