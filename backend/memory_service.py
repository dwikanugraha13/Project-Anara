import asyncio
import json
import logging
import os
import re
import sqlite3
import time
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Tuple, Callable

# Prevent OpenBLAS / OMP multithreading memory errors on Windows
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"

import numpy as np
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "anara_brain.db")


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
        f0_med = float(np.median(f0_list)) if len(f0_list) > 0 else 150.0

        # 2. Spectral Analysis (Centroid, Rolloff, Spread)
        window = np.hanning(nperseg)
        w_frames = voiced_frames * window
        specs = np.abs(np.fft.rfft(w_frames, n=nperseg, axis=-1))
        freqs = np.fft.rfftfreq(nperseg, 1.0 / sample_rate)

        spec_sum = np.sum(specs, axis=-1, keepdims=True) + 1e-9
        centroids = np.sum(specs * freqs, axis=-1) / np.squeeze(spec_sum, axis=-1)
        cent_mean = float(np.mean(centroids))
        cent_std = float(np.std(centroids))

        # 3. 32 Mel Filterbank Formant Distribution
        low_f, high_f = 80, sample_rate / 2
        mel_pts = np.linspace(2595 * np.log10(1 + low_f / 700), 2595 * np.log10(1 + high_f / 700), 34)
        hz_pts = 700 * (10**(mel_pts / 2595) - 1)
        bin_pts = np.floor((nperseg + 1) * hz_pts / sample_rate).astype(int)

        fbank = np.zeros((32, len(freqs)))
        for m in range(1, 33):
            for k in range(bin_pts[m-1], bin_pts[m]):
                fbank[m-1, k] = (k - bin_pts[m-1]) / (bin_pts[m] - bin_pts[m-1] + 1e-9)
            for k in range(bin_pts[m], bin_pts[m+1]):
                if k < len(freqs):
                    fbank[m-1, k] = (bin_pts[m+1] - k) / (bin_pts[m+1] - bin_pts[m] + 1e-9)

        mel_energies = np.dot(specs ** 2, fbank.T)
        mel_energies = np.where(mel_energies <= 0, 1e-9, mel_energies)
        log_mel = np.log10(mel_energies)

        # Spectral formant envelope curve (normalized across 32 bands)
        mel_curve = np.mean(log_mel, axis=0) # shape (32,)
        mel_curve = (mel_curve - np.mean(mel_curve)) / (np.std(mel_curve) + 1e-9)

        # 4. MFCC + Cepstral Mean Normalization (CMN)
        N = 32
        k_arr = np.arange(13)[:, None]
        n_arr = np.arange(N)[None, :]
        dct_mat = np.cos((np.pi / N) * (n_arr + 0.5) * k_arr)
        dct_mat[0] *= np.sqrt(1.0 / (4.0 * N)) * 2.0
        dct_mat[1:] *= np.sqrt(1.0 / (2.0 * N)) * 2.0

        mfcc = np.dot(log_mel, dct_mat.T) # shape (num_frames, 13)
        mfcc_cmn = mfcc - np.mean(mfcc, axis=0, keepdims=True)

        mfcc_std = np.std(mfcc_cmn[:, 1:], axis=0) # 12
        mfcc_max = np.max(mfcc_cmn[:, 1:], axis=0) # 12
        mfcc_min = np.min(mfcc_cmn[:, 1:], axis=0) # 12

        # Normalized Pitch & Brightness features
        norm_pitch = np.array([
            (f0_mean - 160.0) / 80.0,
            (f0_med - 160.0) / 80.0,
            f0_std / 30.0,
            (cent_mean - 1200.0) / 600.0,
            cent_std / 300.0
        ])

        # Dense vector assembly
        raw_vec = np.concatenate([
            norm_pitch * 2.5,
            mel_curve * 1.5,
            mfcc_std,
            mfcc_max * 0.5,
            mfcc_min * 0.5
        ])

        if len(raw_vec) < 128:
            padded = np.pad(raw_vec, (0, 128 - len(raw_vec)))
        else:
            padded = raw_vec[:128]

        norm = np.linalg.norm(padded)
        if norm > 1e-6:
            padded = padded / norm
        return padded.astype(np.float32)
    except Exception as e:
        logger.warning(f"[Voice Biometrics] Error extracting embedding: {e}")
        return None


def get_current_indonesian_time_str() -> Dict[str, str]:
    """Returns real-time Indonesian day, date, and clock time in WIB (UTC+7)."""
    wib_tz = timezone(timedelta(hours=7))
    now = datetime.now(wib_tz)
    
    days_id = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
    months_id = [
        "Januari", "Februari", "Maret", "April", "Mei", "Juni",
        "Juli", "Agustus", "September", "Oktober", "November", "Desember"
    ]
    
    day_name = days_id[now.weekday()]
    month_name = months_id[now.month - 1]
    date_formatted = f"{day_name}, {now.day} {month_name} {now.year}"
    time_formatted = now.strftime("%H:%M WIB")
    
    return {
        "day": day_name,
        "date_full": date_formatted,
        "time_str": time_formatted,
        "iso": now.isoformat()
    }


# ── Zero-Shot Dynamic AI Entity Classifier & Semantic Reasoner ─────────────

_DYNAMIC_ENTITY_CACHE: Dict[str, Dict[str, Any]] = {}

def classify_preference_entity_ai(entity: str, speaker_name: str = "Pengguna") -> Dict[str, Any]:
    """
    Uses Gemini Zero-Shot Semantic Classification to dynamically recognize ANY entity
    (animal, food, drink, vehicle, movie, game, sport, hobby, music, anime, etc.)
    and generates natural companion commentary and confirmation prompts without hardcoded dictionaries.
    """
    cache_key = entity.lower().strip()
    if cache_key in _DYNAMIC_ENTITY_CACHE:
        return _DYNAMIC_ENTITY_CACHE[cache_key]

    eff_speaker = speaker_name.strip().title() if speaker_name else "Pengguna"
    prompt = f"""Anda adalah otak semantik Anara (AI Companion 3D & J.A.R.V.I.S.).
Analisis entitas atau hal yang disukai pengguna berikut: "{entity}"

TUGAS:
1. Periksa apakah pengguna menyebutkan LEBIH DARI SATU hal (misal: "kucing dan panda", "sate sama rendang", "porsche dan ferrari").
   - Jika multi-entity (is_multi_entity: true):
     - entities: array berisi nama-nama entitas yang bersih (contoh: ["Kucing", "Panda"])
     - Buat confirmation_question: "Kamu menyukai [Entitas 1] dan [Entitas 2] ya! Antara keduanya, mana yang ingin Anara ingat sebagai [category_label] utamamu, atau kamu ingin Anara mengingat keduanya, {eff_speaker}?"
   - Jika single entity (is_multi_entity: false):
     - entities: ["{entity.title()}"]
     - Buat companion_comment: 1 kalimat pujian/komentar hangat & antusias tentang entitas tersebut.
     - Buat confirmation_question: "Bahwa {entity.title()} adalah [category_label] kamu, Anara boleh mengingatnya, {eff_speaker}?"
2. Klasifikasikan canonical_key: (contoh: hewan_favorit, makanan_favorit, minuman_favorit, kendaraan_favorit, film_favorit, game_favorit, lagu_favorit, band_favorit, anime_favorit, hobi, dsb).
3. Tentukan category_label: (contoh: hewan kesukaan, makanan kesukaan, minuman kesukaan, kendaraan kesukaan, film favorit, band favorit, hobi, dsb).

KEMBALIKAN HANYA JSON VALID:
{{
  "is_multi_entity": false,
  "entities": ["Panda"],
  "canonical_key": "hewan_favorit",
  "category_label": "hewan kesukaan",
  "companion_comment": "Wah, Panda itu menggemaskan banget!",
  "confirmation_question": "Bahwa Panda adalah hewan kesukaan kamu, Anara boleh mengingatnya, {eff_speaker}?"
}}"""

    try:
        from key_manager import key_manager
        from google.genai import types
        for attempt in range(len(key_manager._keys) or 3):
            key = key_manager.get_active_key()
            client = key_manager.get_client()
            try:
                res = client.models.generate_content(
                    model="gemini-3.5-flash-lite",
                    contents=prompt,
                    config=types.GenerateContentConfig(max_output_tokens=350, temperature=0.2)
                )
                if res and res.text:
                    raw = res.text.strip()
                    if "{" in raw and "}" in raw:
                        json_str = raw[raw.find("{"):raw.rfind("}")+1]
                        parsed = json.loads(json_str)
                        _DYNAMIC_ENTITY_CACHE[cache_key] = parsed
                        return parsed
            except Exception as e:
                if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e) or "403" in str(e):
                    key_manager.rotate_key(key, reason=str(e))
                    continue
                break
    except Exception as e:
        logger.warning(f"[DynamicEntityAI] Error classifying '{entity}': {e}")

    fallback = {
        "is_multi_entity": False,
        "entities": [entity.title()],
        "canonical_key": "preferensi_kesukaan",
        "category_label": "preferensi kesukaan",
        "companion_comment": f"Wah, tentang {entity.title()} itu menarik banget!",
        "confirmation_question": f"Bahwa {entity.title()} adalah preferensi kesukaan kamu, Anara boleh mengingatnya, {eff_speaker}?"
    }
    _DYNAMIC_ENTITY_CACHE[cache_key] = fallback
    return fallback


def resolve_contextual_memory_command(command: str, recent_chats: List[Dict[str, Any]], speaker_name: str = "Pengguna") -> Optional[Dict[str, Any]]:
    """
    Resolves memory saving commands that use pronouns (e.g. 'simpan itu ke database sebagai hewan favorit saya')
    by identifying the referenced entity from recent dialogue context and mapping to canonical memory key.
    """
    eff_speaker = speaker_name.strip().title() if speaker_name else "Pengguna"
    recent_lines = []
    for c in recent_chats[-3:]:
        u_t = (c.get("user_text") or "").strip()
        a_t = (c.get("ai_text") or "").strip()
        if u_t or a_t:
            recent_lines.append(f"User: {u_t}\nAnara: {a_t}")
    recent_context = "\n---\n".join(recent_lines)

    prompt = f"""Anda adalah otak semantik Project Anara (AI Memory Reasoner).
Pengguna memberikan perintah penyimpanan memori yang menggunakan kata ganti / rujukan (seperti 'itu', 'ini', 'tersebut'):
Perintah Pengguna: "{command}"

KONTEKS PERCAKAPAN TERAKHIR:
{recent_context}

TUGAS:
1. Temukan objek/subjek yang dirujuk oleh 'itu'/'ini' dari KONTEKS PERCAKAPAN TERAKHIR (Contoh: jika baru membahas Panda, maka objek adalah "Panda").
2. Identifikasi kategori memori yang diinginkan (Contoh: hewan favorit, makanan favorit, kendaraan favorit, film favorit, lagu favorit, band favorit, hobi, dsb).
3. Tentukan canonical_key (contoh: hewan_favorit, makanan_favorit, kendaraan_favorit, film_favorit, lagu_favorit, band_favorit, hobi, dsb).
4. Tentukan category_label (contoh: hewan kesukaan, makanan kesukaan, kendaraan kesukaan, film favorit, band favorit, dsb).
5. Buat confirmation_prompt yang ramah dan alami dengan format:
   "Bahwa [Objek] adalah [category_label] kamu, Anara boleh mengingatnya, {eff_speaker}?"

KEMBALIKAN HANYA JSON VALID:
{{
  "resolved_entity": "Panda",
  "canonical_key": "hewan_favorit",
  "category_label": "hewan kesukaan",
  "confirmation_prompt": "Bahwa Panda adalah hewan kesukaan kamu, Anara boleh mengingatnya, {eff_speaker}?"
}}"""

    try:
        from key_manager import key_manager
        from google.genai import types
        for attempt in range(len(key_manager._keys) or 3):
            key = key_manager.get_active_key()
            client = key_manager.get_client()
            try:
                res = client.models.generate_content(
                    model="gemini-3.5-flash-lite",
                    contents=prompt,
                    config=types.GenerateContentConfig(max_output_tokens=300, temperature=0.2)
                )
                if res and res.text:
                    raw = res.text.strip()
                    if "{" in raw and "}" in raw:
                        json_str = raw[raw.find("{"):raw.rfind("}")+1]
                        return json.loads(json_str)
            except Exception as e:
                if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e) or "403" in str(e):
                    key_manager.rotate_key(key, reason=str(e))
                    continue
                break
    except Exception as e:
        logger.warning(f"[ContextualMemoryAI] Error resolving command '{command}': {e}")
    return None


def canonicalize_speaker_name(name: Optional[str]) -> Optional[str]:
    """Cleans and standardizes speaker name formatting for multi-user system."""
    if not name:
        return None
    clean = name.strip().title()
    if clean.lower() in ("adnan", "ag nan", "ad nan"):
        return "Agnan"
    return clean


class AnaraMemoryEngine:
    """
    SQLite-backed JARVIS-style Cognitive Brain & Voice Biometrics Engine for Project Anara.
    Stores and recalls user profiles, personal preferences, voiceprints, notes, to-dos,
    and episodic conversation history with strict deduplication and zero-shot AI distillation.
    Includes interactive confirmation before committing new facts & tasks to SQLite.
    """

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._pending_proposals: Dict[str, Dict[str, Any]] = {}
        self._mutation_listeners: List[Callable[[str, Dict[str, Any]], Any]] = []
        self._init_db()

    def register_mutation_listener(self, listener: Callable[[str, Dict[str, Any]], Any]):
        """Registers a callback for real-time memory/todo mutations (for live WebSocket sync)."""
        if listener not in self._mutation_listeners:
            self._mutation_listeners.append(listener)

    def _emit_mutation(self, event_type: str, data: Dict[str, Any]):
        """Invokes all registered mutation listeners safely."""
        for listener in self._mutation_listeners:
            try:
                res = listener(event_type, data)
                if asyncio.iscoroutine(res):
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(res)
                    except RuntimeError:
                        res.close()
            except Exception as e:
                logger.warning(f"[MemoryMutation] Error in listener callback: {e}")

    def semantic_search_brain(self, query: str, speaker_name: Optional[str] = None, top_k: int = 4) -> List[Dict[str, Any]]:
        """
        JARVIS 2.0 Semantic Memory & Episodic RAG Search:
        Computes BM25/TF-IDF token and concept similarity across memories, projects, notes, and past conversations.
        """
        if not query or len(query.strip()) < 2:
            return []
        
        eff_speaker = canonicalize_speaker_name(speaker_name) if speaker_name else None
        
        # Tokenize query
        q_tokens = set(re.findall(r"\w+", query.lower()))
        STOP = {"yang", "dan", "dari", "ke", "di", "ini", "itu", "aku", "kamu", "saya", "apa", "ada", "nih", "ya", "yah", "dong", "deh", "tentang", "dong"}
        q_clean_tokens = [t for t in q_tokens if t not in STOP and len(t) >= 2]
        if not q_clean_tokens:
            q_clean_tokens = list(q_tokens)

        scored_items = []

        with self._get_connection() as conn:
            cur = conn.cursor()
            
            # 1. Search in memories
            m_query = """
                SELECT m.key, m.value, m.category, s.name as sp_name
                FROM memories m
                LEFT JOIN speakers s ON m.speaker_id = s.id
                WHERE (s.name = ? OR ? IS NULL)
            """
            cur.execute(m_query, (eff_speaker, eff_speaker))
            for r in cur.fetchall():
                text = f"{r['key']} {r['value']} {r['category']}".lower()
                score = sum(2.5 if t in r['key'].lower() else (1.8 if t in r['value'].lower() else 0.5) for t in q_clean_tokens if t in text)
                if score > 0:
                    scored_items.append({
                        "type": "memory",
                        "title": r['key'].replace('_', ' ').title(),
                        "content": r['value'],
                        "category": r['category'],
                        "score": score
                    })

            # 2. Search in projects
            p_query = """
                SELECT p.name, p.tech_stack, p.goal, p.status, p.notes, s.name as sp_name
                FROM projects p
                LEFT JOIN speakers s ON p.speaker_id = s.id
                WHERE (s.name = ? OR ? IS NULL OR p.speaker_id IS NULL)
            """
            cur.execute(p_query, (eff_speaker, eff_speaker))
            for r in cur.fetchall():
                text = f"{r['name']} {r['tech_stack']} {r['goal']} {r['notes']}".lower()
                score = sum(3.5 if t in r['name'].lower() else (2.2 if t in (r['tech_stack'] or '').lower() else 1.2) for t in q_clean_tokens if t in text)
                if score > 0:
                    scored_items.append({
                        "type": "project",
                        "title": f"Proyek '{r['name']}'",
                        "content": f"Tech: {r['tech_stack']} | Target: {r['goal']}" + (f" | Catatan: {r['notes']}" if r['notes'] else ""),
                        "category": "project",
                        "score": score
                    })

            # 3. Search in notes / todos
            n_query = """
                SELECT n.title, n.content, n.category, n.is_completed, s.name as sp_name
                FROM notes_and_todos n
                LEFT JOIN speakers s ON n.speaker_id = s.id
                WHERE (s.name = ? OR ? IS NULL OR n.speaker_id IS NULL)
            """
            cur.execute(n_query, (eff_speaker, eff_speaker))
            for r in cur.fetchall():
                text = f"{r['title']} {r['content']} {r['category']}".lower()
                score = sum(2.8 if t in r['title'].lower() else 1.2 for t in q_clean_tokens if t in text)
                if score > 0:
                    status_lbl = "Selesai" if r['is_completed'] else "Aktif"
                    scored_items.append({
                        "type": "todo",
                        "title": f"Tugas [{r['category'].upper()} - {status_lbl}]: {r['title']}",
                        "content": r['content'] or "",
                        "category": r['category'],
                        "score": score
                    })

            # 4. Search in past conversation turns
            c_query = "SELECT user_text, ai_text, created_at FROM conversations WHERE (speaker_name = ? OR ? IS NULL) ORDER BY id DESC LIMIT 30"
            cur.execute(c_query, (eff_speaker, eff_speaker))
            for r in cur.fetchall():
                text = f"{r['user_text']} {r['ai_text']}".lower()
                score = sum(1.2 for t in q_clean_tokens if t in text)
                if score >= 1.5:
                    scored_items.append({
                        "type": "conversation",
                        "title": f"Percakapan Sebelumnya: '{r['user_text']}'",
                        "content": f"Jawaban Anara: {r['ai_text']}",
                        "category": "history",
                        "score": score
                    })

        scored_items.sort(key=lambda x: x["score"], reverse=True)
        return scored_items[:top_k]

    def get_proactive_relevant_facts(self, user_query: str, speaker_name: Optional[str] = None) -> str:
        """
        Cognitive Proactive Fact Association & Semantic RAG:
        Finds domain-specific memories and cross-table semantic knowledge.
        """
        if not user_query:
            return ""
        eff_speaker = canonicalize_speaker_name(speaker_name)
        if not eff_speaker:
            return ""

        rag_results = self.semantic_search_brain(user_query, speaker_name=eff_speaker, top_k=3)
        if not rag_results:
            return ""

        snippets = []
        for item in rag_results:
            if item["type"] == "memory":
                snippets.append(f"- Ingatan: {item['title']} = {item['content']}")
            elif item["type"] == "project":
                snippets.append(f"- {item['title']}: {item['content']}")
            elif item["type"] == "todo":
                snippets.append(f"- {item['title']}" + (f" ({item['content']})" if item['content'] else ""))
            elif item["type"] == "conversation":
                snippets.append(f"- Riwayat Dialog: {item['title']} -> {item['content']}")

        return (
            f"[MEMORI SEMANTIK & RIWAYAT RELEVAN ({eff_speaker.upper()}) DARI DATABASE]:\n"
            + "\n".join(snippets) + "\n"
            "Gunakan konteks memori di atas secara alami untuk menjawab dengan cerdas, presisi, dan kontekstual."
        )

    def get_proactive_briefing_guidance(self, speaker_name: Optional[str] = None, acoustic_tone: Optional[Dict[str, Any]] = None) -> str:
        """
        JARVIS 2.0 Proactive Anticipation & Acoustic Empathy Engine.
        Analyzes time of day, acoustic fatigue, pending deadlines, and active project targets.
        """
        eff_speaker = canonicalize_speaker_name(speaker_name)
        if not eff_speaker:
            return ""

        time_info = get_current_indonesian_time_str()
        hour = 12
        try:
            hour = int(time_info["time_str"].split(":")[0])
        except Exception:
            pass

        proactive_notes = []

        # 1. Time-of-day Awareness
        if 5 <= hour <= 10:
            proactive_notes.append("Konteks Pagi: Berikan semangat pagi yang segar dan sebutkan target hari ini jika relevan.")
        elif 22 <= hour or hour <= 4:
            proactive_notes.append("Konteks Larut Malam: Pengguna sedang bekerja larut malam. Bersikaplah perhatian, apresiatif atas dedikasinya, dan sarankan rehat jika tugas selesai.")

        # 2. Acoustic Tone SER & Fatigue Analysis
        if acoustic_tone:
            em = acoustic_tone.get("emotion", "neutral")
            pitch = acoustic_tone.get("pitch_hz", 150)
            if em == "sad" or pitch < 110:
                proactive_notes.append("Analisis Suara: Pengguna terdengar lelah/berat. Tunjukkan empati hangat dan nada menenangkan layaknya JARVIS peduli.")
            elif em == "angry":
                proactive_notes.append("Analisis Suara: Pengguna terdengar tegang/stres. Berikan respon yang tenang, solutif, dan efisien.")
            elif em == "happy" or pitch > 220:
                proactive_notes.append("Analisis Suara: Pengguna terdengar ceria/antusias. Balas dengan energi positif dan antusias.")

        # 3. Check Pending To-Dos
        todos = self.get_notes_and_todos(speaker_name=eff_speaker)
        pending = [t for t in todos if not t["is_completed"]]
        if len(pending) > 0:
            top_task = pending[0]["title"]
            proactive_notes.append(f"To-Do Utama: Ada {len(pending)} tugas aktif (prioritas: '{top_task}').")

        # 4. Check Active Project
        projs = self.get_projects_for_speaker(speaker_name=eff_speaker)
        if projs:
            active_p = projs[0]
            proactive_notes.append(f"Proyek Utama: '{active_p['name']}' ({active_p.get('goal', '')}).")

        if not proactive_notes:
            return ""

        return (
            f"[MODUL ANTISIPASI PROAKTIF & EMPATI JARVIS 2.0]:\n"
            + "\n".join([f"- {n}" for n in proactive_notes]) + "\n"
        )

    def set_pending_proposal(self, speaker_name: str, proposal: Dict[str, Any]):
        """Stages a proposed fact/task waiting for user's explicit verbal/chat confirmation."""
        proposal["timestamp"] = time.time()
        self._pending_proposals[speaker_name.strip().title()] = proposal

    def get_pending_proposal(self, speaker_name: str) -> Optional[Dict[str, Any]]:
        """Retrieves active pending proposal if within 3-minute window."""
        p = self._pending_proposals.get(speaker_name.strip().title())
        if p and (time.time() - p.get("timestamp", 0)) < 180:
            return p
        return None

    def commit_pending_proposal(self, speaker_name: str) -> Optional[str]:
        """User confirmed: commits the pending fact/task/deletion to SQLite database."""
        p = self.get_pending_proposal(speaker_name)
        if not p:
            return None
        self._pending_proposals.pop(speaker_name.strip().title(), None)
        p_type = p.get("type", "fact")
        target_name = canonicalize_speaker_name(speaker_name) or speaker_name.strip().title()
        if p_type == "fact":
            self.store_memory(target_name, p["key"], p["value"], p.get("category", "preference"))
            title_lbl = p.get("title", p["key"].replace("_", " "))
            return f"Siap {target_name}! Anara akan selalu mengingat bahwa '{p['value']}' adalah {title_lbl} kamu. ✨"
        elif p_type == "todo":
            self.create_note_or_todo(
                title=p["title"],
                content=p.get("content", ""),
                category=p.get("category", "todo"),
                due_date=p.get("due_date"),
                speaker_name=target_name
            )
            return f"Siap {target_name}! Tugas '{p['title']}' sudah resmi Anara catat di daftar to-do kamu."
        elif p_type == "delete_speaker":
            target_del = p.get("target_speaker", target_name)
            self.delete_speaker(target_del)
            return f"Profil {target_del} beserta seluruh ingatan dan catatan telah resmi dihapus dari database Anara."
        elif p_type == "enroll_speaker":
            target_sp = p.get("target_speaker", "Tamu")
            self.enroll_or_update_speaker(target_sp)
            return f"Siap {target_name}! Profil pengguna baru '{target_sp}' telah berhasil didaftarkan di sistem database Anara."
        return None

    def reject_pending_proposal(self, speaker_name: str) -> Optional[str]:
        """User declined: cancels the pending fact/task/deletion without writing to SQLite."""
        p = self.get_pending_proposal(speaker_name)
        if not p:
            return None
        self._pending_proposals.pop(speaker_name.strip().title(), None)
        p_type = p.get("type", "fact")
        if p_type == "delete_speaker":
            return "Baik, penghapusan profil dibatalkan. Profil dan seluruh catatanmu tetap aman di database Anara."
        return "Baik, pencatatan dibatalkan. Tidak ada data yang disimpan ke database."

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initializes full database schema with unique constraints to prevent duplicates."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Registered Speakers & Voice Biometrics
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS speakers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE COLLATE NOCASE,
                    voice_embedding TEXT,
                    sample_count INTEGER DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_seen DATETIME DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # 2. Categorized Long-Term Memories & Facts
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    speaker_id INTEGER,
                    category TEXT,
                    key TEXT,
                    value TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (speaker_id) REFERENCES speakers(id) ON DELETE CASCADE,
                    UNIQUE(speaker_id, key) ON CONFLICT REPLACE
                );
            """)
            
            # 3. Notes & To-Do Lists (JARVIS Task Tracker)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS notes_and_todos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    speaker_id INTEGER,
                    category TEXT DEFAULT 'todo', -- 'todo', 'note', 'reminder'
                    title TEXT NOT NULL,
                    content TEXT,
                    is_completed INTEGER DEFAULT 0,
                    due_date TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (speaker_id) REFERENCES speakers(id) ON DELETE SET NULL
                );
            """)
            
            # 4. Episodic Multi-Session Conversation Logs
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    speaker_name TEXT,
                    speaker_id INTEGER,
                    user_text TEXT,
                    ai_text TEXT,
                    media_type TEXT,
                    media_url TEXT,
                    visual_data_json TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # 5. Knowledge Base & Custom Learned Schematics
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS knowledge_base (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic TEXT UNIQUE COLLATE NOCASE,
                    content TEXT NOT NULL,
                    tags_json TEXT,
                    source TEXT DEFAULT 'user',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # 6. 3D Animations & Behaviors
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS animations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE COLLATE NOCASE,
                    category TEXT,
                    emotion TEXT,
                    gesture TEXT,
                    intensity REAL DEFAULT 0.8,
                    duration_sec REAL DEFAULT 3.0,
                    keywords_json TEXT,
                    description TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 7. User Personal Projects & Work Context
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    speaker_id INTEGER,
                    name TEXT NOT NULL,
                    tech_stack TEXT,
                    goal TEXT,
                    status TEXT DEFAULT 'active', -- 'active', 'completed', 'paused'
                    notes TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (speaker_id) REFERENCES speakers(id) ON DELETE CASCADE
                );
            """)

            # ── Dynamic Column Migrations for Existing Databases ──
            try:
                cursor.execute("ALTER TABLE speakers ADD COLUMN voice_snapshots_json TEXT")
            except Exception:
                pass
            try:
                cursor.execute("ALTER TABLE speakers ADD COLUMN preferred_tone TEXT DEFAULT 'balanced'")
            except Exception:
                pass

            conn.commit()
            
            # ── Clean up existing duplicate conversations keeping only newest ──
            try:
                cursor.execute("""
                    DELETE FROM conversations
                    WHERE id NOT IN (
                        SELECT MAX(id)
                        FROM conversations
                        GROUP BY COALESCE(speaker_name, ''), LOWER(TRIM(user_text))
                    );
                """)
                conn.commit()
            except Exception as e:
                logger.warning(f"[Deduplication] Initial conversation cleanup error: {e}")

            self._seed_default_animations(conn)
            self._seed_default_notes(conn)
            logger.info(f"[AnaraMemory] SQLite Brain initialized at {self.db_path}")

    def _seed_default_animations(self, conn: sqlite3.Connection):
        """Seeds standard built-in 3D animations and behavior profiles if not yet present."""
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM animations")
        if cursor.fetchone()[0] > 0:
            return

        defaults = [
            ("dance", "dance", "dance", "dance", 1.0, 9.0, json.dumps([
                "nari", "menari", "tarian", "joget", "dance", "dancing", "hibur", "goyang", "rumba", "musik", "pesta", "anara siap"
            ]), "Animasi tarian Rumba 3D penuh semangat dengan irama musik Latin"),
            ("angry", "emotion", "angry", "angry_pointing", 0.9, 4.0, json.dumps([
                "marah", "kesal", "jengkel", "frustrasi", "menyebalkan", "tidak sabar", "capek", "bosan", "mengecewakan", "tidak menyenangkan", "angry", "furious", "upset", "annoyed", "frustrated", "irritated", "terrible", "awful", "unacceptable", "ridiculous"
            ]), "Ekspresi marah dengan alis menekuk dan gestur menunjuk tegas"),
            ("crying", "emotion", "sad", "sad", 0.85, 4.0, json.dumps([
                "sedih", "menangis", "crying", "kecewa", "menyesal", "kasihan", "kehilangan", "duka", "hancur", "terpukul", "sakit hati", "patah hati", "sad", "disappointed", "sorry to hear", "unfortunate", "heartbroken"
            ]), "Ekspresi sedih/menangis dengan kepala menunduk dan mata berkaca-kaca"),
            ("laughing", "emotion", "happy", "joy", 0.95, 4.0, json.dumps([
                "senang", "gembira", "bahagia", "tertawa", "ketawa", "ngakak", "laughing", "wkwk", "haha", "suka", "bagus", "keren", "hebat", "luar biasa", "mantap", "wah", "fantastis", "sempurna", "selamat", "sukses", "menakjubkan", "seru", "happy", "great", "awesome", "amazing", "wonderful", "excellent", "fantastic", "congratulations", "yay", "hore"
            ]), "Ekspresi tertawa riang dan gestur gembira ceria"),
            ("shy", "emotion", "shy", "shy_movement", 0.8, 3.5, json.dumps([
                "malu", "tersipu", "canggung", "segan", "salah tingkah", "aduh", "hehe", "hihi", "ehehe", "ah kamu bisa aja", "terima kasih", "makasih", "cantik", "manis", "pujian", "shy", "embarrassed", "blush", "flattered", "thank you", "thanks"
            ]), "Gestur tersipu malu dengan senyuman manis"),
            ("salute", "gesture", "happy", "salute", 0.85, 3.0, json.dumps([
                "hormat", "sikap hormat", "memberi hormat", "salute", "lapor", "siap grak", "tegak grak", "salam hormat"
            ]), "Gestur memberi hormat tegak ala asisten AI profesional"),
            ("greeting", "gesture", "happy", "wave", 0.85, 3.0, json.dumps([
                "halo", "hai", "hey", "hello", "hi", "selamat pagi", "selamat siang", "selamat sore", "selamat malam", "assalamualaikum", "apa kabar", "senang berkenalan", "good morning", "good afternoon", "good evening", "welcome", "greetings", "sampai jumpa", "dadah", "bye", "goodbye"
            ]), "Melambaikan tangan kanan dengan senyuman ramah"),
            ("thinking", "gesture", "thinking", "think", 0.75, 3.5, json.dumps([
                "menurut saya", "mari kita", "mungkin", "sepertinya", "hmm", "menarik", "pertimbangkan", "analisis", "coba kita", "jika dilihat", "secara umum", "let me think", "perhaps", "maybe", "interesting", "considering", "i believe", "in my opinion", "well"
            ]), "Gestur berpikir dengan tangan di dagu dan mata menatap ke atas"),
            ("empathy", "emotion", "empathetic", "empathy", 0.8, 3.5, json.dumps([
                "maaf", "mohon maaf", "turut berduka", "jangan khawatir", "tenang saja", "saya mengerti", "sabar", "tetap semangat", "sorry", "apologize", "don't worry", "i understand", "stay strong", "i feel you"
            ]), "Gestur menenangkan dengan tatapan penuh kehangatan"),
            ("agree", "reaction", "happy", "nod", 0.75, 2.5, json.dumps([
                "iya", "ya", "tentu", "betul", "benar", "setuju", "pasti", "oke", "baik", "siap", "jelas", "tentu saja", "yes", "sure", "absolutely", "correct", "agree", "of course", "definitely"
            ]), "Mengangguk setuju dengan mantap"),
            ("disagree", "reaction", "neutral", "shake", 0.75, 2.5, json.dumps([
                "tidak", "bukan", "kurang tepat", "sayangnya tidak", "mustahil", "no", "not exactly", "incorrect", "disagree", "i'm afraid not"
            ]), "Menggelengkan kepala dengan tenang"),
            ("explaining", "gesture", "curious", "explaining", 0.75, 3.0, json.dumps([
                "pertama", "kedua", "ketiga", "karena", "jadi", "contohnya", "merupakan", "hal ini", "dengan demikian", "langkah", "fungsinya", "first", "second", "because", "therefore", "for example", "this means", "specifically", "in summary"
            ]), "Gestur tangan terbuka saat memaparkan penjelasan")
        ]

        cursor.executemany("""
            INSERT INTO animations (name, category, emotion, gesture, intensity, duration_sec, keywords_json, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, defaults)
        conn.commit()
        logger.info(f"[AnaraMemory] Seeded {len(defaults)} default animations into SQLite database.")

    def _seed_default_notes(self, conn: sqlite3.Connection):
        """Seeds standard welcoming notes/todos if table is empty."""
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM notes_and_todos")
        if cursor.fetchone()[0] > 0:
            return

        defaults = [
            (None, "todo", "Eksplorasi Fitur Visual Anara", "Coba minta Anara menampilkan foto Monas, ramalan cuaca, kode Python, atau telemetri sistem.", 1, None),
            (None, "todo", "Kenalkan Nama dan Suara ke Anara", "Sapa Anara: 'Hai Anara, kenalkan aku [Nama Kamu]'.", 0, None),
            (None, "note", "Protokol Sistem Anara", "Anara memiliki memori kognitif SQLite, biometrik suara, dan proyeksi visual HUD cerdas.", 0, None)
        ]
        cursor.executemany("""
            INSERT INTO notes_and_todos (speaker_id, category, title, content, is_completed, due_date)
            VALUES (?, ?, ?, ?, ?, ?)
        """, defaults)
        conn.commit()

    # ── Speaker Management & Voice Biometrics ────────────────────────────────

    def enroll_or_update_speaker(self, name: str, audio_pcm: Optional[bytes] = None) -> Dict[str, Any]:
        """Enrolls a new speaker or updates an existing speaker without duplicates."""
        clean_name = canonicalize_speaker_name(name)
        if not clean_name:
            return {"status": "error", "message": "Nama tidak valid"}

        emb = extract_voice_embedding(audio_pcm) if audio_pcm else None
        emb_json = json.dumps(emb.tolist()) if emb is not None else None

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, voice_embedding, sample_count FROM speakers WHERE name = ?", (clean_name,))
            existing = cursor.fetchone()

            if existing:
                speaker_id = existing["id"]
                count = existing["sample_count"] + (1 if emb is not None else 0)
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
            return {"status": "error", "message": "Sampel audio terlalu pendek untuk kalibrasi biometrik."}
        emb = extract_voice_embedding(audio_pcm)
        if emb is None:
            return {"status": "error", "message": "Gagal mengekstrak sidik suara dari audio. Pastikan Anda berbicara dengan jelas."}
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
                # Check if there is an existing registered speaker profile (like Agnan) waiting for initial voice registration
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

            # Precise threshold (0.58): accurately matches enrolled profiles while safely treating any different voice (e.g. friend/guest) as Tamu
            eff_threshold = 0.58

            if best_speaker and best_score >= eff_threshold:
                # Online Adaptive Moving Average Calibration: refine speaker embedding smoothly on confident matches
                try:
                    if best_score >= 0.80 and best_stored_emb is not None and len(best_stored_emb) == len(emb):
                        alpha = max(0.04, 1.0 / min(best_count + 1, 15))
                        adapted = ((1.0 - alpha) * best_stored_emb) + (alpha * emb)
                        adapted_norm = np.linalg.norm(adapted)
                        if adapted_norm > 1e-6:
                            adapted = adapted / adapted_norm
                            cursor.execute("""
                                UPDATE speakers 
                                SET voice_embedding = ?, sample_count = sample_count + 1, last_seen = CURRENT_TIMESTAMP 
                                WHERE id = ?
                            """, (json.dumps(adapted.tolist()), best_id))
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

    # ── Memory & Fact Management ─────────────────────────────────────────────

    def normalize_memory_key(self, raw_key: str) -> str:
        """Normalizes any variation of a preference key (e.g. lagu_favorit_baru) to its canonical key."""
        k = raw_key.strip().lower().replace("-", "_").replace(" ", "_")
        k = re.sub(r"_(?:baru|baruku|sekarang|ini|terbaru)$", "", k)
        if "band" in k or "grup_musik" in k:
            return "band_favorit"
        if "lagu" in k or "musik" in k:
            return "lagu_favorit"
        if "makan" in k or "kuliner" in k:
            return "makanan_favorit"
        if "minum" in k:
            return "minuman_favorit"
        if "hobi" in k or "kegemaran" in k:
            return "hobi"
        if "warna" in k:
            return "warna_favorit"
        if "film" in k or "movie" in k:
            return "film_favorit"
        if "game" in k or "permainan" in k:
            return "game_favorit"
        return k

    def store_memory(self, speaker_name: str, key: str, value: str, category: str = "preference") -> bool:
        """Stores or updates a specific fact or preference for a speaker, replacing and deduplicating old keys."""
        norm_key = self.normalize_memory_key(key)
        val_clean = value.strip().strip(".,!?\"'")
        
        # Guard against saving pronoun/temporal garbage as fact value
        INVALID_VALS = {"sekarang", "sekarang ini", "saat ini", "jadinya", "menjadi", "jadi", "ku", "saya", "aku", "kamu", "dia", "apa", "siapa", "mana", "kah", "dong", "sih", "nih", "ya", "yah", "ini", "itu", "ubah", "ganti", "mau"}
        if val_clean.lower() in INVALID_VALS or len(val_clean) < 2:
            logger.warning(f"[AnaraMemory] Rejected storing invalid value '{val_clean}' for key '{norm_key}'")
            return False

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM speakers WHERE name = ?", (speaker_name.strip().title(),))
            row = cursor.fetchone()
            if not row:
                res = self.enroll_or_update_speaker(speaker_name)
                speaker_id = res["speaker_id"]
            else:
                speaker_id = row["id"]

            # Remove any obsolete/rogue variant keys for this speaker (e.g. lagu_favorit_baru, band_favorit_baru)
            root_prefix = norm_key.split("_")[0]
            cursor.execute("""
                DELETE FROM memories
                WHERE speaker_id = ? AND key != ? AND (key LIKE ? OR key LIKE ?)
            """, (speaker_id, norm_key, f"{root_prefix}%", "%_baru%"))

            # Update canonical key
            cursor.execute("""
                INSERT INTO memories (speaker_id, category, key, value, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(speaker_id, key) DO UPDATE SET value = excluded.value, category = excluded.category, updated_at = CURRENT_TIMESTAMP
            """, (speaker_id, category, norm_key, val_clean))
            conn.commit()
            logger.info(f"[AnaraMemory] Saved canonical memory for {speaker_name}: [{norm_key}] = {val_clean} ({category})")
            self._emit_mutation("memory_stored", {
                "speaker_name": speaker_name.strip().title(),
                "key": norm_key,
                "value": val_clean,
                "category": category
            })
            return True

    def get_memories_for_speaker(self, speaker_name: str) -> List[Dict[str, Any]]:
        """Retrieves all stored facts and preferences for a speaker."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT m.id, m.category, m.key, m.value, m.created_at, m.updated_at
                FROM memories m
                JOIN speakers s ON m.speaker_id = s.id
                WHERE s.name = ?
                ORDER BY m.updated_at DESC
            """, (speaker_name.strip().title(),))
            return [dict(r) for r in cursor.fetchall()]

    def get_all_memories(self) -> List[Dict[str, Any]]:
        """Retrieves all memories across all speakers."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT m.id, s.name as speaker_name, m.category, m.key, m.value, m.created_at, m.updated_at
                FROM memories m
                LEFT JOIN speakers s ON m.speaker_id = s.id
                ORDER BY m.updated_at DESC
            """)
            return [dict(r) for r in cursor.fetchall()]

    def delete_memory_by_id(self, memory_id: int) -> bool:
        """Deletes a memory by its primary key ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            conn.commit()
            ok = cursor.rowcount > 0
            if ok:
                self._emit_mutation("memory_deleted", {"memory_id": memory_id})
            return ok

    def delete_memory(self, speaker_name: str, key: str) -> bool:
        """Deletes a specific memory key for a speaker."""
        norm_key = self.normalize_memory_key(key)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM memories
                WHERE (key = ? OR key = ?) AND speaker_id IN (
                    SELECT id FROM speakers WHERE name = ?
                )
            """, (norm_key, key.strip().lower(), speaker_name.strip().title()))
            conn.commit()
            logger.info(f"[AnaraMemory] Deleted memory key '{key}' for {speaker_name}")
            self._emit_mutation("memory_deleted", {
                "speaker_name": speaker_name.strip().title(),
                "key": norm_key
            })
            return True

    # ── AI Zero-Shot Memory & Fact Distillation ──────────────────────────────

    async def distill_and_store_memories_async(self, client: genai.Client, user_text: str, speaker_name: Optional[str] = None):
        """
        AI Contextual Distillation (Zero-Shot Lifelong Learning).
        Asynchronously parses implicit facts, tasks, and preferences mentioned casually in conversation
        and persists them directly to SQLite for the active speaker.
        """
        if not user_text or len(user_text.strip()) < 10 or not speaker_name:
            return

        clean_speaker = canonicalize_speaker_name(speaker_name)
        if not clean_speaker:
            return

        # Fast heuristic: only call LLM if sentence contains potential fact/todo markers
        FACT_MARKERS = [
            "aku", "saya", "gue", "gw", "lagi", "suka", "favorit", "sedang", "besok", "nanti",
            "mau", "ingin", "proyek", "project", "bikin", "belajar", "beli", "jadwal", "ujian",
            "rapat", "meeting", "kantor", "kuliah", "sekolah", "kerja", "hobi", "minum", "makan"
        ]
        u_lower = user_text.lower()
        if not any(m in u_lower for m in FACT_MARKERS):
            return

        try:
            prompt = (
                f"Analisis ucapan pengguna berikut dalam Bahasa Indonesia dari pembicara bernama '{clean_speaker}'.\n"
                f"Ucapan: \"{user_text}\"\n\n"
                f"Ekstraksi fakta implisit baru, preferensi pribadi, to-do/tugas, atau proyek yang sedang dikerjakan.\n"
                f"KEMBALIKAN HANYA JSON array murni tanpa markdown/penjelasan dengan skema:\n"
                f"[\n"
                f"  {{\"type\": \"preference\", \"key\": \"kunci_fakta_singkat\", \"value\": \"nilai fakta\", \"category\": \"preference\"}},\n"
                f"  {{\"type\": \"todo\", \"title\": \"judul tugas ringkas\", \"content\": \"rincian jika ada\", \"category\": \"todo\"}},\n"
                f"  {{\"type\": \"project\", \"name\": \"nama proyek\", \"tech_stack\": \"teknologi jika ada\", \"goal\": \"tujuan proyek\"}}\n"
                f"]\n"
                f"Jika TIDAK ADA fakta/tugas baru yang berharga untuk disimpan jangka panjang, kembalikan: []"
            )

            resp = await client.aio.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1,
                    max_output_tokens=300
                )
            )

            if resp and resp.text:
                raw_json = resp.text.strip()
                items = json.loads(raw_json)
                if isinstance(items, list):
                    for item in items:
                        t = item.get("type", "")
                        if t == "preference" and item.get("key") and item.get("value"):
                            self.store_memory(
                                speaker_name=clean_speaker,
                                key=str(item["key"]),
                                value=str(item["value"]),
                                category=str(item.get("category", "preference"))
                            )
                        elif t == "todo" and item.get("title"):
                            self.create_note_or_todo(
                                title=str(item["title"]),
                                content=str(item.get("content", "")),
                                category=str(item.get("category", "todo")),
                                speaker_name=clean_speaker
                            )
                        elif t == "project" and item.get("name"):
                            self.create_or_update_project(
                                name=str(item["name"]),
                                speaker_name=clean_speaker,
                                tech_stack=str(item.get("tech_stack", "")),
                                goal=str(item.get("goal", ""))
                            )
                    logger.info(f"[AI Distillation] Automatically persisted {len(items)} implicit items for {clean_speaker}")
        except Exception as e_distill:
            logger.debug(f"[AI Distillation Notice]: {e_distill}")

    # ── Notes & To-Do List Management (JARVIS Task Tracker) ──────────────────

    def create_note_or_todo(
        self,
        title: str,
        content: str = "",
        category: str = "todo",
        due_date: Optional[str] = None,
        speaker_name: Optional[str] = None
    ) -> int:
        """Creates a new note, to-do, or reminder item in SQLite."""
        speaker_id = None
        if speaker_name:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT id FROM speakers WHERE name = ?", (speaker_name.strip().title(),))
                r = cur.fetchone()
                if r:
                    speaker_id = r["id"]

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO notes_and_todos (speaker_id, category, title, content, is_completed, due_date, updated_at)
                VALUES (?, ?, ?, ?, 0, ?, CURRENT_TIMESTAMP)
            """, (speaker_id, category.strip().lower(), title.strip(), content.strip(), due_date))
            conn.commit()
            new_id = cursor.lastrowid or 0
            self._emit_mutation("todo_created", {
                "id": new_id,
                "speaker_name": speaker_name.strip().title() if speaker_name else None,
                "title": title.strip(),
                "category": category.strip().lower()
            })
            return new_id

    def get_notes_and_todos(self, category: Optional[str] = None, speaker_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieves active notes and to-dos."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = """
                SELECT n.id, n.category, n.title, n.content, n.is_completed, n.due_date,
                       n.created_at, n.updated_at, s.name as speaker_name
                FROM notes_and_todos n
                LEFT JOIN speakers s ON n.speaker_id = s.id
                WHERE 1=1
            """
            params = []
            if category:
                query += " AND n.category = ?"
                params.append(category.strip().lower())
            if speaker_name:
                query += " AND (s.name = ? OR n.speaker_id IS NULL)"
                params.append(speaker_name.strip().title())

            query += " ORDER BY n.is_completed ASC, n.updated_at DESC"
            cursor.execute(query, params)
            return [dict(r) for r in cursor.fetchall()]

    def toggle_todo(self, note_id: int) -> bool:
        """Toggles a to-do item between completed and active."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE notes_and_todos
                SET is_completed = CASE WHEN is_completed = 1 THEN 0 ELSE 1 END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (note_id,))
            conn.commit()
            ok = cursor.rowcount > 0
            if ok:
                self._emit_mutation("todo_toggled", {"id": note_id})
            return ok

    def delete_note_or_todo(self, note_id: int) -> bool:
        """Deletes a note or to-do by its ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM notes_and_todos WHERE id = ?", (note_id,))
            conn.commit()
            ok = cursor.rowcount > 0
            if ok:
                self._emit_mutation("todo_deleted", {"id": note_id})
            return ok

    # ── User Projects & Work Context Tracking (Episodic Assistant) ───────────

    def create_or_update_project(
        self,
        name: str,
        speaker_name: Optional[str] = None,
        tech_stack: str = "",
        goal: str = "",
        status: str = "active",
        notes: str = ""
    ) -> int:
        """Creates or updates an ongoing personal project for a speaker."""
        speaker_id = None
        if speaker_name:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT id FROM speakers WHERE name = ?", (speaker_name.strip().title(),))
                r = cur.fetchone()
                if r:
                    speaker_id = r["id"]

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM projects WHERE LOWER(name) = LOWER(?) AND (speaker_id = ? OR (speaker_id IS NULL AND ? IS NULL))", (name.strip(), speaker_id, speaker_id))
            existing = cursor.fetchone()
            if existing:
                proj_id = existing["id"]
                cursor.execute("""
                    UPDATE projects
                    SET tech_stack = COALESCE(NULLIF(?, ''), tech_stack),
                        goal = COALESCE(NULLIF(?, ''), goal),
                        status = COALESCE(NULLIF(?, ''), status),
                        notes = COALESCE(NULLIF(?, ''), notes),
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (tech_stack.strip(), goal.strip(), status.strip().lower(), notes.strip(), proj_id))
            else:
                cursor.execute("""
                    INSERT INTO projects (speaker_id, name, tech_stack, goal, status, notes, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (speaker_id, name.strip(), tech_stack.strip(), goal.strip(), status.strip().lower(), notes.strip()))
                proj_id = cursor.lastrowid or 0
            conn.commit()

            self._emit_mutation("project_saved", {
                "id": proj_id,
                "name": name.strip(),
                "speaker_name": speaker_name.strip().title() if speaker_name else None,
                "status": status.strip().lower()
            })
            return proj_id

    def get_projects_for_speaker(self, speaker_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieves active projects for a speaker."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = """
                SELECT p.id, p.name, p.tech_stack, p.goal, p.status, p.notes,
                       p.created_at, p.updated_at, s.name as speaker_name
                FROM projects p
                LEFT JOIN speakers s ON p.speaker_id = s.id
                WHERE 1=1
            """
            params = []
            if speaker_name:
                query += " AND (s.name = ? OR p.speaker_id IS NULL)"
                params.append(speaker_name.strip().title())
            query += " ORDER BY p.updated_at DESC"
            cursor.execute(query, params)
            return [dict(r) for r in cursor.fetchall()]

    def delete_project(self, project_id: int) -> bool:
        """Deletes a project by its primary key."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            conn.commit()
            ok = cursor.rowcount > 0
            if ok:
                self._emit_mutation("project_deleted", {"id": project_id})
            return ok

    # ── Episodic Conversation Logs (Multi-Session Memory) ────────────────────

    def log_conversation(
        self,
        user_text: str,
        ai_text: str,
        speaker_name: Optional[str] = None,
        media_type: Optional[str] = None,
        media_url: Optional[str] = None,
        visual_data: Optional[Dict[str, Any]] = None
    ) -> int:
        """Persists a full dialogue turn to SQLite conversations table."""
        speaker_id = None
        clean_name = speaker_name.strip().title() if speaker_name else None
        if clean_name:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT id FROM speakers WHERE name = ?", (clean_name,))
                r = cur.fetchone()
                if r:
                    speaker_id = r["id"]

        vis_json = json.dumps(visual_data) if visual_data else None

        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # ── Deduplication: Remove any previous identical user query so only 1 newest instance is kept ──
            if clean_name:
                cursor.execute("""
                    DELETE FROM conversations 
                    WHERE LOWER(TRIM(user_text)) = LOWER(?) AND speaker_name = ?
                """, (user_text.strip(), clean_name))
            else:
                cursor.execute("""
                    DELETE FROM conversations 
                    WHERE LOWER(TRIM(user_text)) = LOWER(?)
                """, (user_text.strip(),))

            cursor.execute("""
                INSERT INTO conversations (speaker_name, speaker_id, user_text, ai_text, media_type, media_url, visual_data_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (clean_name, speaker_id, user_text.strip(), ai_text.strip(), media_type, media_url, vis_json))
            last_id = cursor.lastrowid or 0

            # ── Auto-Pruning Policy: Keep only latest 30 dialogue turns to prevent accumulation ──
            cursor.execute("""
                DELETE FROM conversations
                WHERE id NOT IN (
                    SELECT id FROM conversations ORDER BY id DESC LIMIT 30
                )
            """)
            conn.commit()

        self._emit_mutation("conversation_logged", {
            "id": last_id,
            "speaker_name": clean_name,
            "user_text": user_text.strip(),
            "ai_text": ai_text.strip()
        })
        return last_id

    def delete_conversation_by_id(self, conversation_id: int) -> bool:
        """Deletes a single conversation log entry by its ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
            conn.commit()
            ok = cursor.rowcount > 0
            if ok:
                self._emit_mutation("conversation_deleted", {"id": conversation_id})
            return ok

    def get_recent_conversations(self, limit: int = 30, speaker_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieves recent conversation history from SQLite (newest first)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = """
                SELECT id, speaker_name, user_text, ai_text, media_type, media_url,
                       visual_data_json, created_at
                FROM conversations
            """
            params = []
            if speaker_name:
                query += " WHERE speaker_name = ?"
                params.append(speaker_name.strip().title())

            query += " ORDER BY id DESC LIMIT ?"
            params.append(limit)
            cursor.execute(query, params)
            rows = cursor.fetchall()
            result = []
            for r in rows:
                item = dict(r)
                if item.get("visual_data_json"):
                    try:
                        item["visual_data"] = json.loads(item["visual_data_json"])
                    except Exception:
                        item["visual_data"] = None
                result.append(item)
            return result

    def clear_conversations(self) -> bool:
        """Clears conversation logs."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM conversations")
            conn.commit()
            return True

    # ── Deterministic Intent & Command Parser ────────────────────────────────

    def extract_and_apply_intent(self, text: str, audio_pcm: Optional[bytes] = None, speaker_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Fast-path deterministic command parser for instant, 100% accurate database responses.
        Includes interactive confirmation before committing new facts & to-dos to SQLite.
        """
        norm = text.lower().strip()
        clean_norm = re.sub(r"^(?:halo|hai|hey|hei|oi|eh|woi)?\s*(?:anara|hanara|annara|anarah|nara)\s*[,:\-]?\s*", "", norm).strip()
        
        target_name = canonicalize_speaker_name(speaker_name) if speaker_name else self.get_last_active_speaker_name()

        # ── 0. Pending Proposal Confirmation / Rejection Check ──
        proposal_speaker = target_name or "Tamu"

        # Guard against visual / media / playback commands:
        # e.g. "ya tampilkan", "tampilkan fotonya", "lihat gambarnya", "tunjukkan", "putar lagu"
        # These are VISUAL / DISPLAY requests, NEVER database memory saving commands!
        VISUAL_OR_ACTION_WORDS = {
            "tampilkan", "tampilin", "tampilkanlah", "lihat", "liat", "tunjukkan", "tunjukan",
            "tujukin", "munculkan", "gambar", "foto", "visual", "video", "lagu", "musik", "nari",
            "joget", "dance", "dansa", "rumba", "putar", "puter", "mainkan", "play"
        }
        has_visual_action = any(re.search(rf"\b{w}\b", norm) for w in VISUAL_OR_ACTION_WORDS)

        p = self.get_pending_proposal(proposal_speaker)
        if p is not None:
            if has_visual_action:
                # User has moved on to asking for visual/media display. Clear stale memory proposal.
                self.reject_pending_proposal(proposal_speaker)
            else:
                # ── Multi-Entity Choice Disambiguation ──
                if p.get("is_multi_entity") and p.get("entities"):
                    ent_list = p.get("entities", [])
                    # 1. User picks both ("keduanya", "dua-duanya", "semua", "semuanya", "keduanya boleh")
                    if re.search(r"\b(?:keduanya|dua-duanya|semua|semuanya|keduanya\s+boleh|dua-duanya\s+boleh|dua\s+duanya|keduanya\s+aja|dua\s+duanya\s+aja)\b", norm):
                        combined_val = " dan ".join(e.title() for e in ent_list)
                        p["value"] = combined_val
                        p["is_multi_entity"] = False
                        msg = self.commit_pending_proposal(proposal_speaker)
                        if msg:
                            return {"type": "direct_answer", "reply_text": msg}
                    # 2. User picks one specific entity from the list (e.g. "kucing" or "panda")
                    else:
                        chosen_entity = None
                        for ent in ent_list:
                            clean_e = ent.lower().strip()
                            if len(clean_e) >= 2 and re.search(rf"\b{re.escape(clean_e)}\b", norm):
                                chosen_entity = ent
                                break
                        if chosen_entity:
                            p["value"] = chosen_entity.title()
                            p["is_multi_entity"] = False
                            msg = self.commit_pending_proposal(proposal_speaker)
                            if msg:
                                return {"type": "direct_answer", "reply_text": msg}

                # Explicit Memory/Task Confirmation: "iya", "ya simpan", "simpan", "catat", "iya betul", "simpan aja", "ya hapus", "boleh", "ingat ya", "ya boleh"
                is_confirm = (
                    re.search(r"^(?:iya|ya|simpan|catat|ok|oke|yes|betul|benar|yup|yoi|setuju|mau|boleh|siap|ingat\s+ya|ingatlah|ya\s+boleh|iya\s+boleh)(?:\s+(?:simpan|catat|ke\s+database|di\s+database|aja|deh|dong|ya|yah|nih|betul|benar|hewan|makanan|band|lagu|minuman|hobi|warna|film|game|profil|semuanya|keduanya|boleh))?$", norm) or
                    re.search(r"\b(?:simpan\s+ke\s+database|catat\s+ke\s+database|iya\s+simpan|ya\s+simpan|iya\s+catat|ya\s+catat|tolong\s+simpan|tolong\s+catat|ya\s+hapus|iya\s+hapus|boleh\s+ingat|tolong\s+ingat|ya\s+boleh|iya\s+boleh|boleh\s+banget)\b", norm)
                )
                if is_confirm:
                    msg = self.commit_pending_proposal(proposal_speaker)
                    if msg:
                        return {"type": "direct_answer", "reply_text": msg}
                # Rejection: Jangan, nggak, enggak, gak, tidak, batal, batalin, salah, nggak usah, gak usah, no, jangan disimpan
                elif re.search(r"\b(?:tidak|jangan|nggak|enggak|gak|batal|batalin|salah|nggak\s+usah|gak\s+usah|no|jangan\s+disimpan|jangan\s+simpan|ga\s+usah|bukan|ngga)\b", norm):
                    msg = self.reject_pending_proposal(proposal_speaker)
                    if msg:
                        return {"type": "direct_answer", "reply_text": msg}

        # ── 0.1 Contextual Fallback Confirmation for Name Enrollment when Proposal is None ──
        is_generic_confirm = bool(
            re.search(r"^(?:iya|ya|simpan|catat|ok|oke|yes|betul|benar|yup|yoi|setuju|mau|boleh|siap|ingat\s+ya|ingatlah|ya\s+boleh|iya\s+boleh|boleh\s+banget)(?:\s+(?:simpan|catat|ke\s+database|di\s+database|aja|deh|dong|ya|yah|nih|betul|benar|profil|namaku|nama|suara))?$", norm) or
            re.search(r"\b(?:ya\s+boleh|iya\s+boleh|boleh\s+ingat|boleh\s+catat|tolong\s+simpan|tolong\s+catat|simpan\s+namaku|catat\s+namaku)\b", norm)
        )
        if is_generic_confirm and p is None:
            recent_logs = self.get_recent_conversations(limit=4)
            for log in recent_logs:
                a_txt = (log.get("ai_text") or "").lower()
                u_txt = (log.get("user_text") or "").lower()
                m_ai_name = re.search(r"(?:dipanggil|namamu|nama\s+kamu|nama|halo|hai)\s*['\"]?([a-zA-Z]+)['\"]?.*(?:boleh\s+mengingatnya|boleh\s+catat|boleh\s+ingat|diingat)", a_txt)
                if not m_ai_name:
                    m_ai_name = re.search(r"\b(?:kenalin|kenalkan|perkenalkan)\s+(?:aku|saya|nama\s+saya)\s+([a-zA-Z]+)", u_txt)
                if not m_ai_name:
                    m_ai_name = re.search(r"\b(?:namaku|nama\s+saya)\s+([a-zA-Z]+)", u_txt)
                
                if m_ai_name:
                    cand_name = m_ai_name.group(1).strip().title()
                    INVALID_NAMES = {"anara", "halo", "kamu", "saya", "aku", "dia", "tahu", "tau", "ingat", "catat", "siapa", "apa", "mana", "kenapa", "mengapa", "bagaimana", "gimana", "adnan", "ya", "yah", "nih", "dong", "kan", "lah", "deh", "oke", "siap", "baik"}
                    if len(cand_name) >= 3 and cand_name.lower() not in INVALID_NAMES:
                        self.enroll_or_update_speaker(cand_name, audio_pcm)
                        return {
                            "type": "introduction",
                            "speaker_name": cand_name,
                            "is_new": True,
                            "reply_text": f"Siap {cand_name}! Profilmu resmi aktif dan tersimpan di database Anara."
                        }

        # ── 0.5 Contextual Pronoun Directives ("simpan itu ke database sebagai hewan favorit saya", "catat ini sebagai makanan kesukaanku", "jadikan itu band favoritku") ──
        is_contextual_pronoun_cmd = bool(
            re.search(r"\b(?:simpan|catat|masukkan|jadikan|jadikanlah|tambahkan|taruh|input)\s+(?:itu|ini|tersebut|hal\s+itu|hal\s+ini|foto\s+itu|foto\s+ini|gambar\s+itu|gambar\s+ini)\b", clean_norm) or
            re.search(r"\b(?:sebagai|jadi)\s+(?:hewan|binatang|makanan|minuman|band|lagu|musik|film|movie|game|hobi|kendaraan|mobil|motor|warna|tipe|kriteria)\s+(?:favorit|favourite|kesukaan|impian|fav)?(?:ku| saya)?\b", clean_norm)
        )
        if is_contextual_pronoun_cmd:
            recent_chats = self.get_recent_conversations(limit=4)
            if recent_chats:
                eff_name = target_name or "Tamu"
                ctx_res = resolve_contextual_memory_command(text, recent_chats, eff_name)
                if ctx_res and ctx_res.get("resolved_entity"):
                    entity = ctx_res["resolved_entity"].strip().title()
                    key = ctx_res.get("canonical_key", "preferensi_kesukaan")
                    title_lbl = ctx_res.get("category_label", "preferensi kesukaan")
                    prompt_msg = ctx_res.get("confirmation_prompt") or f"Bahwa {entity} adalah {title_lbl} kamu, Anara boleh mengingatnya, {eff_name}?"
                    
                    self.set_pending_proposal(eff_name, {
                        "type": "fact",
                        "key": key,
                        "value": entity,
                        "category": "preference",
                        "title": title_lbl
                    })
                    return {
                        "type": "direct_answer",
                        "reply_text": prompt_msg
                    }

        # ── 1. Introduction, Enrollment & Save Name (Instant enrollment & SQLite persistence) ──
        STOP_WORDS = {
            "anara", "halo", "hai", "oi", "hey", "aku", "saya", "gue", "gw", "mau", "maunya", "pengen", "ingin", "lagi",
            "bisa", "punya", "punyanya", "sedang", "suka", "sukanya", "tahu", "tau", "ada", "tidak", "gak", "nggak", "senang",
            "bukan", "nih", "dong", "lho", "deh", "kan", "kok", "itu", "ini", "dia", "sini", "situ",
            "siapa", "apa", "sama", "kamu", "jangan", "lupa", "ya", "yah", "disini", "banget", "orang",
            "bicara", "ngobrol", "tanya", "jawab", "baca", "lihat", "catat", "simpan", "dengan", "menarik",
            "seperti", "tentang", "karena", "untuk", "dalam", "pada", "kalau", "jika", "adalah", "juga",
            "hari", "malam", "siang", "pagi", "sore", "yang", "dan", "dari", "ke", "di", "tolong", "coba",
            "ayo", "hibur", "tarian", "nari", "joget", "dance", "dansa", "rumba", "musik", "lagu",
            "sekarang", "tadi", "dulu", "nanti", "boleh", "harus", "udah", "sudah", "belum", "baru", "paling", "sangat",
            "makanan", "minuman", "band", "hobi", "game", "film", "siap", "baik", "oke", "jadinya", "menjadi", "jadi", "database"
        }
        enroll_patterns = [
            r"\b(?:kenalin|kenalkan|perkenalkan)\s+(?:aku|saya|gue|gw|nama\s+saya)\s+([a-zA-Z]+)",
            r"\b(?:kalibrasi|daftarkan|rekam|simpan)\s+(?:sidik\s+)?suara\s+(?:saya|ku|untuk\s+)?\s*([a-zA-Z]+)",
            r"\b(?:ingat|daftarkan|catat|kalibrasi|rekam|simpan)\s+(?:dan\s+simpan\s+)?(?:ya\s+)?(?:nama(?:ku| saya)|suara(?:ku| saya)|profil(?:ku| saya))\s*(?:sebagai\s+|=|\s+ke\s+database\s+ya|\s+ke\s+database|\s+)?\s*([a-zA-Z]+)",
            r"\b(?:ingat|simpan|catat|daftarkan)\s+(?:ya\s+)?namaku\s+([a-zA-Z]+)",
            r"\bnamaku\s+([a-zA-Z]+)\b",
            r"\bnama\s+saya\s+([a-zA-Z]+)\b",
            r"\bpanggil\s+aku\s+([a-zA-Z]+)\b",
            r"^(?:halo|hai|hey|hei)?\s*(?:anara|nara)?\s*,?\s*(?:ini\s+)?(?:aku|saya|gue|gw)\s+([a-zA-Z]+)(?:\s+ya|\s+nih|\s+dong|\s+ke\s+database)?$",
            r"\b(?:aku|saya|gue|gw)\s+([a-zA-Z]+)(?:\s+ya|\s+nih|\s+dong)?$",
        ]

        extracted_name = None
        for pat in enroll_patterns:
            m = re.search(pat, clean_norm) or re.search(pat, norm)
            if m and m.group(1):
                cand = m.group(1).strip().title()
                if len(cand) >= 3 and cand.lower() not in STOP_WORDS:
                    extracted_name = cand
                    break

        # Contextual save name: "ingat dan simpan namaku ya", "simpan namaku ya", "catat namaku", "ingat namaku ya", "simpan ke database ya"
        if not extracted_name and re.search(r"\b(?:ingat|simpan|catat|daftarkan|rekam)\s+(?:dan\s+simpan\s+)?(?:ya\s+)?(?:nama(?:ku| saya)|profil(?:ku| saya)|suara(?:ku| saya))\b", norm):
            if target_name:
                extracted_name = target_name
            else:
                recent_logs = self.get_recent_conversations(limit=6)
                for log in recent_logs:
                    u_txt = (log.get("user_text") or "").lower()
                    a_txt = (log.get("ai_text") or "").lower()
                    for p in [
                        r"\b(?:kenalin|kenalkan|perkenalkan)\s+(?:aku|saya|nama\s+saya)\s+([a-zA-Z]+)",
                        r"\bnamaku\s+([a-zA-Z]+)",
                        r"\bnama\s+saya\s+([a-zA-Z]+)",
                        r"\bpanggil\s+aku\s+([a-zA-Z]+)",
                        r"\b(?:aku|saya)\s+([a-zA-Z]+)",
                    ]:
                        m_prev = re.search(p, u_txt)
                        if m_prev and m_prev.group(1).lower() not in STOP_WORDS:
                            extracted_name = m_prev.group(1).strip().title()
                            break
                    if not extracted_name:
                        # Check AI confirmation quotes: e.g. "dipanggil 'Ratno'" or "Halo Ratno"
                        m_ai = re.search(r"(?:dipanggil|halo|hai)\s*['\"]?([a-zA-Z]+)['\"]?", a_txt)
                        if m_ai and m_ai.group(1).lower() not in STOP_WORDS:
                            extracted_name = m_ai.group(1).strip().title()
                    if extracted_name:
                        break

        if extracted_name:
            clean_sp_name = canonicalize_speaker_name(extracted_name) or extracted_name
            is_chat_mode = (audio_pcm is None)

            # Check if speaker already exists in SQLite
            existing_sp = None
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM speakers WHERE LOWER(name) = LOWER(?)", (clean_sp_name,))
                row = cursor.fetchone()
                if row:
                    existing_sp = row["name"]

            if existing_sp:
                if is_chat_mode:
                    mems = self.get_memories_for_speaker(existing_sp)
                    if mems:
                        top_facts = [f"{mem['key'].replace('_', ' ')} '{mem['value']}'" for mem in mems[:2]]
                        reply_text = f"Halo {existing_sp}! Profilmu telah tersimpan dan aktif di database Anara beserta preferensimu seperti {', '.join(top_facts)}."
                    else:
                        reply_text = f"Halo {existing_sp}! Profilmu sekarang tersimpan dan aktif di database Anara."
                    return {
                        "type": "introduction",
                        "speaker_name": existing_sp,
                        "is_new": False,
                        "reply_text": reply_text
                    }
                else:
                    self.enroll_or_update_speaker(existing_sp, audio_pcm)
                    mems = self.get_memories_for_speaker(existing_sp)
                    if mems:
                        top_facts = [f"{mem['key'].replace('_', ' ')} '{mem['value']}'" for mem in mems[:2]]
                        reply_text = f"Halo {existing_sp}! Sidik suaramu terkalibrasi dan tersimpan di database. Profilmu aktif bersama preferensimu seperti {', '.join(top_facts)}."
                    else:
                        reply_text = f"Halo {existing_sp}! Sidik suaramu terkalibrasi dan profilmu sekarang aktif tersimpan di database."
                    return {
                        "type": "introduction",
                        "speaker_name": existing_sp,
                        "is_new": False,
                        "reply_text": reply_text
                    }
            else:
                self.enroll_or_update_speaker(clean_sp_name, audio_pcm)
                if is_chat_mode:
                    reply_text = f"Halo {clean_sp_name}! Profilmu resmi disimpan dan aktif di database Anara."
                else:
                    reply_text = f"Halo {clean_sp_name}! Senang berkenalan denganmu. Namamu dan sidik suaramu resmi disimpan di database Anara!"
                return {
                    "type": "introduction",
                    "speaker_name": clean_sp_name,
                    "is_new": True,
                    "reply_text": reply_text
                }

        # ── 1.5 Delete Profile (Asks Confirmation First!) ──
        del_speaker_match = re.search(r"\bhapus\s+(?:profil|profile|data|user|akun)(?:ku| saya|\s+saya|\s+ku)?(?:\s+([a-zA-Z]+))?\b", clean_norm)
        if del_speaker_match:
            target_del = del_speaker_match.group(1).strip().title() if del_speaker_match.group(1) else (target_name or "Tamu")
            if target_del.lower() not in {"anara", "profil", "profile", "data"}:
                eff_name = target_name or target_del
                self.set_pending_proposal(eff_name, {
                    "type": "delete_speaker",
                    "target_speaker": target_del
                })
                return {
                    "type": "direct_answer",
                    "reply_text": f"Apakah kamu yakin ingin menghapus seluruh profil {target_del} beserta semua ingatan dan catatan dari database? (Katakan atau ketik 'ya hapus' atau 'tidak')"
                }

        # ── 2. Update / Change Preference Command ("ubah band fav ku", "ganti makanan favoritku") ──
        update_match = re.search(r"\b(?:ubah|ganti|update|gantilah)\s+(?:nama\s+)?(band|lagu|musik|makanan|minuman|hobi|warna|film|game)(?:\s+(?:favorit|favourite|kesukaan|fav))?(?:ku| saya|\s+ku|\s+saya)?(?:\s+(?:menjadi|jadi|ke|adalah|=|:)\s*([a-zA-Z0-9\s\-]+))?", clean_norm)
        if update_match:
            cat_type = update_match.group(1).lower()
            new_val = update_match.group(2).strip().strip(".,!?\"'") if update_match.group(2) else ""
            key_map = {
                "band": ("band_favorit", "preference", "band favorit"),
                "lagu": ("lagu_favorit", "preference", "lagu favorit"),
                "musik": ("lagu_favorit", "preference", "lagu favorit"),
                "makanan": ("makanan_favorit", "preference", "makanan favorit"),
                "minuman": ("minuman_favorit", "preference", "minuman kesukaan"),
                "hobi": ("hobi", "preference", "hobi"),
                "warna": ("warna_favorit", "preference", "warna favorit"),
                "film": ("film_favorit", "preference", "film favorit"),
                "game": ("game_favorit", "preference", "game favorit"),
            }
            if cat_type in key_map:
                key, cat, title_lbl = key_map[cat_type]
                eff_name = target_name or "Tamu"
                INVALID_FACT_VALUES = {"ku", "saya", "aku", "kamu", "dia", "apa", "siapa", "mana", "kah", "dong", "sih", "nih", "ya", "yah", "ini", "itu", "ubah", "ganti", "mau", "jadi", "menjadi"}
                if new_val and len(new_val) >= 2 and new_val.lower() not in INVALID_FACT_VALUES:
                    self.set_pending_proposal(eff_name, {
                        "type": "fact",
                        "key": key,
                        "value": new_val.title(),
                        "category": cat,
                        "title": title_lbl
                    })
                    return {
                        "type": "direct_answer",
                        "reply_text": f"Baik {eff_name}, bahwa {title_lbl} kamu sekarang adalah '{new_val.title()}', Anara boleh mengingatnya?"
                    }
                else:
                    return {
                        "type": "direct_answer",
                        "reply_text": f"Kamu ingin mengubah {title_lbl} menjadi apa, {eff_name}? Beri tahu nama barunya (contoh: '{title_lbl} baru kamu') ya!"
                    }

        # ── 3. Direct Specific Fact / Memory Lookups (Zero-latency instant database answers) ──
        # Check "siapa namaku" / "siapa aku" / "kamu tahu siapa aku" / "kamu kenal aku" / "kamu tahu namaku"
        identity_patterns = (
            r"\b(?:"
            r"siapa\s+namaku|namaku\s+siapa|"
            r"siapa\s+nama\s+saya|nama\s+saya\s+siapa|"
            r"siapa\s+aku|aku\s+siapa|"
            r"siapa\s+saya|saya\s+siapa|"
            r"(?:kamu|lu|elo|lo|anara)?\s*(?:tahu|tau|kenal|ingat)\s+(?:gak|nggak|ga|ngga)?\s*(?:siapa\s+)?(?:aku|saya|gue|gw|namaku|nama\s+saya)|"
            r"(?:kamu|lu|elo|lo|anara)?\s*(?:tahu|tau|kenal|ingat)\s+namaku|"
            r"(?:kenal|ingat|tahu|tau)\s+(?:aku|saya|gue|gw)|"
            r"(?:apakah\s+)?(?:kamu\s+)?(?:mengenal|mengingat|mengenali)\s*(?:aku|saya|ku|suaraku|suara\s+saya)|"
            r"(?:kamu\s+)?(?:kenal|tahu|tau|ingat)\s+(?:sama\s+)?(?:suara(?:ku| saya)|sidik\s+suara(?:ku| saya))(?:\s+gak|\s+nggak|\s+ga)?|"
            r"suara\s+siapa\s+ini|ini\s+suara\s+siapa|"
            r"ini\s+siapa|siapa\s+yang\s+(?:lagi\s+)?bicara|"
            r"tau\s+ga\s+aku\s+siapa|tahu\s+gak\s+aku\s+siapa"
            r")\b"
        )
        if re.search(identity_patterns, norm):
            if target_name:
                mems = self.get_memories_for_speaker(target_name)
                if mems:
                    top_facts = [f"{mem['key'].replace('_', ' ')} '{mem['value']}'" for mem in mems[:2]]
                    return {
                        "type": "direct_answer",
                        "reply_text": f"Dari sidik suaramu, kamu adalah {target_name}! Aku mengenali suaramu dan mengingat preferensimu seperti {', '.join(top_facts)}."
                    }
                else:
                    return {
                        "type": "direct_answer",
                        "reply_text": f"Dari sidik suaramu, kamu adalah {target_name}! Aku mengenali suaramu dan seluruh preferensimu di database Anara."
                    }
            else:
                return {
                    "type": "direct_answer",
                    "reply_text": "Aku belum mengenali sidik suaramu nih. Kamu bisa mengenalkan nama dan suaramu (contoh: 'Halo Anara, kenalkan aku [Nama Kamu]') agar aku bisa mendaftarkan profilmu di database!"
                }

        # Check "apa band favoritku" / "band kesukaanku siapa" / "band kesukaanku apa"
        if not re.search(r"\b(?:ubah|ganti|update|set)\b", norm) and re.search(r"\b(?:(?:apa|siapa|sebutkan)\s+(?:nama\s+)?band\s+(?:favorit|favourite|kesukaan|fav)(?:ku| saya|\s+ku|\s+saya)?|band\s+(?:favorit|favourite|kesukaan|fav)(?:ku| saya|\s+ku|\s+saya)?\s+(?:apa|siapa|mana|kah)|grup\s+musik\s+(?:favorit|favourite|kesukaan|fav)(?:ku| saya|\s+ku|\s+saya)?)\b", norm):
            if not target_name:
                return {
                    "type": "direct_answer",
                    "reply_text": "Beri tahu dulu siapa namamu (contoh: 'Halo Anara, kenalkan aku [Nama Kamu]') agar aku bisa membuka catatan preferensimu di database!"
                }
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT m.value FROM memories m
                    JOIN speakers s ON m.speaker_id = s.id
                    WHERE s.name = ? AND m.key LIKE '%band%'
                    ORDER BY m.id DESC LIMIT 1
                """, (target_name,))
                row = cursor.fetchone()
                if row:
                    return {
                        "type": "direct_answer",
                        "reply_text": f"Band favoritmu yang tersimpan di database adalah {row['value']}!"
                    }
                return {
                    "type": "direct_answer",
                    "reply_text": f"Aku belum memiliki catatan band favorit untuk profil {target_name}. Kamu bisa memberi tahu aku (misal: 'Band favoritku Avenged Sevenfold')."
                }

        # Check "apa lagu favoritku" / "lagu kesukaanku apa"
        if re.search(r"\b(?:(?:apa|siapa|sebutkan)\s+(?:judul\s+)?lagu\s+(?:favorit|favourite|kesukaan|fav)(?:ku| saya|\s+ku|\s+saya)?|lagu\s+(?:favorit|favourite|kesukaan|fav)(?:ku| saya|\s+ku|\s+saya)?(?:\s+(?:apa|siapa|mana|kah))?|musik\s+(?:favorit|favourite|kesukaan|fav)(?:ku| saya|\s+ku|\s+saya)?)\b", norm):
            if not target_name:
                return {
                    "type": "direct_answer",
                    "reply_text": "Beri tahu dulu siapa namamu (contoh: 'Halo Anara, kenalkan aku [Nama Kamu]') agar aku bisa membuka catatan preferensimu di database!"
                }
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT m.value FROM memories m
                    JOIN speakers s ON m.speaker_id = s.id
                    WHERE s.name = ? AND (m.key LIKE '%lagu%' OR m.key LIKE '%music%')
                    ORDER BY m.id DESC LIMIT 1
                """, (target_name,))
                row = cursor.fetchone()
                if row:
                    return {
                        "type": "direct_answer",
                        "reply_text": f"Lagu favoritmu yang tersimpan di database adalah {row['value']}!"
                    }
                return {
                    "type": "direct_answer",
                    "reply_text": f"Aku belum memiliki catatan lagu favorit untuk profil {target_name}. Kamu bisa memberi tahu aku kapan saja!"
                }

        # Check "apa makanan favoritku" / "makanan kesukaanku apa"
        if re.search(r"\b(?:(?:apa|siapa|sebutkan)\s+makanan\s+(?:favorit|favourite|kesukaan|fav|yang\s+aku\s+suka)(?:ku| saya|\s+ku|\s+saya)?|makanan\s+(?:favorit|favourite|kesukaan|fav)(?:ku| saya|\s+ku|\s+saya)?(?:\s+(?:apa|siapa|mana|kah))?|apa\s+makanan\s+yang\s+(?:aku|saya)\s+suka)\b", norm):
            if not target_name:
                return {
                    "type": "direct_answer",
                    "reply_text": "Beri tahu dulu siapa namamu (contoh: 'Halo Anara, kenalkan aku [Nama Kamu]') agar aku bisa membuka catatan preferensimu di database!"
                }
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT m.value FROM memories m
                    JOIN speakers s ON m.speaker_id = s.id
                    WHERE s.name = ? AND m.key LIKE '%makan%'
                    ORDER BY m.id DESC LIMIT 1
                """, (target_name,))
                row = cursor.fetchone()
                if row:
                    return {
                        "type": "direct_answer",
                        "reply_text": f"Makanan kesukaanmu di database adalah {row['value']}!"
                    }
                return {
                    "type": "direct_answer",
                    "reply_text": f"Aku belum memiliki catatan makanan kesukaan untuk profil {target_name}."
                }

        # Check "apa hobiku" / "hobi kesukaanku apa"
        if re.search(r"\b(?:(?:apa|siapa|sebutkan)\s+hobi(?:ku| saya|\s+ku|\s+saya)?|hobi(?:ku| saya|\s+ku|\s+saya)?(?:\s+(?:apa|siapa|mana|kah))?|apa\s+kegemaran(?:ku| saya|\s+ku|\s+saya)?)\b", norm):
            if not target_name:
                return {
                    "type": "direct_answer",
                    "reply_text": "Beri tahu dulu siapa namamu (contoh: 'Halo Anara, kenalkan aku [Nama Kamu]') agar aku bisa membuka catatan hobimu di database!"
                }
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT m.value FROM memories m
                    JOIN speakers s ON m.speaker_id = s.id
                    WHERE s.name = ? AND m.key LIKE '%hobi%'
                    ORDER BY m.id DESC LIMIT 1
                """, (target_name,))
                row = cursor.fetchone()
                if row:
                    return {
                        "type": "direct_answer",
                        "reply_text": f"Hobimu yang tercatat di database adalah {row['value']}!"
                    }
                return {
                    "type": "direct_answer",
                    "reply_text": f"Aku belum memiliki catatan hobi untuk profil {target_name}."
                }



        # ── JARVIS 2.0 Smart Action Tool: Holographic HUD Timer ──
        timer_match = re.search(r"\b(?:set|pasang|atur|mulai|buat)?\s*timer\s+(\d+)\s*(menit|detik|jam)(?:\s+(?:untuk|buat|buatkan|label)?\s*([a-zA-Z0-9\s\-]+))?", norm)
        if timer_match:
            qty = int(timer_match.group(1))
            unit = timer_match.group(2)
            raw_label = timer_match.group(3)
            label = raw_label.strip().title() if raw_label and len(raw_label.strip()) > 1 else "Timer Anara"
            total_seconds = qty * 60 if unit == "menit" else (qty * 3600 if unit == "jam" else qty)
            eff_name = target_name or "Tamu"
            return {
                "type": "hud_timer",
                "duration_seconds": total_seconds,
                "label": label,
                "reply_text": f"Baik {eff_name}, timer '{label}' selama {qty} {unit} telah Anara aktifkan di layar HUD."
            }

        # ── 4. Proposing New Fact / Preference (Asks Confirmation First!) ──
        # Do not treat questions with "apa", "siapa", "mana", "apakah" or commands with "ubah", "ganti" as direct preference setting commands!
        if not re.search(r"\b(?:apa|apakah|siapa|kenapa|mengapa|bagaimana|gimana|mana|ubah|ganti|update)\b", norm):
            clean_fact_text = re.sub(r"\b(?:tambah|tambahkan|simpan|catat|masukkan)\s+(?:ke\s+database|ke\s+ingatan|ke\s+memori|di\s+database)\b", "", text, flags=re.IGNORECASE).strip()
            
            preference_patterns = [
                (r"\b(?:band|grup\s+musik)\s+(?:favorit|favourite|kesukaan|fav)(?:ku| saya|\s+ku|\s+saya)?\s*(?:sekarang\s+)?(?:adalah\s+|yaitu\s+|=|:|\s+itu\s+)?\s*([a-zA-Z0-9\s\-]+)", "band_favorit", "preference", "band favorit"),
                (r"\b(?:lagu|musik)\s+(?:favorit|favourite|kesukaan|fav)(?:ku| saya|\s+ku|\s+saya)?\s*(?:sekarang\s+)?(?:adalah\s+|yaitu\s+|=|:|\s+itu\s+)?\s*([a-zA-Z0-9\s\-]+)", "lagu_favorit", "preference", "lagu favorit"),
                (r"\b(?:makanan|kuliner)\s+(?:favorit|favourite|kesukaan|fav)(?:ku| saya|\s+ku|\s+saya)?\s*(?:sekarang\s+)?(?:adalah\s+|yaitu\s+|=|:|\s+itu\s+)?\s*([a-zA-Z0-9\s\-]+)", "makanan_favorit", "preference", "makanan favorit"),
                (r"\b(?:minuman)\s+(?:favorit|favourite|kesukaan|fav)(?:ku| saya|\s+ku|\s+saya)?\s*(?:sekarang\s+)?(?:adalah\s+|yaitu\s+|=|:|\s+itu\s+)?\s*([a-zA-Z0-9\s\-]+)", "minuman_favorit", "preference", "minuman kesukaan"),
                (r"\b(?:hobi|kegemaran)(?:ku| saya|\s+ku|\s+saya)?\s*(?:sekarang\s+)?(?:adalah\s+|yaitu\s+|=|:|\s+itu\s+)?\s*([a-zA-Z0-9\s\-]+)", "hobi", "preference", "hobi"),
                (r"\b(?:warna)\s+(?:favorit|favourite|kesukaan|fav)(?:ku| saya|\s+ku|\s+saya)?\s*(?:sekarang\s+)?(?:adalah\s+|yaitu\s+|=|:|\s+itu\s+)?\s*([a-zA-Z0-9\s\-]+)", "warna_favorit", "preference", "warna favorit"),
                (r"\b(?:film|movie)\s+(?:favorit|favourite|kesukaan|fav)(?:ku| saya|\s+ku|\s+saya)?\s*(?:sekarang\s+)?(?:adalah\s+|yaitu\s+|=|:|\s+itu\s+)?\s*([a-zA-Z0-9\s\-]+)", "film_favorit", "preference", "film favorit"),
                (r"\b(?:game|permainan)\s+(?:favorit|favourite|kesukaan|fav)(?:ku| saya|\s+ku|\s+saya)?\s*(?:sekarang\s+)?(?:adalah\s+|yaitu\s+|=|:|\s+itu\s+)?\s*([a-zA-Z0-9\s\-]+)", "game_favorit", "preference", "game favorit"),
                (r"\b(?:hewan|binatang|peliharaan)\s+(?:favorit|favourite|kesukaan|fav)(?:ku| saya|\s+ku|\s+saya)?\s*(?:sekarang\s+)?(?:adalah\s+|yaitu\s+|=|:|\s+itu\s+)?\s*([a-zA-Z0-9\s\-]+)", "hewan_favorit", "preference", "hewan kesukaan"),
                (r"\b(?:tipe\s+(?:cewek|wanita|pasangan|perempuan|pria|cowok)|kriteria\s+(?:pasangan|cewek|wanita))(?:ku| saya|\s+ku|\s+saya)?\s*(?:sekarang\s+)?(?:adalah\s+|yaitu\s+|=|:|\s+itu\s+)?\s*([a-zA-Z0-9\s\-]+)", "tipe_wanita_kesukaan", "preference", "tipe wanita kesukaan"),
                (r"\b(?:saya|aku|gue|gw)\s+(?:suka|tertarik\s+(?:sama|dengan)|gemar)\s+(?:tipe\s+)?(wanita\s+[a-zA-Z0-9\s\-]+|cewek\s+[a-zA-Z0-9\s\-]+)", "tipe_wanita_kesukaan", "preference", "tipe wanita kesukaan"),
                (r"\b(?:saya|aku|gue|gw)\s+(?:suka|tertarik\s+(?:sama|dengan)|gemar)\s+([a-zA-Z0-9\s\-]+)", "preferensi_kesukaan", "preference", "preferensi kesukaan"),
                (r"\b(?:tempat\s+tinggal|domisili|kota\s+asal|asal)(?:ku| saya|\s+ku|\s+saya)?\s*(?:sekarang\s+)?(?:adalah\s+|yaitu\s+|=|:|\s+itu\s+|di\s+)?\s*([a-zA-Z0-9\s\-]+)", "tempat_tinggal", "personal", "tempat tinggal"),
                (r"\b(?:pekerjaan|profesi|jabatan|kantor)(?:ku| saya|\s+ku|\s+saya)?\s*(?:sekarang\s+)?(?:adalah\s+|yaitu\s+|=|:|\s+itu\s+|sebagai\s+)?\s*([a-zA-Z0-9\s\-]+)", "pekerjaan", "work", "pekerjaan"),
            ]

            INVALID_FACT_VALUES = {"ku", "saya", "aku", "kamu", "dia", "apa", "siapa", "mana", "kah", "dong", "sih", "nih", "ya", "yah", "ini", "itu", "ubah", "ganti", "mau", "jadi", "menjadi", "nari", "menari", "joget", "dance"}

            for pat, key, cat, title_lbl in preference_patterns:
                m = re.search(pat, clean_fact_text, re.IGNORECASE) or re.search(pat, text, re.IGNORECASE)
                if m:
                    extracted_val = m.group(1).strip().strip(".,!?\"'")
                    # Clean leading temporal / conversational prefixes (e.g. 'sekarang ayam goreng' -> 'ayam goreng')
                    extracted_val = re.sub(r"^(?:sekarang(?:\s+ini)?|saat\s+ini|jadinya|menjadi|jadi|adalah|yaitu|itu|itu\s+sih|sih|dong|deh|berubah\s+jadi|ganti\s+jadi)\s+", "", extracted_val, flags=re.IGNORECASE).strip()
                    # Clean trailing filler words
                    extracted_val = re.sub(r"\b(?:ya|nih|dong|lho|deh|kan|loh|banget|sih|aja|saja)\b", "", extracted_val, flags=re.IGNORECASE).strip()
                    if len(extracted_val) >= 2 and extracted_val.lower() not in INVALID_FACT_VALUES and not extracted_val.lower().startswith(("apa", "siapa", "kenapa", "bagaimana", "tahu", "ubah", "ganti")):
                        eff_name = target_name or "Tamu"

                        # ── Zero-Shot Dynamic AI Entity Classification & Companion Commentary ──
                        # AI automatically identifies if extracted_val is an animal, food, drink, vehicle,
                        # movie, game, sport, hobby, etc. without ANY static hardcoded dictionaries!
                        ai_class = classify_preference_entity_ai(extracted_val, eff_name)

                        actual_key = ai_class.get("canonical_key") or key
                        actual_cat = "preference"
                        actual_title = ai_class.get("category_label") or title_lbl
                        comment = ai_class.get("companion_comment", "").strip()
                        question = ai_class.get("confirmation_question", "").strip()

                        if comment and question:
                            reply_text = f"{comment} {question}"
                        elif comment:
                            reply_text = f"{comment} Bahwa {extracted_val.title()} adalah {actual_title} kamu, Anara boleh mengingatnya, {eff_name}?"
                        else:
                            reply_text = f"Wah, tentang {extracted_val.title()} itu menarik banget! Bahwa {actual_title} kamu adalah '{extracted_val.title()}', Anara boleh mengingatnya, {eff_name}?"

                        self.set_pending_proposal(eff_name, {
                            "type": "fact",
                            "key": actual_key,
                            "value": extracted_val.title(),
                            "category": actual_cat,
                            "title": actual_title,
                            "is_multi_entity": ai_class.get("is_multi_entity", False),
                            "entities": ai_class.get("entities", [extracted_val.title()])
                        })
                        return {
                            "type": "direct_answer",
                            "reply_text": reply_text
                        }

        # ── 4. Proposing New To-Do / Task (Asks Confirmation First!) ──
        todo_add_match = re.search(r"\b(?:catat|tambahkan|tulis|ingatkan)\s+(?:tugas|to\s*do|catatan|jadwal)\s+(?:baru\s+)?(?:bahwa\s+|untuk\s+|=|:)?\s*([a-zA-Z0-9\s\-.,]+)", norm)
        if todo_add_match:
            task_title = todo_add_match.group(1).strip().strip(".,!?\"'").title()
            if len(task_title) >= 3 and not task_title.lower().startswith(("apa", "lihat", "daftar", "list")):
                eff_name = target_name or "Tamu"
                self.set_pending_proposal(eff_name, {
                    "type": "todo",
                    "title": task_title,
                    "category": "todo"
                })
                return {
                    "type": "direct_answer",
                    "reply_text": f"Baik, kamu ingin aku menambahkan tugas '{task_title}' ke daftar to-do database? Mau aku simpan sekarang?"
                }

        # 3. Read / List All Memories
        read_memory_patterns = [
            r"\b(?:apa\s+saja\s+(?:yang\s+)?kamu\s+ingat|sebutkan\s+ingatan(?:ku)?|lihat\s+(?:daftar\s+)?ingatan(?:ku)?|apa\s+(?:saja\s+)?yang\s+kamu\s+tahu\s+tentang\s+aku|cek\s+ingatan(?:ku)?)\b",
            r"\b(?:daftar\s+ingatan(?:ku)?|list\s+ingatan(?:ku)?|ingatan\s+database)\b"
        ]
        for pat in read_memory_patterns:
            if re.search(pat, clean_norm) or re.search(pat, norm):
                return {"type": "read_memories"}

        # 4. 3D Animation Capability & Inquiries (Strict Multi-Word Questions: 2-3+ Words)
        read_anim_patterns = [
            r"\b(?:apa\s+saja\s+animasi(?:mu| kamu)?|sebutkan\s+animasi(?:mu| kamu)?|list\s+animasi|daftar\s+animasi|bisa\s+gerak\s+apa\s+aja)\b",
            r"\b(?:apakah\s+kamu|kamu\s+bisa|bisa\s+nggak\s+kamu|bisa\s+gak\s+kamu)\s+(?:nari|menari|joget|dance|dansa)\b",
            r"\b(?:bisa\s+(?:nari|menari|joget|dance|dansa)\s+(?:nggak|tidak|gak|bisa))\b",
        ]
        for pat in read_anim_patterns:
            if re.search(pat, clean_norm) or re.search(pat, norm):
                if re.search(r"\b(?:nari|menari|joget|dance|dansa)\b", norm):
                    return {
                        "type": "dance_capability",
                        "reply_text": "Bisa dong! Aku punya animasi tarian Rumba 3D di databaseku. Kalau kamu mau lihat aku menari, cukup katakan: 'Anara, ayo nari dong!' dan aku akan langsung bergoyang untukmu!"
                    }
                return {"type": "read_animations"}

        # 5. Read To-Dos / Notes
        read_todo_patterns = [
            r"\b(?:apa\s+saja\s+to\s*do|lihat\s+catatan|lihat\s+to\s*do|daftar\s+tugas|list\s+to\s*do|apa\s+jadwal(?:ku)?|apa\s+tugas(?:ku)?)\b"
        ]
        for pat in read_todo_patterns:
            if re.search(pat, clean_norm) or re.search(pat, norm):
                return {"type": "read_todos"}

        # 6. Delete Memory Key
        delete_patterns = [
            (r"\b(?:lupakan|hapus\s+memori)\s+lagu\s+(?:favorit|kesukaan)(?:ku)?", "lagu_favorit"),
            (r"\b(?:lupakan|hapus\s+memori)\s+band\s+(?:favorit|kesukaan)(?:ku)?", "band_favorit"),
            (r"\b(?:lupakan|hapus\s+memori)\s+motor(?:ku)?", "motor_dimiliki"),
            (r"\b(?:lupakan|hapus\s+memori)\s+mobil(?:ku)?", "mobil_favorit"),
            (r"\b(?:lupakan|hapus\s+memori)\s+warna\s+(?:favorit|kesukaan)(?:ku)?", "warna_favorit"),
            (r"\b(?:lupakan|hapus\s+memori)\s+makanan\s+(?:favorit|kesukaan)(?:ku)?", "makanan_favorit"),
            (r"\b(?:lupakan|hapus\s+memori)\s+hobi(?:ku)?", "hobi"),
            (r"\b(?:lupakan|hapus\s+memori)\s+film\s+(?:favorit|kesukaan)(?:ku)?", "film_favorit"),
            (r"\b(?:lupakan|hapus\s+memori)\s+game\s+(?:favorit|kesukaan)(?:ku)?", "game_favorit"),
        ]
        for pat, key in delete_patterns:
            if re.search(pat, clean_norm) or re.search(pat, norm):
                return {"type": "delete_memory", "key": key}

        return None

    # ── Dynamic Context & Knowledge Injection ────────────────────────────────

    def get_system_prompt_context(self, speaker_name: Optional[str] = None) -> str:
        """
        Builds a contextual multi-user memory block from SQLite database.
        Injects catalog of registered user profiles and the active speaker's memories.
        """
        time_info = get_current_indonesian_time_str()

        # 1. Animations & 3D Capabilities from DB
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT name, category, description FROM animations ORDER BY id ASC")
                anim_rows = cursor.fetchall()
                anim_list = [f"- {r['name'].title()} ({r['category']}): {r['description']}" for r in anim_rows]
                anim_str = "\n".join(anim_list)
        except Exception:
            anim_str = "- Dance: Tarian Rumba 3D\n- Laughing: Tertawa ceria\n- Angry: Ekspresi marah\n- Crying: Ekspresi sedih"

        # 2. All Registered Profiles in Database
        try:
            all_speakers = self.get_all_speakers()
            speaker_profiles_summary = []
            for s in all_speakers:
                s_name = s["name"]
                s_mems = self.get_memories_for_speaker(s_name)
                if s_mems:
                    fact_preview = "; ".join([f"{m['key'].replace('_', ' ')}: {m['value']}" for m in s_mems[:3]])
                    speaker_profiles_summary.append(f"- {s_name} ({s['sample_count']} sampel suara): {fact_preview}")
                else:
                    speaker_profiles_summary.append(f"- {s_name} ({s['sample_count']} sampel suara terdaftar)")
            profiles_str = "\n".join(speaker_profiles_summary) if speaker_profiles_summary else "- Belum ada profil terdaftar."
        except Exception:
            profiles_str = "- Belum ada profil terdaftar."

        target_speaker = canonicalize_speaker_name(speaker_name) if speaker_name else None

        if target_speaker:
            todos = self.get_notes_and_todos(speaker_name=target_speaker)
            active_todos = [t for t in todos if not t["is_completed"]][:5]
            todo_str = "\n".join([f"- [{t['category'].upper()}] {t['title']}" + (f": {t['content']}" if t['content'] else "") for t in active_todos]) if active_todos else "- Tidak ada tugas pending."

            projs = self.get_projects_for_speaker(speaker_name=target_speaker)
            active_projs = [p for p in projs if p.get("status") == "active"][:3]
            proj_str = "\n".join([f"- Proyek '{p['name']}'" + (f" ({p['tech_stack']})" if p.get('tech_stack') else "") + (f": Target '{p['goal']}'" if p.get('goal') else "") for p in active_projs]) if active_projs else "- Belum ada proyek aktif tersimpan."

            m_rows = self.get_memories_for_speaker(target_speaker)
            mem_str = "\n".join([f"- {r['key'].replace('_', ' ').title()} ({r['category']}): {r['value']}" for r in m_rows]) if m_rows else f"- Nama: {target_speaker} (Profil aktif terdaftar di database SQLite Anara)."

            # Tone & Persona Guidance
            tone_guidance = "Gunakan bahasa Indonesia yang ramah, hangat, natural, dan ringkas (1-2 kalimat)."

            active_section = (
                f"[PROFIL PENGGUNA AKTIF / TERIDENTIFIKASI]: {target_speaker}\n\n"
                f"[FAKTA DAN INGATAN PRIBADI {target_speaker.upper()} DI DATABASE]:\n"
                f"{mem_str}\n\n"
                f"[PROYEK AKTIF & RIWAYAT KERJA {target_speaker.upper()}]:\n"
                f"{proj_str}\n\n"
                f"[CATATAN & TO-DO {target_speaker.upper()} DI DATABASE]:\n"
                f"{todo_str}\n\n"
                f"[PANDUAN INTERAKSI UTAMA]:\n"
                f"1. Kamu sedang berbicara dengan {target_speaker}! Pengguna ini sudah terdaftar dan sidik suaranya terkalibrasi di database.\n"
                f"2. Jika pengguna menyapa atau bertanya seperti 'kamu kenal aku?', 'siapa namaku?', 'tahu suaraku gak?', jawab dengan yakin, hangat, dan ramah bahwa kamu mengenalnya sebagai {target_speaker}.\n"
                f"3. Jika pengguna menyapa pagi ('pagi anara', 'selamat pagi'), kamu bisa secara proaktif menyapa namanya dan memberi ringkasan singkat to-do atau proyeknya jika ada.\n"
                f"4. Sapa dan panggil namanya ({target_speaker}) dalam percakapan. {tone_guidance}"
            )
        else:
            active_section = (
                f"[STATUS IDENTITAS PENGGUNA]: Tamu / Belum Terdaftar (Suara tidak cocok dengan profil terdaftar)\n\n"
                f"[PANDUAN INTERAKSI TAMU & PRIVASI]:\n"
                f"1. Pengguna saat ini adalah TAMU (suaranya berbeda/belum terdaftar di database).\n"
                f"2. JANGAN mengasumsikan pengguna ini adalah profil terdaftar lain dan JANGAN membocorkan data pribadi profil lain.\n"
                f"3. Perlakukan pengguna dengan ramah dan sopan sebagai Tamu. Jika dia bertanya siapa dia, katakan bahwa suaranya belum terdaftar dan persilakan mengenalkan diri (contoh: 'Halo Anara, kenalkan aku [Nama]') jika ingin mendaftarkan profil baru."
            )

        return (
            f"\n[WAKTU & KALENDER REAL-TIME]:\n"
            f"Hari & Tanggal: {time_info['date_full']}\n"
            f"Waktu Sekarang: {time_info['time_str']}\n\n"
            f"[DAFTAR PROFIL TERDAFTAR DI DATABASE SQLITE ANARA]:\n"
            f"{profiles_str}\n\n"
            f"{active_section}\n\n"
            f"[KAPABILITAS PROYEKSI VISUAL ANARA]:\n"
            f"- Kamu adalah Anara, asisten AI visual 3D multi-pengguna cerdas dengan visual holographic di layar.\n"
            f"- Kamu BISA menampilkan: Foto Asli Web, Widget Cuaca Real-time, Terminal Kode Sci-Fi, Telemetri Status Sistem Anara, Skematik Pengetahuan, dan Checklist To-Do di layar.\n\n"
            f"[ATURAN KOMUNIKASI & ANTI-ROLEPLAY]:\n"
            f"1. Jawablah pesan pengguna secara langsung, relevan, alami, dan ringkas (1-2 kalimat).\n"
            f"2. DILARANG KERAS menuliskan teks roleplay dalam tanda bintang seperti *tersenyum*, *menari*, atau *dansa*.\n"
            f"3. DILARANG mengajak menari atau membicarakan tarian kecuali pengguna secara eksplisit meminta ('Anara, ayo nari!').\n"
        )

    def format_memories_summary(self, speaker_name: str) -> str:
        """Returns a polite, complete voice/text list of all memories for a speaker (READ)."""
        mems = self.get_memories_for_speaker(speaker_name)
        if not mems:
            # Fallback to all memories if specific speaker filter returned none
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT key, value FROM memories ORDER BY id DESC LIMIT 10")
                mems = [dict(r) for r in cursor.fetchall()]

        if not mems:
            return f"Halo {speaker_name}, saat ini aku belum memiliki catatan preferensi khusus tentang kamu di database. Kamu bisa menyuruhku mencatat apa saja!"

        items = []
        for m in mems:
            k = m["key"].replace("_", " ").title()
            v = m["value"]
            items.append(f"{k}: {v}")

        formatted = ", ".join(items)
        return f"Tentu {speaker_name}! Ini daftar ingatan yang tersimpan di database: {formatted}."

    def format_todos_summary(self, speaker_name: str) -> str:
        """Returns a summary of pending to-do tasks."""
        todos = self.get_notes_and_todos(speaker_name=speaker_name)
        active = [t for t in todos if not t["is_completed"]]
        if not active:
            return f"Tidak ada tugas to-do yang pending untuk {speaker_name}. Semuanya sudah selesai!"
        
        t_list = [f"{i+1}. {t['title']}" for i, t in enumerate(active[:5])]
        return f"Berikut catatan tugas aktif {speaker_name}: " + ", ".join(t_list)

    def format_animations_summary(self) -> str:
        """Returns a polite list of available 3D animations and expressions from database."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name, description FROM animations ORDER BY id ASC")
            rows = cursor.fetchall()
            if not rows:
                return "Aku memiliki animasi dasar berbicara, melambai, dan ekspresi emosi."

            names = [r["name"].capitalize() for r in rows]
            names_str = ", ".join(names)
            return f"Aku memiliki {len(rows)} animasi dinamis di database: {names_str}. Coba suruh aku menari, marah, tertawa, atau melambai!"

    def get_all_animations(self) -> List[Dict[str, Any]]:
        """Returns all registered 3D animation/behavior profiles from the database."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, name, category, emotion, gesture, intensity, duration_sec, keywords_json, description
                FROM animations
                ORDER BY
                    CASE WHEN category = 'dance' THEN 1
                         WHEN category = 'emotion' THEN 2
                         WHEN category = 'gesture' THEN 3
                         ELSE 4 END, id ASC
            """)
            rows = cursor.fetchall()
            result = []
            for r in rows:
                try:
                    kws = json.loads(r["keywords_json"]) if r["keywords_json"] else []
                except Exception:
                    kws = []
                result.append({
                    "id": r["id"],
                    "name": r["name"],
                    "category": r["category"],
                    "emotion": r["emotion"],
                    "gesture": r["gesture"],
                    "intensity": float(r["intensity"]),
                    "duration_sec": float(r["duration_sec"]),
                    "keywords": [k.strip() for k in kws if str(k).strip()],
                    "description": r["description"] or ""
                })
            return result

    def upsert_animation(
        self,
        name: str,
        category: str,
        emotion: str,
        gesture: str,
        keywords: List[str],
        intensity: float = 0.8,
        duration_sec: float = 3.0,
        description: str = ""
    ) -> bool:
        """Creates or updates an animation profile in the animations table."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO animations (name, category, emotion, gesture, intensity, duration_sec, keywords_json, description, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(name) DO UPDATE SET
                        category = excluded.category,
                        emotion = excluded.emotion,
                        gesture = excluded.gesture,
                        intensity = excluded.intensity,
                        duration_sec = excluded.duration_sec,
                        keywords_json = excluded.keywords_json,
                        description = excluded.description,
                        updated_at = CURRENT_TIMESTAMP
                """, (
                    name.strip().lower(),
                    category.strip().lower(),
                    emotion.strip().lower(),
                    gesture.strip().lower(),
                    intensity,
                    duration_sec,
                    json.dumps([k.strip().lower() for k in keywords if str(k).strip()]),
                    description
                ))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"[AnaraMemory] Error upserting animation '{name}': {e}")
            return False

    def delete_animation(self, name: str) -> bool:
        """Deletes an animation profile by name."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM animations WHERE name = ?", (name.strip().lower(),))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"[AnaraMemory] Error deleting animation '{name}': {e}")
            return False

    def get_brain_stats(self) -> Dict[str, Any]:
        """Returns comprehensive stats of the Anara Cognitive Brain."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM speakers")
            speaker_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM memories")
            memory_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM notes_and_todos")
            note_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM notes_and_todos WHERE is_completed = 1")
            completed_todo_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM conversations")
            conversation_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM animations")
            animation_count = cursor.fetchone()[0]

            return {
                "speakers_count": speaker_count,
                "memories_count": memory_count,
                "notes_count": note_count,
                "completed_todos": completed_todo_count,
                "conversations_count": conversation_count,
                "animations_count": animation_count,
                "db_size_bytes": os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0,
                "db_path": self.db_path
            }


# Global singleton instance
memory_engine = AnaraMemoryEngine()
