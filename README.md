# Project Anara - 3D AI Assistant & Autonomous Intelligence Agent

> **Anara** adalah perpaduan mutakhir antara asisten AI visual 3D berkemampuan suara dua arah real-time, agen koding otonom terstruktur berbasis **OpenCode** (Plan Mode & Build Mode), arsitektur pemanggilan alat otonom **Hermes Agent**, serta konsol manajemen agen modular berbingkai *liquid-glass*.

---

## Daftar Isi

- [Ringkasan Proyek](#ringkasan-proyek)
- [Filosofi & Identitas Inti](#filosofi--identitas-inti)
- [Fitur Utama](#fitur-utama)
  - [1. OpenCode Autonomous Coding & Exploration Engine](#1-opencode-autonomous-coding--exploration-engine)
  - [2. Hermes ReAct Multi-Tools & Subagent Delegation](#2-hermes-react-multi-tools--subagent-delegation)
  - [3. Multi-Provider AI Backbone & OAuth PKCE](#3-multi-provider-ai-backbone--oauth-pkce)
  - [4. Real-Time Fluid Streaming & Visual Rhythm](#4-real-time-fluid-streaming--visual-rhythm)
  - [5. Anara Brain Console (Framed Dual-Pane Window)](#5-anara-brain-console-framed-dual-pane-window)
  - [6. Humanoid 3D Avatar & Real-Time Voice Engine](#6-humanoid-3d-avatar--real-time-voice-engine)
  - [7. Integrasi Komunikasi & Ekosistem Eksternal](#7-integrasi-komunikasi--ekosistem-eksternal)
- [Tech Stack](#tech-stack)
- [Struktur Direktori Proyek](#struktur-direktori-proyek)
- [Panduan Instalasi & Menjalankan](#panduan-instalasi--menjalankan)
  - [Metode 1: Peluncur Otomatis Satu Klik (Windows)](#metode-1-peluncur-otomatis-satu-klik-windows)
  - [Metode 2: Setup Manual (Backend & Frontend)](#metode-2-setup-manual-backend--frontend)
- [Konfigurasi Variabel Lingkungan](#konfigurasi-variabel-lingkungan)
- [Panduan Penggunaan Alur Kerja](#panduan-penggunaan-alur-kerja)

---

## Ringkasan Proyek

Project Anara menghadirkan pengalaman AI masa depan yang menggabungkan keramahan asisten virtual dengan kekuatan eksekusi *software engineer* otonom. Berbeda dari AI percakapan web biasa yang terisolasi dari sistem komputer, Anara memiliki akses langsung ke ruang kerja (*workspace*) lokal untuk menelusuri kode, menyunting berkas secara presisi, menjalankan perintah terminal, mengompilasi proyek, dan membuat artefak digital siap unduh.

Sistem ini beroperasi dalam dua mode interaksi utama:
1. **Voice Mode (Percakapan Suara Real-Time)**: Interaksi audio dua arah berlatensi sangat rendah menggunakan Google Gemini Live API, dilengkapi Speech Emotion Recognition (SER), deteksi interupsi instan, serta biometrik pengenalan suara pembicara.
2. **Chat & Build Mode (Autonomous Coding Workbench)**: Ruang kerja koding dual-pane lengkap dengan editor berkas *in-place*, terminal terintegrasi, penelusur pohon proyek, status perubahan Git (`+X -Y`), dan widget checklist progres tugas otonom.

---

## Filosofi & Identitas Inti

Perilaku dan kepribadian Anara dipandu oleh pedoman inti dalam berkas `soul.md` yang dimuat secara dinamis via `soul_loader.py` dengan dukungan *hot-reloading* instan:

- **Anti-Robotik & Zero-Hardcode**: 100% jawaban dan penalaran diproduksi langsung oleh model AI tanpa kalimat hafalan atau template kalengan.
- **Protokol OpenCode (Plan Mode & Build Mode)**:
  - **Plan Mode (Eksplorasi & Perancangan Aman)**: Mengunci izin modifikasi berkas (*read-only guard*). Agen menggunakan alat eksplorasi (`glob_find_files`, `grep_search_code`, `read_local_file`) untuk meneliti masalah dan menyajikan proposal rencana kerja (`plan_card`) terstruktur kepada pengguna.
  - **Build Mode (Konstruksi & Verifikasi Otonom)**: Membuka izin modifikasi sistem. Agen menyunting berkas secara *in-place* (`edit_file`), membuat dokumen/arsip (`create_zip_archive`), serta menjalankan verifikasi kompilasi terminal secara mandiri.
- **Adaptive Language Mirroring**: Model secara otomatis mencocokkan bahasa yang digunakan pengguna (fasih berbahasa Inggris saat disapa dalam Bahasa Inggris, santun dan bersahabat dalam Bahasa Indonesia, serta mendukung *code-switching*).
- **Universal Time-Awareness**: Deteksi otomatis zona waktu lokal komputer dan browser (WIB, WITA, WIT, JST, UTC, EST, dll.) tanpa aturan kaku *if-else* di backend.

---

## Fitur Utama

### 1. OpenCode Autonomous Coding & Exploration Engine
- **`edit_file` (Selective In-Place Replacement)**: Menyunting berkas dengan mencocokkan `old_string` $\rightarrow$ `new_string` secara presisi. Menghemat 90% token, mencegah pemotongan kode secara tidak sengaja, dan menghasilkan kartu *visual diff* baris per baris (`+X -Y`).
- **`read_local_file` (Windowed Line Pagination)**: Membaca berkas dokumen atau kode dengan parameter `offset` (nomor baris awal) dan `limit` (jumlah baris), dilengkapi penomoran baris `<line>: <content>`.
- **`glob_find_files` (Fast Pattern Matcher)**: Mencari lokasi berkas dengan pola nama (`**/*.tsx`, `src/**/*.py`) dengan mengabaikan direktori sampah (`node_modules`, `.git`, `.next`, `venv`).
- **`grep_search_code` (Fast Regex Search)**: Pencarian regex di seluruh isi proyek kode untuk menemukan definisi fungsi, variabel, atau teks dalam hitungan milidetik.
- **Self-Verification Loop Protocol**: Agen dibekali protokol untuk membaca kode sebelum mengedit dan menjalankan verifikasi kompilasi/linting (`execute_cli_command`) secara mandiri setelah melakukan perubahan.

### 2. Hermes ReAct Multi-Tools & Subagent Delegation
- **Deep ReAct Chaining**: Batas langkah penalaran otonom berturut-turut ditingkatkan hingga **25 langkah mandiri** per giliran obrolan.
- **Context Sliding Window & Pruning**: Observasi keluaran tool yang panjang (seperti log kompilasi ratusan baris) diringkas secara otomatis setelah beberapa langkah agar batas konteks token tetap terjaga.
- **`delegate_subagent`**: Kemampuan mendelegasikan tugas berat (riset web mendalam, audit multi-berkas) ke pekerja latar belakang asinkron (`anara_subagent.py`) tanpa memblokir thread percakapan utama.
- **`create_zip_archive`**: Mengompresi seluruh proyek ke dalam arsip ZIP siap unduh dengan *Hermes Context Recovery* (mengekstrak blok kode percakapan jika berkas belum ada di disk).
- **`generate_file_artifact`**: Pembuatan berkas dokumen resmi (.docx via `python-docx`, .pdf via `reportlab`, dan semua format teks/kode).
- **Extended Terminal Timeout**: Batas waktu eksekusi perintah terminal dinaikkan menjadi **120 detik** untuk mendukung instalasi dependensi (`npm install`), pengujian unit (`pytest`), dan kompilasi build.

### 3. Multi-Provider AI Backbone & OAuth PKCE
- **Google Gemini SDK & Live API**: Dukungan penuh untuk Gemini 3.1 Flash Live Preview (audio dua arah) dan Gemini 2.5/3.0/3.8 Flash Multimodal.
- **OpenAI Codex OAuth PKCE Flow**: Integrasi resmi via listener lokal `http://localhost:1455/auth/callback` dengan enkripsi tantangan PKCE S256. Login langsung menggunakan akun OpenAI tanpa perlu API key berbayar.
- **Anthropic Claude Direct API**: Streaming langsung untuk Claude 3.7 Sonnet, Claude 3.5 Sonnet, dan Claude 3.5 Haiku.
- **Custom Gateway / 9Router Proxy**: Kompatibel dengan semua proxy lokal atau penyedia pihak ketiga yang mengikuti standar OpenAI `/chat/completions`.
- **Actual Token Usage Capture**: Menangkap penggunaan token riil dari metadata penyedia (`usage_metadata`, `stream_options.include_usage`) yang disajikan pada bilah metrik Hermes di footer pesan.
- **Multi-Account Failover Pool**: Mendukung penyimpanan banyak akun/kunci API per provider dengan rotasi dan pendinginan otomatis (*cooldown*) saat terkena kuota batas HTTP 429/503.

### 4. Real-Time Fluid Streaming & Visual Rhythm
- **Micro-Cadence Word Streaming**: Backend memecah letupan chunk besar dari upstream proxy menjadi aliran kata-per-kata yang stabil (~12ms per kata).
- **Fluid Token Consumer (60fps)**: Komponen frontend mengalirkan teks menggunakan `requestAnimationFrame` dengan mekanisme akselerasi adaptif (*catch-up*) agar tidak membuat pengguna menunggu.
- **Monospace Active Cursor (`▌`)**: Kursor blok bercahaya cyan berkedip di ujung teks selama proses streaming berlangsung.
- **Sticky Plan Checklist Widget**: Menempel di atas bar input chat, menampilkan progres langkah rencana (`X dari Y tugas selesai ˅`), beradaptasi dengan tinggi dinamis menggunakan `ResizeObserver`, dan otomatis menghilang (*auto-dismiss*) saat seluruh tugas tuntas.
- **Dual-Font System**: Memadukan font **Inter** untuk teks narasi dan antarmuka dengan font **JetBrains Mono** untuk kode, diff git, angka metrik token, dan baris terminal.

### 5. Anara Brain Console (Framed Dual-Pane Window)
- **Framed Inset Window**: Jendela mengambang berbingkai elegan (`inset-3 sm:inset-5 lg:inset-6`) dengan latar belakang *dark obsidian liquid-glass* yang tidak memotong suasana 3D avatar di sekelilingnya.
- **Sidebar Navigasi Vertikal Ramping**: Menu dikelompokkan ke dalam 4 pilar fungsional:
  - *Agen Otonom*: Editor `soul.md`, Katalog 23 Alat Otonom, Skills Hermes.
  - *Memori & Konteks*: Ingatan & Fakta SQLite, Catatan & Tugas, Proyek Aktif, Profil Pengguna.
  - *AI & Jaringan*: Providers & Model Pool, Koneksi Media.
  - *Audit & Sistem*: Log Percakapan, Animasi 3D Avatar.
- **Live Editor `soul.md`**: Editor teks terintegrasi langsung di konsol dengan tombol penyimpanan instan (*hot-reload*) dan preset persona (*Fullstack Engineer*, *Software Architect*, *Minimalist CLI*).
- **Tools & MCP Inspector**: Peninjau 23 alat otonom lengkap dengan skema parameter JSON dan penanda izin mode (*Read-Only Plan Mode vs Build Mode*).
- **Subagent Mission Monitor**: Pemantau tugas latar belakang dengan Task ID, status badge, progress bar dinamis, dan log langkah pengerjaan.

### 6. Humanoid 3D Avatar & Real-Time Voice Engine
- Model humanoid fotorealistik Avaturn berbasis Three.js dan React Three Fiber.
- 72 blendshapes standar ARKit dan Oculus Visemes dengan interpolasi gerakan bibir (*lip-sync*) halus berbasis fonem audio.
- Kinematika prosedural: pernapasan dinamis, kedipan mata alami, pelacakan lirikan mata (*gaze tracking*), gestur tangan, serta postur santun adat Jawa Ngapurancang.
- Dukungan gerakan tarian dinamis (Rumba dance) yang terintegrasi dengan synthesizer audio Web Audio API.

### 7. Integrasi Komunikasi & Ekosistem Eksternal
- **WhatsApp Web Bridge**: Koneksi jembatan Node.js Baileys dengan pemindaian kode QR langsung pada kartu HUD Anara.
- **Telegram Bot API**: Pengiriman dan pemantauan pesan masuk via bot Telegram.
- **Google Workspace**: Pemeriksaan pesan masuk Gmail dan sinkronisasi agenda Google Calendar.

---

## Tech Stack

### Frontend
- **Framework**: Next.js 16.3.2 (App Router)
- **Bahasa**: TypeScript
- **Library UI & Styling**: React 19, Tailwind CSS v4
- **Tipografi**: Inter (Sans-serif) & JetBrains Mono (Monospace)
- **Grafis 3D**: Three.js, `@react-three/fiber`, `@react-three/drei`
- **Audio & Stream**: Web Audio API, AudioWorklet, Native WebSocket

### Backend
- **Framework**: FastAPI 0.115.0, Uvicorn
- **Bahasa**: Python 3.10+ (Diuji hingga Python 3.14)
- **AI SDK**: `google-genai 1.0.0`, HTTPX (Async SSE Streaming)
- **Komputasi & Format**: NumPy, Pydub, ReportLab (PDF), Python-Docx (Word), Zipfile
- **Basis Data**: SQLite3 persisten (`anara_brain.db`)

### WhatsApp Bridge
- **Runtime**: Node.js
- **Library**: `@whiskeysockets/baileys` (port 8001)

---

## Struktur Direktori Proyek

```
Project Anara/
├── START_ANARA.bat              # Peluncur otomatis seluruh sistem (Windows)
├── run.bat                      # Pintasan cepat peluncur
├── soul.md                      # Persona, filosofi agen, dan aturan koding
├── anara_brain.db               # Basis data SQLite persisten
│
├── backend/
│   ├── main.py                  # Server FastAPI, REST endpoints, Git API, & WebSocket handler
│   ├── ai_service.py            # Bridge Google Gemini Live API untuk suara audio dua arah
│   ├── anara_agent.py           # Mesin otonom ruang kerja proyek dan manajemen sesi
│   ├── anara_subagent.py        # Mesin pekerja latar belakang asinkron (Sub-Agents)
│   ├── agent_tools.py           # 23 Implementasi tools otonom & deklarasi skema fungsi
│   ├── model_router.py          # Router multi-provider, ReAct loop (25 langkah), & context pruning
│   ├── memory_service.py        # Mesin basis data SQLite, biometrik suara, dan jam global
│   ├── soul_loader.py           # Modul pembaca dinamis, editor mentah, & hot-reload soul.md
│   ├── model_capabilities.py    # Registri kapabilitas model AI (suara, teks, visi)
│   ├── emotion_engine.py        # Klasifikasi emosi dan pemicu gestur avatar
│   ├── audio_utils.py           # Analisis gelombang audio PCM16 & Speech Emotion Recognition
│   ├── key_manager.py           # Pengelola pool kunci API, rotasi akun, dan auto-cooldown
│   ├── briefing_service.py      # Penyusun laporan Daily Briefing harian
│   ├── media_service.py         # Integrasi pencarian audio/video YouTube
│   ├── image_service.py         # Proyeksi kartu visual dan foto web asli
│   ├── proactive_service.py     # Layanan pengingat proaktif dan tenggat waktu tugas
│   ├── telegram_service.py      # Integrasi klien Telegram Bot API
│   ├── google_service.py        # Integrasi Gmail dan Google Calendar
│   ├── whatsapp_service.py      # Pengontrol jembatan Baileys WhatsApp
│   ├── whatsapp_bridge/         # Sub-proyek Node.js jembatan WhatsApp
│   │   ├── bridge.js
│   │   └── package.json
│   ├── requirements.txt         # Dependensi pustaka Python
│   └── .env.example             # Contoh variabel lingkungan backend
│
└── frontend/
    ├── app/
    │   ├── page.tsx             # Orkestrator antarmuka utama dan timeline percakapan
    │   ├── layout.tsx           # Layout root Next.js dengan inisialisasi font & zero-flash script
    │   └── globals.css          # Desain tema Tailwind CSS v4, liquid-glass, dan token styling
    ├── components/
    │   ├── AnaraBrain.tsx       # Konsol manajemen Framed Dual-Pane (Soul, Tools, Providers)
    │   ├── VoiceControls.tsx    # Antarmuka input prompt, dock mengambang, dan checklist sticky
    │   ├── AnaraHUD.tsx         # Render kartu visual multimodal, Plan Card, dan ZIP viewer
    │   ├── AnaraCodeIDE.tsx     # In-browser code viewer dengan diff baris per baris
    │   ├── WorkbenchTerminal.tsx# Terminal interaktif lokal shell (/api/agent/terminal/execute)
    │   ├── ChatSessionSidebar.tsx # Sidebar riwayat chat, Buka Folder native, dan Git Changes
    │   ├── AgentToolCard.tsx    # Kartu eksekusi aksi tool (Sunting, Baca, Shell, Glob, Grep)
    │   ├── AgentMarkdown.tsx    # Fluid stream markdown renderer dengan active cursor (▌)
    │   ├── Avatar3D.tsx         # Engine avatar 3D humanoid, morph targets, dan gestur
    │   ├── Scene.tsx            # Setup Three.js scene, kamera potret, dan pencahayaan studio
    │   ├── AnaraMediaPlayer.tsx # Pemutar media YouTube terintegrasi
    │   └── LoadingScreen.tsx    # Layar transisi inisialisasi
    ├── hooks/
    │   ├── useWebSocket.ts      # Pengelola pesan WebSocket, event tool, dan streaming token
    │   ├── useMicrophone.ts     # Perekaman mikrofon AudioWorklet (16kHz PCM16)
    │   ├── useAudioPlayer.ts    # Pemutaran streaming audio jawaban asisten
    │   └── useLipSync.ts        # Kontroler sinkronisasi bibir berbasis fonem
    ├── lib/
    │   ├── visemeMap.ts         # Pemetaan fonem ke blendshapes ARKit/Oculus
    │   ├── sentimentAnalyzer.ts # Analisis sentimen ekspresi wajah avatar
    │   ├── danceMusic.ts        # Generator audio tarian Rumba via Web Audio API
    │   ├── danceDetector.ts     # Logika pemicu gerakan tarian
    │   └── alarmSound.ts        # Pembangkit nada alarm dan pengingat waktu
    └── package.json             # Konfigurasi dependensi frontend
```

---

## Panduan Instalasi & Menjalankan

### Prasyarat Sistem
- **Node.js**: Versi 18.0 atau lebih baru
- **Python**: Versi 3.10 atau lebih baru (disarankan menggunakan Python venv)
- **Koneksi Internet**: Untuk komunikasi model AI dan pencarian web

---

### Metode 1: Peluncur Otomatis Satu Klik (Windows)

1. Buka folder repositori di komputer Anda.
2. Klik ganda berkas **`START_ANARA.bat`** atau **`run.bat`**.
3. Skrip akan secara otomatis:
   - Meminta hak akses administrator (UAC elevation) jika diperlukan.
   - Memeriksa keabsahan dependensi Node.js dan virtual environment Python.
   - Memastikan ketersediaan port 8000 (Backend FastAPI) dan port 3000 (Frontend Next.js).
   - Menjalankan backend dan frontend secara bersamaan.
4. Akses aplikasi melalui browser pada alamat **`http://localhost:3000`**.

---

### Metode 2: Setup Manual (Backend & Frontend)

#### 1. Setup Backend Python
Buka terminal pada direktori `backend`:
```bash
cd backend

# Buat dan aktifkan virtual environment
python -m venv venv
venv\Scripts\activate            # Windows
# atau: source venv/bin/activate # Linux / macOS

# Instal seluruh dependensi Python
pip install -r requirements.txt

# Jalankan server backend FastAPI
python main.py
```
Backend akan aktif di `http://localhost:8000` (Dokumentasi Swagger API interaktif tersedia di `http://localhost:8000/docs`).

#### 2. Setup Frontend Next.js
Buka terminal kedua pada direktori `frontend`:
```bash
cd frontend

# Instal dependensi Node.js
npm install

# Jalankan server pengembangan Next.js
npm run dev
```
Frontend akan aktif di `http://localhost:3000`.

---

## Konfigurasi Variabel Lingkungan

### Backend (`backend/.env`)

| Variabel | Default / Format | Keterangan |
| :--- | :--- | :--- |
| `GEMINI_API_KEY` | Opsional | Kunci API Google AI Studio (bisa dikonfigurasi via konsol UI) |
| `GEMINI_MODEL` | `gemini-3.1-flash-live-preview` | Model suara default untuk mode audio |
| `SYSTEM_PROMPT` | String | Persona dasar asisten (rujukan utama ada di `soul.md`) |
| `CORS_ORIGINS` | `http://localhost:3000` | Alamat frontend yang diizinkan |
| `TELEGRAM_BOT_TOKEN` | Opsional | Token Bot Telegram untuk integrasi chat |
| `TELEGRAM_CHAT_ID` | Opsional | Chat ID target Telegram |
| `GOOGLE_USER_EMAIL` | Opsional | Alamat Gmail untuk Google Workspace |
| `WA_BRIDGE_PORT` | `8001` | Port server bridge WhatsApp |

> **Catatan Pengelolaan Kunci API**: Anda **tidak perlu** menyunting berkas `.env` secara manual untuk menambahkan kunci API Google, OpenAI Codex, atau endpoint Custom (9Router). Seluruh kunci API, login OAuth, penambahan endpoint, dan pool akun dapat dikelola secara langsung dan aman melalui konsol **Anara Brain** (tab *Providers*).

### Frontend (`frontend/.env.local`)

| Variabel | Default | Keterangan |
| :--- | :--- | :--- |
| `NEXT_PUBLIC_WS_URL` | `ws://localhost:8000/ws` | Alamat koneksi WebSocket backend |
| `NEXT_PUBLIC_BACKEND_URL` | `http://localhost:8000` | Alamat HTTP REST API backend |

---

## Panduan Penggunaan Alur Kerja

### 1. Navigasi Antarmuka Utama
- **Sidebar Kiri**: Menyediakan tab **`💬 Sesi`** untuk menelusuri riwayat percakapan lama dan tab **`</> Editor`** untuk membuka folder proyek di komputer (via Windows native picker), menjelajahi berkas kode, melihat perubahan Git (`+X -Y`), dan membuka terminal interaktif.
- **Header Atas**: Menampilkan tombol buka **Anara Brain Console** untuk meninjau memori, aturan agen (`soul.md`), katalog alat, dan manajemen provider AI.
- **Bilah Bawah (Dock)**: Tempat mengetik prompt, memilih mode kerja (*Plan Mode* vs *Build Mode*), memilih model AI aktif, menyisipkan lampiran berkas, atau mengaktifkan mode suara mikrofon.

### 2. Alur Kerja Plan Mode ke Build Mode (OpenCode Protocol)
1. **Perancangan di Plan Mode**:
   - Ketik permintaan proyek (misal: *"Buatkan halaman web login modern dengan Tailwind CSS"*).
   - Anara akan membaca ruang kerja dan menyajikan kartu rencana visual (**Plan Card**) berisi judul, tech stack, dan tahapan eksekusi tanpa memodifikasi berkas.
2. **Persetujuan & Eksekusi di Build Mode**:
   - Klik tombol **`⚡ Setujui & Eksekusi di Build Mode`** pada kartu visual.
   - Status kartu bertransisi menjadi `APPROVED — BUILD MODE`.
   - Widget sticky checklist progres tugas muncul di atas bar prompt (`0 dari 3 tugas selesai ˅`).
   - Anara mengeksekusi pembuatan berkas secara otonom (`write_local_file` atau `edit_file`), memverifikasi kode, dan mengemas seluruh proyek ke dalam arsip ZIP (`create_zip_archive`).
3. **Penyelesaian Otomatis**:
   - Berkas kode yang baru dibuat otomatis terbuka ke tab Editor sebelah kiri.
   - Seluruh tugas pada checklist otomatis tercentang (`3 dari 3 tugas selesai`), dan kartu sticky otomatis menghilang (*auto-dismiss*) setelah pekerjaan selesai.
   - Kartu unduhan interaktif tampil di layar HUD sehingga proyek ZIP dapat langsung diunduh dan dijalankan.

### 3. Mengatur Jiwa & Aturan Agen (`soul.md`)
1. Buka **Anara Brain Console** dari tombol di sidebar atau header.
2. Pilih pilar **Persona & Jiwa** $\rightarrow$ **Soul & Aturan Agen**.
3. Sunting filosofi, aturan respons, atau disiplin koding secara langsung pada editor Markdown.
4. Anda juga dapat memilih preset instan seperti **Fullstack Engineer**, **Software Architect**, atau **Minimalist CLI**.
5. Klik tombol **`Simpan & Terapkan Jiwa`**—perubahan langsung dimuat ulang ke memori model tanpa restart server.

---

## Lisensi & Kontribusi

Project Anara dikembangkan secara terbuka untuk eksperimen kecerdasan buatan otonom, sistem multimodal, dan antarmuka masa depan. Kontribusi perbaikan kode, penambahan tools baru, dan optimalisasi performa sangat dipersilakan melalui *pull request*.
