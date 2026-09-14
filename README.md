# Project Anara — General-Purpose AI Agent
### Setara Hermes — Multi-Channel, Autonomous, dengan Plan/Build Gate

> **Anara** adalah AI Agent serbaguna (*general-purpose*) yang menggabungkan kemampuan **Asisten Percakapan Suara 3D** (*Voice Companion*), **Workstation Koding Mandiri** (*Anara Code Studio*), dan **Kendali Jarak Jauh Multi-Channel** (Telegram, WhatsApp, CLI Runner) — dengan penegakan gerbang keamanan **Plan/Build Gate 4-Tingkat** untuk melindungi sistem host dari aksi berisiko tinggi.

---

## 📑 Daftar Isi

- [Arsitektur & Filosofi Sistem](#arsitektur--filosofi-sistem)
- [Tiga Wajah Interaksi Anara](#tiga-wajah-interaksi-anara)
- [Pilar Keamanan: Unified Tool Risk Taxonomy & Plan Gate](#pilar-keamanan-unified-tool-risk-taxonomy--plan-gate)
- [Sistem Memori 4-File & Privacy Filter](#sistem-memori-4-file--privacy-filter)
- [Skill Library v2 (agentskills.io Format)](#skill-library-v2-agentskillsio-format)
- [Autonomous Task Scheduler & Trust-Level Policy](#autonomous-task-scheduler--trust-level-policy)
- [Multi-Channel: Telegram, WhatsApp & Interactive CLI](#multi-channel-telegram-whatsapp--interactive-cli)
- [Struktur Direktori Proyek](#struktur-direktori-proyek)
- [Panduan Instalasi & Menjalankan](#panduan-instalasi--menjalankan)
- [Suite Pengujian Regresi Otomatis](#suite-pengujian-regresi-otomatis)

---

## 🏛️ Arsitektur & Filosofi Sistem

Sesuai spesifikasi `prd-general-agent.md` dan `rancangan-general-agent.md`, Anara menutup celah keamanan agen general-purpose seperti Hermes:
- **Hermes Agent**: Menggabungkan kemampuan luas (code execution, shell, messaging, autonomous run), namun memanggil tool berisiko tinggi dengan level keamanan yang sama longgarnya dengan obrolan biasa.
- **Anara General Agent**: Memiliki cakupan kemampuan setara Hermes, tetapi menerapkan prinsip inti:  
  **`Level keamanan mengikuti risiko alat (tool) yang dipanggil, bukan mengikuti jenis antarmuka atau channel-nya.`**

Satu otak agen mengendalikan seluruh channel, menegakkan permission gate yang sama persis baik dipicu dari obrolan suara santai, chat WhatsApp di HP, terminal CLI, maupun scheduler otomatis.

---

## 🎭 Tiga Wajah Interaksi Anara

| Antarmuka / Channel | Peran Utama | Mode Sesi | Kapan Digunakan? |
| :--- | :--- | :--- | :--- |
| **Anara 3D Companion (`/`)** | *The Face & Voice* | `conversational` | Obrolan suara santai *hands-free*, musik, briefing harian, dan respons emosional avatar 3D. Bersih tanpa tombol Plan/Build manual. |
| **Anara Code Studio (`/code`)** | *The Deep Workstation* | `explicit_plan_build` | Pekerjaan koding intensif pada repositori lokal: Explorer pohon berkas, CodeMirror 6 in-place editor, terminal terintegrasi, dan tombol toggle eksplisit `Plan` & `Build`. |
| **Remote Control (Telegram, WA, CLI)** | *The Remote Control* | `conversational` | Akses cepat saat bepergian (HP) atau langsung dari terminal tanpa membuka browser, dengan notifikasi persetujuan rencana (*approval gate*). |

---

## 🛡️ Pilar Keamanan: Unified Tool Risk Taxonomy & Plan Gate

Seluruh alat (*tools*) agen terdaftar di dalam taksonomi 4 tingkat risiko:

```
Tingkat 1: read_only  ──► Bebas dieksekusi di mode & channel apa pun
                          (read_local_file, grep_search_code, glob_find_files, web_search, fetch_webpage)

Tingkat 2: action     ──► Efek luar terisolasi & reversible (Plan kondisional jika signifikan)
                          (whatsapp_send_message, telegram_send_message, custom_webhook, manage_memory_and_todos)

Tingkat 3: mutating   ──► Mengubah berkas/sistem host — WAJIB PLAN MODE DULU
                          (edit_file, write_local_file, execute_cli_command, generate_file_artifact, create_zip_archive)

Tingkat 4: ask        ──► Aksi destruktif/ireversibel — SELALU KONFIRMASI GRANULAR
                          (system_control / shutdown / format / drop database)
```

### Logika Keputusan Unified Plan Detector (`needs_plan`):
1. **Di Mode `explicit_plan_build` (Anara Code):** Semua tool selain `read_only` wajib menyusun rencana terlebih dahulu.
2. **Di Mode `conversational` (Anara AI, Telegram, WhatsApp, CLI):**
   - Pertanyaan biasa & riset dijawab instan (*zero-friction*).
   - Perintah terminal/modifikasi berkas **secara otomatis mengaktifkan Plan Mode**: Anara menyusun rencana kerja terstruktur dan meminta konfirmasi sebelum eksekusi.
   - Perintah persetujuan verbal (*"setujui rencana"*, *"eksekusi"*, *"sikat"*, *"gas"*) otomatis beralih ke Build Mode.

---

## 🧠 Sistem Memori 4-File & Privacy Filter

Anara menyimpan memori lintas sesi ke dalam 4 berkas Markdown persisten:

1. **`SOUL.md`** *(Identitas Global)*: Pedoman kepribadian, etika koding, dan prinsip anti-slop (*hot-reloading* instan ke sistem memori).
2. **`USER.md`** *(Profil Pengguna)*: Preferensi bahasa, gaya komunikasi, dan peran pengguna (dibatasi ~1.500 karakter).
3. **`MEMORY.md`** *(Fakta Jangka Panjang)*: Catatan keputusan teknis, arsitektur, dan fakta penting yang dipelajari dengan timestamp otomatis (dibatasi ~2.200 karakter).
4. **`AGENTS.md`** *(Aturan Proyek Lokal)*: Petunjuk arsitektur dan konvensi koding lokal di folder proyek aktif (hanya aktif saat workspace terhubung).

### 🔒 Privacy Filter Otomatis
Sebelum teks dicatat ke `USER.md` atau `MEMORY.md`, filter regex otomatis menyensor data sensitif:
- OpenAI & Anthropic API Key (`sk-...`) $\rightarrow$ `[REDACTED_API_KEY]`
- Google AIza Key (`AIza...`) $\rightarrow$ `[REDACTED_API_KEY]`
- Password & Token Auth $\rightarrow$ `[REDACTED_SECRET]` / `[REDACTED_TOKEN]`

---

## 📦 Skill Library v2 (agentskills.io Format)

Keahlian prosedural yang dipelajari Anara disimpan dalam format direktori standar **agentskills.io**:

```
backend/skills/
├── scaffold-react-vite-tailwind-enterprise/
│   └── SKILL.md
├── deploy-docker-swarm-staging/
│   └── SKILL.md
└── automasi-penulisan-berkas-kode/
    └── SKILL.md
```

### Format Berkas `SKILL.md`:
- **YAML Frontmatter**: Menyimpan metadata (`name`, `category`, `description`, `trigger_keywords`, `status`, `required_environment_variables`).
- **Body Markdown**: Bagian *Overview*, *When to Use*, dan *Steps* prosedur konkret.
- **Alur Persetujuan (FR-16)**: Skill yang diekstrak agen secara otonom berstatus `pending`. Pengguna dapat mereview dan menyetujuinya di Anara Brain Console sebelum aktif ke sistem prompt.
- **Progressive Disclosure (FR-17)**: Prompt hanya memuat indeks ringkas keahlian; isi prosedur lengkap baru dimuat jika instruksi pengguna cocok dengan kata kunci skill.

---

## ⏱️ Autonomous Task Scheduler & Trust-Level Policy

Anara dilengkapi *background worker* persisten berbasis SQLite (`autonomous_tasks`) untuk mengeksekusi tugas terjadwal (*interval / cron / event*):

### Matriks Kebijakan Trust-Level:
- **`supervised` (Default)**: Tugas otonom menyusun rencana di latar belakang, lalu **pause** dan mengirim notifikasi persetujuan ke Telegram dengan tombol `[✅ Setujui Rencana]`.
- **`semi_autonomous`**: Aksi ringan (`action`) otomatis disetujui; aksi *mutating* (terminal/berkas) dan *ask* tetap menunggu konfirmasi.
- **`full_autonomous`**: Aksi *mutating* otomatis disetujui. **Aksi kategori `ask` (destruktif) TETAP 100% WAJIB konfirmasi manusia (NFR-1: Zero exceptions)**.

### 🔄 Git Auto-Commit & Rollback per Langkah Build (FR-18)
- Setiap kali Anara menyunting atau menulis berkas di workspace, perubahan otomatis di-commit ke Git lokal:
  `anara(build): edit server.js (+12 -3 lines)`
- Tersedia endpoint `POST /api/agent/git/rollback` untuk membatalkan langkah build jika terjadi kesalahan.

---

## 📱 Multi-Channel: Telegram, WhatsApp & Interactive CLI

Semua channel dinormalisasi ke format internal seragam:  
`ChannelRequest(text, channel, channel_id, user_id, sender_name, trigger_type)`

### 1. Interactive CLI Runner
Jalankan agen langsung dari terminal tanpa browser:
```powershell
# Jalankan REPL interaktif:
.\anara-cli.bat
# atau:
python cli.py

# Eksekusi satu perintah langsung:
python cli.py "Tolong buatkan skrip backup database"
```
Perintah praktis di CLI:
- `/model` — Menampilkan daftar model AI terkonfigurasi & ganti model aktif (`/model <nomor_atau_id>`)
- `/status` — Memeriksa status sistem, model AI aktif, dan metrik memori
- `/mode` — Beralih mode sesi (`conversational` ↔ `explicit_plan_build`)
- `/memory` — Memeriksa snapshot `USER.md` dan `MEMORY.md`
- `/skills` — Melihat daftar keahlian agen aktif di `agentskills.io`
- `/exit` — Keluar dari terminal REPL

### 2. Inbound Telegram Bot
- **Ganti Model Instan (`/model` / `/models`)**:
  - Mengetik `/model` memunculkan **Inline Keyboard Buttons (tombol klik)** berisi model AI yang aktif dan terdaftar.
  - Cukup ketuk salah satu tombol di layar ponsel untuk langsung beralih model AI seketika!
  - Bisa juga langsung via teks: `/model gemini-3.5-flash-lite`.
- **Daftar Perintah Slash Telegram**:
  - `/start` & `/help` — Menampilkan panduan dan daftar perintah bot
  - `/model` — Pemilih model AI interaktif dengan tombol inline
  - `/status` — Memeriksa status bot, model aktif, dan statistik memori Anara
  - `/memory` — Membaca ringkasan profil pengguna (`USER.md`) & catatan fakta (`MEMORY.md`)
  - `/skills` — Menampilkan keahlian agen aktif berbasis folder
  - `/clear` / `/new` — Membersihkan konteks dan memulai sesi percakapan baru
- **Persetujuan Rencana Interaktif (Plan Gate)**:
  - Perintah berisiko tinggi (*terminal shell, edit file, modifikasi sistem*) otomatis memicu Plan Gate dan mengirimkan kartu rencana kerja lengkap dengan **Inline Keyboard Buttons**:
    `[✅ Setujui Rencana]` dan `[❌ Batalkan]`.
  - Mengetuk tombol approval langsung mengeksekusi Build Mode di komputer lokal Anda dan mengirimkan laporan progres secara langsung.

### 3. Inbound WhatsApp Web (Baileys Bridge)
- Jembatan Node.js Baileys meneruskan pesan masuk ke endpoint webhook FastAPI.
- Mendukung filter *whitelist* nomor pribadi (`whatsapp_allowed_numbers`).
- Responsif terhadap percakapan biasa dan menahan perintah mutating dengan Plan Gate.

---

## 📁 Struktur Direktori Proyek

```
Project Anara/
├── START_ANARA.bat              # Peluncur otomatis seluruh sistem (Admin elevation)
├── anara-cli.bat                # Pintasan peluncur Interactive CLI Runner
├── cli.py                       # Implementasi CLI REPL & single-prompt runner
├── test_general_agent.py        # Suite pengujian regresi otomatis (7 domain arsitektur)
├── soul.md                      # Sumber identitas inti Anara
├── prd-general-agent.md         # Dokumen PRD General AI Agent
├── rancangan-general-agent.md   # Dokumen spesifikasi teknis arsitektur
│
├── backend/
│   ├── main.py                  # Entrypoint FastAPI, lifecycle startup & background daemons
│   ├── cognition/               # Modul kognisi, emosi, briefing, dan 4-file memory
│   │   ├── SOUL.md              # Identitas agen (hot-reloaded)
│   │   ├── USER.md              # Profil pengguna persisten
│   │   └── MEMORY.md            # Catatan fakta persisten
│   ├── core/                    # Inti arsitektur general agent
│   │   ├── channel_adapter.py   # Gateway normalisasi multi-channel
│   │   ├── plan_detector.py     # Unified Plan Detector (needs_plan)
│   │   ├── autonomous_engine.py # Penjadwal tugas otonom & trust-level policy
│   │   ├── skill_library.py     # Manajemen Skill Library v2 (agentskills.io)
│   │   ├── skill_extractor.py   # Ekstraksi keahlian baru otonom pasca-build
│   │   ├── prompt_assembler.py  # 6-Slot prompt assembler dinamis
│   │   ├── agent.py             # Mesin workspace & git commit per build step
│   │   └── subagent.py          # Pekerja sub-agen asinkron latar belakang
│   ├── integrations/            # Integrasi Telegram, WhatsApp, Google Workspace
│   ├── memory/                  # Database SQLite, RAG semantik, & file_memory manager
│   ├── providers/               # Multi-provider model caller (Gemini, Claude, 9Router, OpenAI)
│   ├── routers/                 # Modular APIRouters (brain, workspace, session, integrations)
│   ├── skills/                  # Direktori berkas folder-based SKILL.md
│   ├── tools/                   # Katalog 4-tier risk tools & permission gate
│   ├── websocket/               # WebSocket real-time voice pipeline & agent runner
│   └── whatsapp_bridge/         # Jembatan Node.js Baileys WhatsApp (port 8001)
│
└── frontend/
    ├── app/
    │   ├── page.tsx             # Halaman 3D Companion Voice & Chat
    │   ├── code/page.tsx        # Halaman Anara Code Studio Workstation
    │   ├── globals.css          # Desain sistem Tailwind CSS v4 & liquid-glass
    │   └── layout.tsx           # Root layout dengan synchronous zero-layout-shift script
    ├── components/
    │   ├── avatar/              # 3D Avatar Three.js, pencahayaan studio & scene
    │   ├── brain/               # Anara Brain Console (Skills v2, Memory 4-File, Tugas Otonom)
    │   ├── chat/                # Timeline chat fluid, Wizard card, Tool action card
    │   ├── dock/                # Universal Bottom Dock & Pemilih Model Dinamis (Live vs All)
    │   ├── ide/                 # CodeMirror 6 editor & terminal PowerShell terintegrasi
    │   ├── sidebar/             # Sidebar riwayat sesi & Workspace file tree
    │   └── workbench/           # Orkestrator dual-pane Anara Workbench
    └── package.json
```

---

## 🚀 Panduan Instalasi & Menjalankan

### Prasyarat
- **Node.js**: Versi 18+ atau 20+
- **Python**: Versi 3.10+ (disarankan menggunakan virtualenv di `backend/venv`)
- **Git**: Terpasang di sistem PATH

### Cara Menjalankan Aplikasi:

#### 1. Melalui Peluncur Otomatis Satu Klik (Windows):
Klik ganda berkas **`START_ANARA.bat`** di folder root proyek.
- Skrip otomatis menginstal dependensi bila belum ada.
- Menjalankan backend FastAPI di `http://localhost:8000` dan frontend Next.js di `http://localhost:3000`.
- Membuka browser:
  - **Companion 3D**: `http://localhost:3000`
  - **Code Studio**: `http://localhost:3000/code`

#### 2. Menjalankan Terminal CLI Runner:
Buka PowerShell atau Command Prompt baru:
```powershell
.\anara-cli.bat
```

#### 3. Menghubungkan Telegram Bot:
1. Buat bot di `@BotFather` di Telegram dan dapatkan bot token.
2. Buka Anara Brain Console $\rightarrow$ tab **Integrasi** $\rightarrow$ masukkan token dan Chat ID.
3. Bot Telegram akan langsung aktif mendengarkan pesan dan memproses persetujuan rencana.

#### 4. Menghubungkan WhatsApp Web:
1. Buka Anara Brain Console $\rightarrow$ tab **Integrasi** $\rightarrow$ WhatsApp.
2. Pindai kode QR yang muncul menggunakan aplikasi WhatsApp di ponsel Anda.

---

## 🧪 Suite Pengujian Regresi Otomatis

Untuk memastikan seluruh 7 pilar arsitektur berfungsi 100% tanpa regresi, jalankan perintah:

```powershell
python test_general_agent.py
```

### Hasil Pengujian yang Divalidasi (48/48 Assertions Passed):
```
--- 1. Testing Unified Tool Risk Taxonomy (4 Tiers) ---
  [PASS] Tiers match exactly 4 categories (Tiers: ['action', 'ask', 'mutating', 'read_only'])
  [PASS] Shell command is mutating
  [PASS] File edit is mutating
  [PASS] Permission Gate strictly blocks mutating tools in Plan Mode

--- 2. Testing Unified Plan Detector & Approval Parser ---
  [PASS] Conversational Mode: Casual chat does NOT require Plan Mode
  [PASS] Conversational Mode: Terminal shell command triggers Plan Mode
  [PASS] Approval: 'setujui rencana' / 'sikat rencana' / 'gas eksekusi'

--- 3. Testing 4-File Memory & Privacy Filter ---
  [PASS] Privacy Filter censors OpenAI sk- key & password
  [PASS] SOUL.md, USER.md, MEMORY.md are readable with character caps
  [PASS] Memory trigger detects 'ingat bahwa...'

--- 4. Testing Skill Library v2 (agentskills.io Format) ---
  [PASS] Skill file saved to disk with YAML frontmatter
  [PASS] Approve skill transitions status to active
  [PASS] Progressive disclosure includes matched skill details

--- 5. Testing Multi-Channel Gateway (Telegram, WhatsApp, CLI) ---
  [PASS] Telegram & WhatsApp safe turns respond directly
  [PASS] Mutating requests trigger Plan Gate automatically

--- 6. Testing Autonomous Engine & Trust-Level Policy ---
  [PASS] Trust Policy: 'supervised', 'semi_autonomous', 'full_autonomous' enforced
  [PASS] Trust Policy (NFR-1): 'ask' tier is BLOCKED across ALL trust levels

--- 7. Testing Git Auto-Commit & Rollback per Build Step (FR-18) ---
  [PASS] Git Auto-Commit created SHA on file creation & edit
  [PASS] Git Rollback reverted commit cleanly
```

---

*Project Anara — Dikembangkan secara berdedikasi sebagai asisten AI cerdas multi-channel dan mitra koding otonom.*
