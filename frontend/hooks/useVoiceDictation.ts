"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { getBackendUrl } from "@/lib/apiClient";

export type DictationStatus = "idle" | "recording" | "transcribing";

export interface UseVoiceDictationOptions {
  onTranscriptUpdate?: (text: string) => void;
  lang?: string;
  maxRecordingSeconds?: number;
}

export function useVoiceDictation({
  onTranscriptUpdate,
  lang = "id-ID",
  maxRecordingSeconds = 120,
}: UseVoiceDictationOptions = {}) {
  const [status, setStatus] = useState<DictationStatus>("idle");
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [level, setLevel] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const statusRef = useRef<DictationStatus>("idle");
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const intervalTimerRef = useRef<number | null>(null);
  const timeoutTimerRef = useRef<number | null>(null);
  const baseTextRef = useRef<string>("");
  const recognitionRef = useRef<any>(null);

  const onTranscriptUpdateRef = useRef(onTranscriptUpdate);
  onTranscriptUpdateRef.current = onTranscriptUpdate;

  const cleanupAudio = useCallback(() => {
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
      animationFrameRef.current = null;
    }
    if (intervalTimerRef.current) {
      clearInterval(intervalTimerRef.current);
      intervalTimerRef.current = null;
    }
    if (timeoutTimerRef.current) {
      clearTimeout(timeoutTimerRef.current);
      timeoutTimerRef.current = null;
    }

    if (recognitionRef.current) {
      try {
        recognitionRef.current.abort();
      } catch {}
      recognitionRef.current = null;
    }

    if (audioContextRef.current && audioContextRef.current.state !== "closed") {
      try {
        audioContextRef.current.close();
      } catch {}
      audioContextRef.current = null;
    }

    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((track) => track.stop());
      mediaStreamRef.current = null;
    }

    analyserRef.current = null;
    mediaRecorderRef.current = null;
    setLevel(0);
  }, []);

  const cancelDictation = useCallback(() => {
    statusRef.current = "idle";
    setStatus("idle");
    cleanupAudio();
  }, [cleanupAudio]);

  const stopDictation = useCallback(async () => {
    if (statusRef.current !== "recording") {
      cancelDictation();
      return;
    }

    statusRef.current = "transcribing";
    setStatus("transcribing");

    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
      animationFrameRef.current = null;
    }
    if (intervalTimerRef.current) {
      clearInterval(intervalTimerRef.current);
      intervalTimerRef.current = null;
    }
    if (timeoutTimerRef.current) {
      clearTimeout(timeoutTimerRef.current);
      timeoutTimerRef.current = null;
    }

    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch {}
    }

    const recorder = mediaRecorderRef.current;
    let audioBlob: Blob | null = null;

    if (recorder && recorder.state !== "inactive") {
      audioBlob = await new Promise<Blob | null>((resolve) => {
        recorder.onstop = () => {
          const finalChunks = audioChunksRef.current;
          const mimeType = recorder.mimeType || "audio/webm";
          if (finalChunks.length > 0) {
            resolve(new Blob(finalChunks, { type: mimeType }));
          } else {
            resolve(null);
          }
        };
        try {
          recorder.stop();
        } catch {
          resolve(null);
        }
      });
    } else if (audioChunksRef.current.length > 0) {
      audioBlob = new Blob(audioChunksRef.current, { type: "audio/webm" });
    }

    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((track) => track.stop());
      mediaStreamRef.current = null;
    }

    if (!audioBlob || audioBlob.size < 64) {
      cleanupAudio();
      statusRef.current = "idle";
      setStatus("idle");
      return;
    }

    try {
      const reader = new FileReader();
      const base64Data = await new Promise<string>((resolve, reject) => {
        reader.onloadend = () => {
          const res = reader.result as string;
          const commaIdx = res.indexOf(",");
          resolve(commaIdx !== -1 ? res.slice(commaIdx + 1) : res);
        };
        reader.onerror = reject;
        reader.readAsDataURL(audioBlob);
      });

      const mime = audioBlob.type || "audio/webm";
      const cleanFormat = mime.includes("ogg")
        ? "ogg"
        : mime.includes("mp4") || mime.includes("m4a")
        ? "mp4"
        : mime.includes("wav")
        ? "wav"
        : "webm";

      const backendUrl = getBackendUrl();
      const resp = await fetch(`${backendUrl}/api/audio/transcribe`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          audio_base64: base64Data,
          format: cleanFormat,
          mime_type: mime,
        }),
      });

      if (resp.ok) {
        const json = await resp.json();
        const transcript = (json?.transcript || "").trim();
        if (transcript) {
          const prefix = baseTextRef.current;
          const fullText = prefix ? `${prefix} ${transcript}` : transcript;
          onTranscriptUpdateRef.current?.(fullText);
        }
      } else {
        console.warn("[VoiceDictation] Backend STT returned status:", resp.status);
      }
    } catch (err: any) {
      console.warn("[VoiceDictation] Transcription error:", err);
      setError(err?.message || "Transcription failed");
    } finally {
      cleanupAudio();
      statusRef.current = "idle";
      setStatus("idle");
    }
  }, [cancelDictation, cleanupAudio]);

  const startDictation = useCallback(
    async (initialText: string = "") => {
      if (typeof window === "undefined") return;

      cleanupAudio();
      baseTextRef.current = initialText ? initialText.trim() : "";
      audioChunksRef.current = [];
      setError(null);
      setElapsedSeconds(0);
      setLevel(0);

      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: {
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true,
          },
        });
        mediaStreamRef.current = stream;

        const AudioContextCtor = window.AudioContext || (window as any).webkitAudioContext;
        if (AudioContextCtor) {
          try {
            const audioCtx = new AudioContextCtor();
            audioContextRef.current = audioCtx;
            const analyser = audioCtx.createAnalyser();
            analyser.fftSize = 256;
            analyser.smoothingTimeConstant = 0.5;
            analyserRef.current = analyser;

            const source = audioCtx.createMediaStreamSource(stream);
            source.connect(analyser);

            const buffer = new Uint8Array(analyser.frequencyBinCount);
            const updateLevel = () => {
              if (!analyserRef.current || statusRef.current !== "recording") return;
              analyserRef.current.getByteFrequencyData(buffer);
              let sum = 0;
              for (let i = 0; i < buffer.length; i++) {
                sum += buffer[i];
              }
              const avg = sum / (buffer.length * 255);
              setLevel(avg);
              animationFrameRef.current = requestAnimationFrame(updateLevel);
            };
            animationFrameRef.current = requestAnimationFrame(updateLevel);
          } catch (ctxErr) {
            console.debug("[VoiceDictation] AudioContext meter notice:", ctxErr);
          }
        }

        const mimeTypes = [
          "audio/webm;codecs=opus",
          "audio/webm",
          "audio/ogg;codecs=opus",
          "audio/mp4",
        ];
        let supportedMime = "audio/webm";
        for (const m of mimeTypes) {
          if (MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported(m)) {
            supportedMime = m;
            break;
          }
        }

        const recorder = new MediaRecorder(stream, { mimeType: supportedMime });
        mediaRecorderRef.current = recorder;

        recorder.ondataavailable = (e) => {
          if (e.data && e.data.size > 0) {
            audioChunksRef.current.push(e.data);
          }
        };

        recorder.start(250);

        statusRef.current = "recording";
        setStatus("recording");

        const startTime = Date.now();
        intervalTimerRef.current = window.setInterval(() => {
          const sec = Math.floor((Date.now() - startTime) / 1000);
          setElapsedSeconds(sec);
        }, 250);

        timeoutTimerRef.current = window.setTimeout(() => {
          void stopDictation();
        }, maxRecordingSeconds * 1000);

        const SpeechRecognitionCtor =
          (window as any).SpeechRecognition ?? (window as any).webkitSpeechRecognition;
        if (SpeechRecognitionCtor) {
          try {
            const recognition = new SpeechRecognitionCtor();
            recognitionRef.current = recognition;
            recognition.lang = lang;
            recognition.continuous = true;
            recognition.interimResults = true;
            recognition.maxAlternatives = 1;

            recognition.onresult = (e: any) => {
              let text = "";
              for (let i = 0; i < e.results.length; i++) {
                text += (text ? " " : "") + (e.results[i][0]?.transcript || "").trim();
              }
              if (text.trim()) {
                const prefix = baseTextRef.current;
                const full = prefix ? `${prefix} ${text.trim()}` : text.trim();
                onTranscriptUpdateRef.current?.(full);
              }
            };
            recognition.onerror = () => {};
            recognition.start();
          } catch {}
        }
      } catch (err: any) {
        console.warn("[VoiceDictation] Could not start microphone:", err);
        setError(err?.message || "Microphone access denied");
        cleanupAudio();
        statusRef.current = "idle";
        setStatus("idle");
      }
    },
    [cleanupAudio, lang, maxRecordingSeconds, stopDictation]
  );

  const toggleDictation = useCallback(
    (currentText: string = "") => {
      if (statusRef.current === "recording") {
        void stopDictation();
      } else if (statusRef.current === "idle") {
        void startDictation(currentText);
      }
    },
    [startDictation, stopDictation]
  );

  useEffect(() => {
    return () => cleanupAudio();
  }, [cleanupAudio]);

  return {
    status,
    isDictating: status !== "idle",
    isRecording: status === "recording",
    isTranscribing: status === "transcribing",
    elapsedSeconds,
    level,
    error,
    startDictation,
    stopDictation,
    cancelDictation,
    toggleDictation,
  };
}
