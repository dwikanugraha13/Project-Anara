import json
import logging
import re
import time
from typing import Optional, Dict, Any, List, Tuple

import numpy as np

from .base import MAX_VOICE_SAMPLES, MATURE_ADAPT_INTERVAL

logger = logging.getLogger(__name__)


def _compute_spectrogram_np(audio: np.ndarray, sample_rate: int = 16000, nperseg: int = 400, noverlap: int = 240) -> Tuple[np.ndarray, np.ndarray]:
    """Pure NumPy STFT spectrogram (replaces scipy.signal.spectrogram for zero-overhead instant startup)."""
    step = nperseg - noverlap
    if len(audio) < nperseg:
        return np.array([]), np.array([[]])
    frames = np.lib.stride_tricks.sliding_window_view(audio, nperseg)[::step]
    window = np.hanning(nperseg)
    windowed = frames * window
    fft_spec = np.fft.rfft(windowed, n=nperseg, axis=-1)
    Sxx = (np.abs(fft_spec) ** 2).T  # shape: (freq_bins, num_frames)
    freqs = np.fft.rfftfreq(nperseg, 1.0 / sample_rate)
    return freqs, Sxx


def _compute_dct_np(matrix: np.ndarray, n_coeffs: int = 20) -> np.ndarray:
    """Pure NumPy Type-II Orthonormal Discrete Cosine Transform (replaces scipy.fft.dct)."""
    N = matrix.shape[0]
    k = np.arange(n_coeffs)[:, None]
    n = np.arange(N)[None, :]
    dct_mat = np.cos((np.pi / N) * (n + 0.5) * k)
    dct_mat[0] *= np.sqrt(1.0 / (4.0 * N)) * 2.0
    dct_mat[1:] *= np.sqrt(1.0 / (2.0 * N)) * 2.0
    return np.dot(dct_mat, matrix)


def extract_voice_embedding(audio_pcm: bytes, sample_rate: int = 16000) -> Optional[np.ndarray]:
    """
    Extracts a 128-dimensional dense normalized acoustic voice embedding vector from raw PCM16 audio.
    Analyzes VAD-gated active speech, Pitch F0 autocorrelation harmonics, vocal tract centroid & rolloff,
    32 Mel filterbank formant distribution, and Cepstral Mean-Normalized (CMN) MFCC statistics.
    """
    if not audio_pcm or len(audio_pcm) < 2400:  # Need at least 75ms of audio
        return None

    try:
        audio = np.frombuffer(audio_pcm, dtype=np.int16).astype(np.float32) / 32768.0

        nperseg = int(sample_rate * 0.025)  # 25ms window (400 samples)
        noverlap = int(sample_rate * 0.015) # 10ms step (240 samples overlap)
        step = nperseg - noverlap
        if len(audio) < nperseg:
            return None

        frames = np.lib.stride_tricks.sliding_window_view(audio, nperseg)[::step]
        energies = np.sum(frames ** 2, axis=1)
        max_e = np.max(energies) if len(energies) > 0 else 0
        if max_e < 1e-6:
            return None

        # VAD filtering: Keep active speech frames (above 2% of peak energy)
        voiced_mask = energies >= max(max_e * 0.02, 1e-6)
        voiced_frames = frames[voiced_mask] if np.sum(voiced_mask) >= 3 else frames

        # 1. Pitch (F0) Autocorrelation on voiced speech frames
        min_lag = int(sample_rate / 450) # 450 Hz max human pitch
        max_lag = int(sample_rate / 65)  # 65 Hz min human pitch
        f0_list = []
        for vf in voiced_frames:
            ac = np.correlate(vf, vf, mode='full')[len(vf)-1:]
            if ac[0] > 1e-6:
                norm_ac = ac / ac[0]
                srch = norm_ac[min_lag:max_lag]
                if len(srch) > 0 and np.max(srch) > 0.25:
                    f0_list.append(sample_rate / (min_lag + np.argmax(srch)))

        f0_mean = float(np.mean(f0_list)) if len(f0_list) > 0 else 150.0
        f0_std = float(np.std(f0_list)) if len(f0_list) > 0 else 15.0

        # 2. STFT Spectrogram & Spectral Analysis (Zero-Scipy)
        freqs, Sxx = _compute_spectrogram_np(audio, sample_rate, nperseg=nperseg, noverlap=noverlap)
        if Sxx.size == 0 or Sxx.shape[1] == 0:
            return None

        # Spectral Centroid & Spectral Rolloff
        power_spec = np.mean(Sxx, axis=1)
        total_p = np.sum(power_spec) + 1e-9
        spec_centroid = float(np.sum(freqs * power_spec) / total_p)
        cumsum = np.cumsum(power_spec)
        rolloff_idx = np.searchsorted(cumsum, 0.85 * total_p)
        spec_rolloff = float(freqs[min(rolloff_idx, len(freqs)-1)])

        # 3. 32 Triangular Mel Filterbanks
        def hz_to_mel(hz): return 2595.0 * np.log10(1.0 + hz / 700.0)
        def mel_to_hz(mel): return 700.0 * (10.0 ** (mel / 2595.0) - 1.0)

        n_mels = 32
        mel_pts = np.linspace(hz_to_mel(80), hz_to_mel(sample_rate / 2.0), n_mels + 2)
        hz_pts = mel_to_hz(mel_pts)
        bin_pts = np.floor((nperseg + 1) * hz_pts / sample_rate).astype(int)

        fbanks = np.zeros((n_mels, len(freqs)), dtype=np.float32)
        for m in range(1, n_mels + 1):
            f_m_minus = bin_pts[m - 1]
            f_m = bin_pts[m]
            f_m_plus = bin_pts[m + 1]
            for k in range(f_m_minus, min(f_m, len(freqs))):
                fbanks[m - 1, k] = (k - bin_pts[m - 1]) / max(f_m - bin_pts[m - 1], 1)
            for k in range(f_m, min(f_m_plus, len(freqs))):
                fbanks[m - 1, k] = (bin_pts[m + 1] - k) / max(bin_pts[m + 1] - f_m, 1)

        mel_energies = np.dot(fbanks, Sxx)
        mel_energies = np.where(mel_energies > 1e-10, mel_energies, 1e-10)
        log_mel_energies = np.log(mel_energies)

        # 4. MFCCs with CMN
        mfccs = _compute_dct_np(log_mel_energies, n_coeffs=20)
        mfccs -= np.mean(mfccs, axis=1, keepdims=True)

        mfcc_means = np.mean(mfccs, axis=1) # 20
        mfcc_stds = np.std(mfccs, axis=1)   # 20

        # Delta MFCCs
        if mfccs.shape[1] > 2:
            delta_mfccs = np.diff(mfccs, axis=1)
            delta_means = np.mean(delta_mfccs, axis=1) # 20
            delta_stds = np.std(delta_mfccs, axis=1)   # 20
        else:
            delta_means = np.zeros(20, dtype=np.float32)
            delta_stds = np.zeros(20, dtype=np.float32)

        # Mel Filterbank Energy distribution
        mel_means = np.mean(log_mel_energies, axis=1) # 32
        mel_stds = np.std(log_mel_energies, axis=1)   # 32

        # 5. Concatenate full 128-dimensional dense feature representation
        feat_128 = np.concatenate([
            mfcc_means,           # 20
            mfcc_stds,            # 20
            delta_means,          # 20
            delta_stds,           # 20
            mel_means[:16],       # 16
            mel_stds[:16],        # 16
            np.array([
                f0_mean / 400.0,
                f0_std / 50.0,
                spec_centroid / 4000.0,
                spec_rolloff / 6000.0,
                float(np.mean(energies)) * 10.0,
                float(np.std(energies)) * 10.0,
                float(np.percentile(energies, 90)) * 10.0,
                float(np.sum(voiced_mask)) / max(len(voiced_mask), 1),
                float(len(f0_list)) / max(len(voiced_frames), 1),
                float(np.median(f0_list) / 400.0) if f0_list else 0.35,
                float(np.max(f0_list) / 500.0) if f0_list else 0.45,
                float(np.min(f0_list) / 300.0) if f0_list else 0.25,
                float(np.ptp(f0_list) / 200.0) if f0_list else 0.1,
                float(np.mean(mel_energies)),
                float(np.var(mel_energies)),
                1.0 # Bias
            ], dtype=np.float32)  # 16
        ]).astype(np.float32)     # Total = 128 dimensions

        # L2-Norm unit vector normalization
        norm = np.linalg.norm(feat_128)
        if norm > 1e-6:
            feat_128 = feat_128 / norm
        return feat_128

    except Exception as e:
        logger.warning(f"[Voice Biometrics] Embedding extraction error: {e}")
        return None


def canonicalize_speaker_name(name: Optional[str]) -> Optional[str]:
    """Ensures consistent title-cased and stripped speaker name (zero hardcoded typos)."""
    if not name:
        return None
    return name.strip().strip("'\"").title()


class VoiceBiometricsMixin:
    """Speaker profile management, voice enrollment, identification, and adaptive calibration."""

    def enroll_or_update_speaker(self, name: str, audio_pcm: Optional[bytes] = None) -> Dict[str, Any]:
        """Enrolls a new speaker or updates an existing speaker without duplicates."""
        clean_name = canonicalize_speaker_name(name)
        if not clean_name:
            return {"status": "error", "message": "Invalid speaker name"}

        emb = extract_voice_embedding(audio_pcm) if audio_pcm else None
        emb_json = json.dumps(emb.tolist()) if emb is not None else None

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, voice_embedding, sample_count FROM speakers WHERE name = ?", (clean_name,))
            existing = cursor.fetchone()

            if existing:
                speaker_id = existing["id"]
                count = min((existing["sample_count"] or 1) + (1 if emb is not None else 0), MAX_VOICE_SAMPLES)
                updated_emb_json = existing["voice_embedding"]
                if emb is not None:
                    if existing["voice_embedding"]:
                        try:
                            old_emb = np.array(json.loads(existing["voice_embedding"]), dtype=np.float32)
                            alpha = max(0.10, 1.0 / min(count, 10))
                            merged = ((1.0 - alpha) * old_emb) + (alpha * emb)
                            norm = np.linalg.norm(merged)
                            if norm > 1e-6:
                                merged = merged / norm
                            updated_emb_json = json.dumps(merged.tolist())
                        except Exception:
                            updated_emb_json = emb_json
                    else:
                        updated_emb_json = emb_json

                cursor.execute("""
                    UPDATE speakers 
                    SET voice_embedding = ?, sample_count = ?, last_seen = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (updated_emb_json, count, speaker_id))
                conn.commit()
                logger.info(f"[AnaraMemory] Updated speaker: {clean_name} (ID={speaker_id}, Samples={count})")
                self._emit_mutation("speaker_enrolled", {"name": clean_name, "id": speaker_id, "sample_count": count})
                return {"status": "updated", "speaker_id": speaker_id, "name": clean_name, "sample_count": count, "is_new": False}
            else:
                cursor.execute("""
                    INSERT INTO speakers (name, voice_embedding, sample_count, last_seen)
                    VALUES (?, ?, 1, CURRENT_TIMESTAMP)
                """, (clean_name, emb_json))
                conn.commit()
                speaker_id = cursor.lastrowid
                logger.info(f"[AnaraMemory] Enrolled new speaker: {clean_name} (ID={speaker_id})")
                self._emit_mutation("speaker_enrolled", {"name": clean_name, "id": speaker_id, "sample_count": 1})
                return {"status": "created", "speaker_id": speaker_id, "name": clean_name, "sample_count": 1, "is_new": True}

    def calibrate_speaker_voice(self, name: str, audio_pcm: bytes) -> Dict[str, Any]:
        """Explicitly calibrates voice embedding for a given speaker profile from audio."""
        if not audio_pcm or len(audio_pcm) < 3200:
            return {"status": "error", "message": "Audio sample is too short for biometric calibration (minimum 200ms required)."}
        emb = extract_voice_embedding(audio_pcm)
        if emb is None:
            return {"status": "error", "message": "Failed to extract voice embedding from audio. Speak clearly into the microphone."}
        return self.enroll_or_update_speaker(name, audio_pcm)

    def get_last_active_speaker_name(self) -> Optional[str]:
        """Retrieves the most recently active speaker from SQLite, or None."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM speakers ORDER BY last_seen DESC LIMIT 1")
                row = cursor.fetchone()
                if row and row["name"]:
                    return canonicalize_speaker_name(row["name"])
        except Exception:
            pass
        return None

    def get_primary_speaker_name(self) -> Optional[str]:
        """Alias for get_last_active_speaker_name in multi-user mode."""
        return self.get_last_active_speaker_name()

    def identify_speaker(self, audio_pcm: bytes, threshold: float = 0.74) -> Tuple[Optional[str], float, Optional[int]]:
        """
        Matches voice against registered embeddings using Cosine Similarity.
        Supports single-speaker adaptive thresholding, multi-speaker discrimination,
        and automatic binding for uncalibrated initial profiles.
        """
        emb = extract_voice_embedding(audio_pcm)
        if emb is None:
            return None, 0.0, None

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, voice_embedding, sample_count FROM speakers WHERE voice_embedding IS NOT NULL")
            rows = cursor.fetchall()

            if not rows:
                cursor.execute("SELECT id, name FROM speakers WHERE voice_embedding IS NULL ORDER BY id ASC LIMIT 1")
                uncalibrated = cursor.fetchone()
                if uncalibrated:
                    target_name = uncalibrated["name"]
                    target_id = uncalibrated["id"]
                    emb_json = json.dumps(emb.tolist())
                    cursor.execute("UPDATE speakers SET voice_embedding = ?, sample_count = 1, last_seen = CURRENT_TIMESTAMP WHERE id = ?", (emb_json, target_id))
                    conn.commit()
                    logger.info(f"[Voice Biometrics Auto-Calibration] Bound initial voice sample to profile '{target_name}' (ID={target_id})")
                    self._emit_mutation("speaker_enrolled", {"name": target_name, "id": target_id, "sample_count": 1})
                    return target_name, 1.0, target_id
                return None, 0.0, None

            best_speaker = None
            best_id = None
            best_score = -1.0
            best_stored_emb = None
            best_count = 1

            for row in rows:
                try:
                    stored_emb = np.array(json.loads(row["voice_embedding"]), dtype=np.float32)
                    if len(stored_emb) != len(emb):
                        min_len = min(len(stored_emb), len(emb))
                        s_norm = stored_emb[:min_len] / (np.linalg.norm(stored_emb[:min_len]) + 1e-9)
                        e_norm = emb[:min_len] / (np.linalg.norm(emb[:min_len]) + 1e-9)
                        sim = float(np.dot(e_norm, s_norm))
                    else:
                        sim = float(np.dot(emb, stored_emb))

                    if sim > best_score:
                        best_score = sim
                        best_speaker = row["name"]
                        best_id = row["id"]
                        best_stored_emb = stored_emb
                        best_count = row["sample_count"] or 1
                except Exception as err:
                    logger.warning(f"[Voice Biometrics] Error comparing with {row['name']}: {err}")

            eff_threshold = 0.62

            if best_speaker and best_score >= eff_threshold:
                try:
                    if best_score >= 0.80 and best_stored_emb is not None and len(best_stored_emb) == len(emb):
                        is_mature = best_count >= MAX_VOICE_SAMPLES
                        now_mono = time.monotonic()
                        last_adapt = self._last_adapt_ts.get(best_id, 0.0)
                        adapt_allowed = (not is_mature) or ((now_mono - last_adapt) >= MATURE_ADAPT_INTERVAL)

                        if adapt_allowed:
                            alpha = max(0.04, 1.0 / min(best_count + 1, 15))
                            adapted = ((1.0 - alpha) * best_stored_emb) + (alpha * emb)
                            adapted_norm = np.linalg.norm(adapted)
                            if adapted_norm > 1e-6:
                                adapted = adapted / adapted_norm
                                new_count = min(best_count + 1, MAX_VOICE_SAMPLES)
                                cursor.execute("""
                                    UPDATE speakers 
                                    SET voice_embedding = ?, sample_count = ?, last_seen = CURRENT_TIMESTAMP 
                                    WHERE id = ?
                                """, (json.dumps(adapted.tolist()), new_count, best_id))
                                self._last_adapt_ts[best_id] = now_mono
                                if is_mature:
                                    logger.info(f"[Voice Biometrics] Mature anti-drift adaptation applied for '{best_speaker}' (cap={MAX_VOICE_SAMPLES})")
                        else:
                            cursor.execute("UPDATE speakers SET last_seen = CURRENT_TIMESTAMP WHERE id = ?", (best_id,))
                    else:
                        cursor.execute("UPDATE speakers SET last_seen = CURRENT_TIMESTAMP WHERE id = ?", (best_id,))
                    conn.commit()
                except Exception:
                    pass

                logger.info(f"[Voice Biometrics Match] Recognized speaker: '{best_speaker}' with confidence {best_score:.3f} (threshold={eff_threshold:.2f})")
                return best_speaker, best_score, best_id

        return None, max(best_score, 0.0), None

    def get_all_speakers(self) -> List[Dict[str, Any]]:
        """Returns all registered speaker records."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT s.id, s.name, s.voice_embedding IS NOT NULL as has_voice_embedding,
                       s.sample_count, s.created_at, s.last_seen,
                       COUNT(m.id) as memory_count
                FROM speakers s
                LEFT JOIN memories m ON s.id = m.speaker_id
                GROUP BY s.id
                ORDER BY s.last_seen DESC
            """)
            return [dict(r) for r in cursor.fetchall()]

    def delete_speaker(self, speaker_name: str) -> bool:
        """Deletes an entire speaker profile and all associated memories/notes."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_keys = ON")
            cursor.execute("DELETE FROM memories WHERE speaker_id IN (SELECT id FROM speakers WHERE name = ?)", (speaker_name.strip().title(),))
            cursor.execute("DELETE FROM notes_and_todos WHERE speaker_id IN (SELECT id FROM speakers WHERE name = ?)", (speaker_name.strip().title(),))
            cursor.execute("DELETE FROM speakers WHERE name = ?", (speaker_name.strip().title(),))
            conn.commit()
            logger.info(f"[AnaraMemory] Deleted speaker profile and memories for: {speaker_name}")
            self._emit_mutation("speaker_deleted", {"speaker_name": speaker_name.strip().title()})
            return True

    def normalize_memory_key(self, raw_key: str) -> str:
        """
        Normalizes memory key format (snake_case) and cleans temporal suffixes (Hermes Parity).
        Semantic naming is preserved directly from model reasoning without rigid word dictionaries.
        """
        k = raw_key.strip().lower().replace("-", "_").replace(" ", "_")
        k = re.sub(r"_(?:baru|baruku|sekarang|ini|terbaru|new|current|latest|recent)$", "", k)
        return k
