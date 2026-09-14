"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import { BACKEND_URL, Speaker, CALIBRATION_WORKLET_CODE } from "../types";

interface BrainSpeakersTabProps {
  activeSpeaker?: string | null;
  onRefreshAll?: () => void;
}

export default function BrainSpeakersTab({
  activeSpeaker,
  onRefreshAll,
}: BrainSpeakersTabProps) {
  const [speakers, setSpeakers] = useState<Speaker[]>([]);
  const [isAddSpeakerOpen, setIsAddSpeakerOpen] = useState(false);
  const [newSpeakerInput, setNewSpeakerInput] = useState("");

  // Calibration State
  const [isCalibrating, setIsCalibrating] = useState(false);
  const [calibratingSpeaker, setCalibratingSpeaker] = useState<string | null>(null);
  const [calibrationCountdown, setCalibrationCountdown] = useState<number | null>(null);
  const [calibrationStatusText, setCalibrationStatusText] = useState<string | null>(null);

  const fetchSpeakers = useCallback(async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/brain/speakers`);
      if (res.ok) {
        const data = await res.json();
        setSpeakers(data || []);
      }
    } catch {}
  }, []);

  useEffect(() => {
    fetchSpeakers();
  }, [fetchSpeakers]);

  const handleSaveSpeaker = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newSpeakerInput.trim()) return;
    try {
      const res = await fetch(`${BACKEND_URL}/api/brain/speakers`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: newSpeakerInput.trim() }),
      });
      if (res.ok) {
        setIsAddSpeakerOpen(false);
        setNewSpeakerInput("");
        fetchSpeakers();
        onRefreshAll?.();
      }
    } catch (err) {
      console.error("Save speaker error:", err);
    }
  };

  const handleDeleteSpeaker = async (speakerName: string) => {
    if (!confirm(`Hapus profil pembicara "${speakerName}" beserta seluruh ingatan dan data terkait?`)) return;
    try {
      const res = await fetch(`${BACKEND_URL}/api/brain/speakers/${encodeURIComponent(speakerName)}`, {
        method: "DELETE",
      });
      if (res.ok) {
        fetchSpeakers();
        onRefreshAll?.();
      }
    } catch (err) {
      console.error("Delete speaker error:", err);
    }
  };

  const handleSelectActiveSpeaker = (speakerName: string) => {
    window.dispatchEvent(
      new CustomEvent("anara-set-active-speaker", {
        detail: { name: speakerName },
      })
    );
  };

  const buildCalibrationPrompts = (name: string): string[] => [
    `Halo Anara, namaku ${name}, senang berkenalan denganmu.`,
    "Cuaca hari ini sangat cerah, aku ingin minum segelas kopi hangat.",
    "Teknologi kecerdasan buatan berkembang sangat pesat belakangan ini.",
  ];

  const convertFloatChunksToBase64Pcm16 = (
    chunks: Float32Array[],
    nativeSampleRate: number
  ): string => {
    const targetSampleRate = 16000;
    const totalLen = chunks.reduce((acc, c) => acc + c.length, 0);
    const mergedFloat = new Float32Array(totalLen);
    let off = 0;
    for (const c of chunks) {
      mergedFloat.set(c, off);
      off += c.length;
    }

    let pcm16: Int16Array;
    if (Math.abs(nativeSampleRate - targetSampleRate) < 100) {
      pcm16 = new Int16Array(mergedFloat.length);
      for (let i = 0; i < mergedFloat.length; i++) {
        const s = Math.max(-1, Math.min(1, mergedFloat[i]));
        pcm16[i] = s < 0 ? s * 32768 : s * 32767;
      }
    } else {
      const ratio = nativeSampleRate / targetSampleRate;
      const targetLen = Math.round(mergedFloat.length / ratio);
      pcm16 = new Int16Array(targetLen);
      for (let i = 0; i < targetLen; i++) {
        const srcIdx = i * ratio;
        const i0 = Math.floor(srcIdx);
        const i1 = Math.min(i0 + 1, mergedFloat.length - 1);
        const frac = srcIdx - i0;
        const s = mergedFloat[i0] * (1 - frac) + mergedFloat[i1] * frac;
        const clamped = Math.max(-1, Math.min(1, s));
        pcm16[i] = clamped < 0 ? clamped * 32768 : clamped * 32767;
      }
    }

    const uint8 = new Uint8Array(pcm16.buffer);
    let binaryStr = "";
    const CHUNK = 8192;
    for (let i = 0; i < uint8.length; i += CHUNK) {
      binaryStr += String.fromCharCode(...uint8.subarray(i, i + CHUNK));
    }
    return btoa(binaryStr);
  };

  const handleStartVoiceCalibration = async (speakerName: string) => {
    const ROUND_SECONDS = 4;
    const MAX_ATTEMPTS_PER_ROUND = 3;
    const prompts = buildCalibrationPrompts(speakerName);

    let stream: MediaStream | null = null;
    let audioCtx: AudioContext | null = null;
    try {
      setIsCalibrating(true);
      setCalibratingSpeaker(speakerName);
      setCalibrationStatusText("Menyiapkan mikrofon...");

      stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
      });

      // @ts-ignore
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      audioCtx = new AudioContextClass();
      const nativeSampleRate = audioCtx.sampleRate;

      const blob = new Blob([CALIBRATION_WORKLET_CODE], { type: "application/javascript" });
      const workletUrl = URL.createObjectURL(blob);
      await audioCtx.audioWorklet.addModule(workletUrl);
      URL.revokeObjectURL(workletUrl);

      const source = audioCtx.createMediaStreamSource(stream);
      const recorder = new AudioWorkletNode(audioCtx, "calibration-recorder");
      source.connect(recorder);

      let currentChunks: Float32Array[] = [];
      recorder.port.onmessage = (e: MessageEvent) => {
        if (e.data instanceof Float32Array) {
          currentChunks.push(e.data);
        }
      };

      for (let roundIdx = 0; roundIdx < prompts.length; roundIdx++) {
        let attempt = 0;
        let roundSuccess = false;

        while (attempt < MAX_ATTEMPTS_PER_ROUND && !roundSuccess) {
          attempt += 1;
          currentChunks = [];

          const promptText = prompts[roundIdx];
          const attemptNote = attempt > 1 ? ` (percobaan ${attempt})` : "";
          setCalibrationStatusText(`Ronde ${roundIdx + 1}/3${attemptNote}: Baca keras: "${promptText}"`);

          for (let sec = ROUND_SECONDS; sec > 0; sec--) {
            setCalibrationCountdown(sec);
            await new Promise((r) => setTimeout(r, 1000));
          }
          setCalibrationCountdown(null);

          const chunksSnapshot = currentChunks.slice();
          if (chunksSnapshot.length === 0) {
            setCalibrationStatusText(`Ronde ${roundIdx + 1}: Suara tidak tertangkap, mengulang...`);
            await new Promise((r) => setTimeout(r, 1200));
            continue;
          }

          setCalibrationStatusText(`Ronde ${roundIdx + 1}: Menganalisis akustik sidik suara...`);
          const base64Audio = convertFloatChunksToBase64Pcm16(chunksSnapshot, nativeSampleRate);

          try {
            const res = await fetch(`${BACKEND_URL}/api/brain/speakers/${encodeURIComponent(speakerName)}/calibrate`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ audio_base64: base64Audio }),
            });
            const data = await res.json();
            if (data.status === "success") {
              roundSuccess = true;
              setCalibrationStatusText(`✓ Ronde ${roundIdx + 1}/3 berhasil direkam!`);
              await new Promise((r) => setTimeout(r, 1000));
            } else {
              setCalibrationStatusText(`Ronde ${roundIdx + 1} gagal. Mengulang...`);
              await new Promise((r) => setTimeout(r, 1200));
            }
          } catch {
            setCalibrationStatusText(`Ronde ${roundIdx + 1} gagal kirim. Mengulang...`);
            await new Promise((r) => setTimeout(r, 1200));
          }
        }
      }

      setCalibrationStatusText(`✓ Kalibrasi 3-ronde selesai untuk ${speakerName}!`);
      await new Promise((r) => setTimeout(r, 1600));
      fetchSpeakers();
      onRefreshAll?.();
    } catch (err: any) {
      console.error("Calibration error:", err);
      alert(`Kalibrasi gagal: ${err?.message || "Tidak dapat mengakses mikrofon"}`);
    } finally {
      if (stream) stream.getTracks().forEach((t) => t.stop());
      if (audioCtx && audioCtx.state !== "closed") {
        try {
          audioCtx.close();
        } catch {}
      }
      setIsCalibrating(false);
      setCalibratingSpeaker(null);
      setCalibrationCountdown(null);
      setCalibrationStatusText(null);
    }
  };

  return (
    <div className="space-y-5">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 p-5 rounded-2xl liquid-glass-subtle text-xs text-slate-300">
        <div>
          <span className="text-cyan-300 font-semibold uppercase tracking-wider text-[11px] flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-ping" />
            Engine Biometrik Sidik Suara 128-D
          </span>
          <p className="mt-1.5 leading-relaxed text-slate-400">
            Sistem mengekstrak vektor MFCC, pitch F0, dan formants dari audio mikrofon secara real-time untuk mengenali pembicara dari database tanpa jeda.
          </p>
        </div>
        <button
          onClick={() => setIsAddSpeakerOpen(true)}
          className="px-4 py-2.5 rounded-2xl bg-gradient-to-r from-cyan-500 to-indigo-500 text-white text-xs font-semibold shadow-[0_4px_20px_rgba(34,211,238,0.3)] transition-all flex items-center gap-2 cursor-pointer shrink-0 hover:opacity-90"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          Tambah Profil
        </button>
      </div>

      {/* Live Calibration Banner Modal */}
      {isCalibrating && (
        <div className="p-4 rounded-2xl liquid-glass border border-cyan-400/40 shadow-[0_0_30px_rgba(34,211,238,0.2)] animate-fade-in flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-cyan-500/20 border border-cyan-400/40 flex items-center justify-center text-cyan-300">
              {calibrationCountdown !== null ? (
                <span className="font-mono font-bold text-lg">{calibrationCountdown}</span>
              ) : (
                <svg className="w-5 h-5 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
                </svg>
              )}
            </div>
            <div className="min-w-0">
              <h4 className="text-xs font-bold text-white uppercase tracking-wide">
                Kalibrasi Multi-Ronde: {calibratingSpeaker}
              </h4>
              <p className="text-xs text-cyan-300 mt-0.5">{calibrationStatusText}</p>
            </div>
          </div>
          <span className="text-[11px] text-cyan-300/90 bg-cyan-500/10 px-3 py-1.5 rounded-lg border border-cyan-400/25 hidden sm:inline shrink-0">
            3 Sampel • 16kHz
          </span>
        </div>
      )}

      {/* Add Speaker Modal */}
      {isAddSpeakerOpen && (
        <div className="p-5 rounded-2xl liquid-glass space-y-4 animate-fade-in">
          <div className="flex items-center justify-between border-b border-white/10 pb-3">
            <h4 className="text-sm font-bold text-white flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-cyan-400" />
              Daftarkan Profil Pembicara Baru
            </h4>
            <button
              onClick={() => setIsAddSpeakerOpen(false)}
              className="text-slate-400 hover:text-white p-1 cursor-pointer"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          <form onSubmit={handleSaveSpeaker} className="space-y-4">
            <div>
              <label className="block text-xs text-slate-400 mb-1.5 uppercase tracking-wider">
                Nama Pembicara (Contoh: Agnan, Sarah, Budi)
              </label>
              <input
                type="text"
                required
                value={newSpeakerInput}
                onChange={(e) => setNewSpeakerInput(e.target.value)}
                placeholder="Ketik nama pembicara..."
                className="w-full liquid-glass-input rounded-xl px-4 py-2.5 text-white text-xs placeholder-slate-500 focus:outline-none"
              />
            </div>
            <div className="flex justify-end gap-2.5 pt-1">
              <button
                type="button"
                onClick={() => setIsAddSpeakerOpen(false)}
                className="px-4 py-2 rounded-xl liquid-glass-subtle border border-white/10 text-slate-300 text-xs cursor-pointer"
              >
                Batal
              </button>
              <button
                type="submit"
                className="px-4 py-2 rounded-xl bg-gradient-to-r from-cyan-500 to-indigo-500 text-white text-xs font-semibold shadow-[0_4px_16px_rgba(34,211,238,0.3)] cursor-pointer hover:opacity-90"
              >
                Simpan Profil
              </button>
            </div>
          </form>
        </div>
      )}

      {speakers.length === 0 ? (
        <div className="py-12 px-6 rounded-2xl border border-dashed border-white/15 liquid-glass-subtle text-center space-y-3">
          <div className="w-12 h-12 rounded-2xl bg-cyan-500/10 border border-cyan-400/25 flex items-center justify-center mx-auto text-cyan-300">
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
            </svg>
          </div>
          <h4 className="text-sm font-semibold text-white">Belum Ada Profil Terdaftar</h4>
          <p className="text-xs text-slate-400 max-w-md mx-auto leading-relaxed">
            Klik tombol <strong className="text-cyan-300">Tambah Profil</strong> di atas atau perkenalkan nama Anda secara langsung melalui mikrofon untuk membuat profil baru.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
          {speakers.map((sp) => {
            const isActive = Boolean(activeSpeaker && sp.name.toLowerCase() === activeSpeaker.toLowerCase());
            const hasEmbedding = Boolean(sp.has_voice_embedding || (sp.sample_count && sp.sample_count > 0));
            return (
              <div
                key={sp.id}
                className={`p-5 rounded-2xl border transition-all duration-300 flex flex-col justify-between relative group ${
                  isActive
                    ? "liquid-glass border-emerald-400/50 shadow-[0_0_30px_rgba(52,211,153,0.15)]"
                    : "liquid-glass-subtle hover:border-cyan-400/35"
                }`}
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3.5 min-w-0">
                    <div className={`w-11 h-11 rounded-2xl flex items-center justify-center font-semibold text-white text-sm shrink-0 border ${
                      isActive
                        ? "bg-gradient-to-tr from-emerald-500/40 to-teal-400/40 border-emerald-300/50 shadow-[0_0_15px_rgba(52,211,153,0.3)]"
                        : "bg-gradient-to-tr from-indigo-500/40 via-purple-500/30 to-cyan-400/40 border-white/20"
                    }`}>
                      {sp.name.slice(0, 2).toUpperCase()}
                    </div>
                    <div className="min-w-0">
                      <h4 className="text-sm font-bold text-white uppercase tracking-wide flex items-center gap-2 truncate">
                        {sp.name}
                        {isActive && (
                          <span className="w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_8px_#34d399] animate-pulse shrink-0" />
                        )}
                      </h4>
                      <div className="flex items-center gap-2 mt-1">
                        {hasEmbedding ? (
                          <span className="text-[11px] text-emerald-300 flex items-center gap-1">
                            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                            </svg>
                            {sp.sample_count || 1} Sampel Terkalibrasi
                            {(sp.sample_count || 1) >= 30 && (
                              <span className="ml-1 px-1.5 py-0.5 rounded-md text-[9px] font-bold uppercase tracking-wider bg-emerald-400/15 border border-emerald-400/40 text-emerald-200">
                                Matang
                              </span>
                            )}
                          </span>
                        ) : (
                          <span className="text-[11px] text-amber-300/90 flex items-center gap-1">
                            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                            </svg>
                            Belum Ada Sidik Suara
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <span className={`px-2.5 py-1 rounded-full text-[10px] font-semibold ${
                      isActive 
                        ? "bg-emerald-500/15 text-emerald-300 border border-emerald-400/35" 
                        : "liquid-glass-subtle text-slate-400 border border-white/10"
                    }`}>
                      {isActive ? "Aktif" : "Tersimpan"}
                    </span>
                    <button
                      onClick={() => handleDeleteSpeaker(sp.name)}
                      className="text-slate-500 hover:text-rose-400 p-1.5 rounded-lg hover:bg-rose-500/10 transition-all cursor-pointer opacity-0 group-hover:opacity-100"
                      title={`Hapus profil ${sp.name}`}
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                    </button>
                  </div>
                </div>

                {/* Action Bar for Voice Calibration & Activation */}
                <div className="mt-4 pt-3 border-t border-white/[0.07] flex items-center justify-between gap-2 flex-wrap">
                  <button
                    onClick={() => handleStartVoiceCalibration(sp.name)}
                    disabled={isCalibrating}
                    className="px-3 py-1.5 rounded-xl bg-cyan-500/10 hover:bg-cyan-500/20 border border-cyan-400/30 text-cyan-200 text-xs font-medium flex items-center gap-1.5 transition-all cursor-pointer disabled:opacity-50"
                  >
                    <svg className="w-3.5 h-3.5 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
                    </svg>
                    {hasEmbedding ? "Rekalibrasi (3×)" : "Kalibrasi (3×)"}
                  </button>

                  {!isActive && (
                    <button
                      onClick={() => handleSelectActiveSpeaker(sp.name)}
                      className="px-3 py-1.5 rounded-xl liquid-glass-subtle hover:bg-emerald-500/15 hover:border-emerald-400/35 border border-white/10 text-slate-300 hover:text-emerald-200 text-xs transition-all cursor-pointer"
                    >
                      Pilih Aktif
                    </button>
                  )}
                </div>

                <div className="mt-3 pt-2.5 border-t border-white/[0.05] flex items-center justify-between text-[11px] text-slate-500">
                  <span>{sp.memory_count} Node Fakta</span>
                  <span>Terakhir: {new Date(sp.last_seen).toLocaleDateString("id-ID")}</span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
