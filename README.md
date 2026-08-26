# 🤖 3D AI Voice Assistant

Aplikasi AI asisten interaktif dengan avatar 3D, komunikasi suara real-time menggunakan Gemini Live API, animasi idle, dan lip-sync otomatis.

## Tech Stack

- **Frontend**: Next.js 15 + TypeScript + Tailwind CSS + React Three Fiber
- **Backend**: Python FastAPI + WebSocket
- **AI**: Google Gemini Live API (voice-to-voice)
- **3D Engine**: Three.js + @react-three/drei

## Prerequisites

- Node.js v18+
- Python 3.10+
- Google Gemini API Key (dengan akses Gemini Live API)

## Quick Start

### 1. Setup Backend

```bash
cd backend

# Copy dan isi API key
copy .env.example .env
# Edit .env → isi GEMINI_API_KEY

# Aktifkan virtual environment
venv\Scripts\activate   # Windows
# atau: source venv/bin/activate  # Mac/Linux

# Install dependencies (sudah dilakukan otomatis)
pip install -r requirements.txt

# Jalankan server
python main.py
```

Backend akan berjalan di: `http://localhost:8000`

### 2. Setup Frontend

```bash
cd frontend

# Install dependencies (sudah dilakukan otomatis)
npm install

# Jalankan dev server
npm run dev
```

Frontend akan berjalan di: `http://localhost:3000`

### 3. Gunakan Aplikasi

1. Buka browser → `http://localhost:3000`
2. Tunggu avatar 3D loading
3. Klik tombol 🎤 (mikrofon) untuk mulai bicara
4. AI akan menjawab dengan suara + avatar bergerak
5. Klik ⏹ untuk menyela AI saat berbicara

## Fitur

- ✅ Real-time voice-to-voice conversation
- ✅ 3D avatar dengan idle animation (breathing, blinking, head sway)
- ✅ Lip-sync berbasis transcript
- ✅ Interrupt (potong pembicaraan AI)
- ✅ Transcript display real-time
- ✅ Auto-reconnect WebSocket
- ✅ Low latency audio streaming

## Struktur Proyek

```
Project Anara/
├── frontend/                 # Next.js app
│   ├── app/
│   │   ├── page.tsx          # Main page
│   │   ├── layout.tsx        # Root layout
│   │   └── globals.css       # Styles
│   ├── components/
│   │   ├── Avatar3D.tsx      # 3D avatar + animation
│   │   ├── Scene.tsx         # Three.js scene
│   │   ├── VoiceControls.tsx # UI controls
│   │   └── LoadingScreen.tsx # Loading UI
│   ├── hooks/
│   │   ├── useWebSocket.ts   # WS connection
│   │   ├── useMicrophone.ts  # Mic capture (AudioWorklet)
│   │   ├── useLipSync.ts     # Lip-sync controller
│   │   └── useAudioPlayer.ts # Audio playback
│   ├── lib/
│   │   └── visemeMap.ts      # Viseme → blendshape mapping
│   └── public/
│       └── avatar.glb        # 3D avatar model
│
└── backend/
    ├── main.py               # FastAPI + WebSocket server
    ├── ai_service.py         # Gemini Live API bridge
    ├── audio_utils.py        # Audio processing utilities
    ├── requirements.txt
    └── .env                  # API keys (jangan di-commit!)
```

## Menggunakan Avatar RPM Sendiri

1. Buka [readyplayer.me](https://readyplayer.me)
2. Create/customize avatar
3. Export dengan opsi:
   - Format: GLB
   - Morph Targets: ARKit + Oculus Visemes
4. Simpan sebagai `frontend/public/avatar.glb`

## Environment Variables

### Backend (`backend/.env`)
| Variable | Nilai | Keterangan |
|----------|-------|------------|
| `GEMINI_API_KEY` | `AIza...` | Google AI API Key |
| `GEMINI_MODEL` | `gemini-2.0-flash-live-001` | Model untuk Live API |
| `SYSTEM_PROMPT` | string | Persona AI asisten |
| `CORS_ORIGINS` | `http://localhost:3000` | Frontend URL |

### Frontend (`frontend/.env.local`)
| Variable | Nilai | Keterangan |
|----------|-------|------------|
| `NEXT_PUBLIC_WS_URL` | `ws://localhost:8000/ws` | Backend WebSocket URL |
