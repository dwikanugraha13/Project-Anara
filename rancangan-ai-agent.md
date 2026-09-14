# Rancangan Arsitektur AI Agent (Plan Mode + Build Mode)
Setara Claude Code, OpenCode, dan Hermes Agent

---

## 1. Gambaran Umum Sistem

```
┌─────────────────────────────────────────────────────────────┐
│                        USER INTERFACE                       │
│              (CLI / Web / IDE Extension)                    │
└───────────────────────────┬───────────────────────────────┘
                             │
┌───────────────────────────▼───────────────────────────────┐
│                      SESSION MANAGER                        │
│  - session state (mode, history, project context)            │
│  - mode toggle (plan ⇄ build)                                │
│  - context window management (compaction/summarization)      │
└───────────────────────────┬───────────────────────────────┘
                             │
┌───────────────────────────▼───────────────────────────────┐
│                    PROMPT ASSEMBLER                          │
│  Slot #1: Identity (SOUL.md-equivalent)                       │
│  Slot #2: Mode instructions (plan/build)                      │
│  Slot #3: Tool guidance                                       │
│  Slot #4: Memory snapshot                                     │
│  Slot #5: Skills manifest                                     │
│  Slot #6: Project context (AGENTS.md-equivalent)              │
└───────────────────────────┬───────────────────────────────┘
                             │
┌───────────────────────────▼───────────────────────────────┐
│                   LLM PROVIDER / ROUTER                       │
│   (Anthropic API / OpenAI / lokal via Ollama)                │
│   - model berbeda per mode (murah utk plan, kuat utk build)   │
│   - streaming response token-by-token                        │
└───────────────────────────┬───────────────────────────────┘
                             │  tool_use blocks
┌───────────────────────────▼───────────────────────────────┐
│                    PERMISSION GATE                            │
│  cek: mode saat ini × jenis tool (read-only/mutating/ask)      │
│  → allow / deny / minta konfirmasi user                       │
└───────────────────────────┬───────────────────────────────┘
                             │
┌───────────────────────────▼───────────────────────────────┐
│                     TOOL EXECUTOR                             │
│  read_file, write_file (diff-based), run_shell (sandboxed),   │
│  search_code, web_search, subagent_delegate…                  │
│  - retry/backoff untuk kegagalan                              │
└───────────────────────────┬───────────────────────────────┘
                             │
┌───────────────────────────▼───────────────────────────────┐
│               MEMORY & SKILL LAYER (persisten)                │
│  MEMORY.md / state.db / skills/ (auto-capture proses berhasil)│
└───────────────────────────┬───────────────────────────────┘
                             │
┌───────────────────────────▼───────────────────────────────┐
│                 OBSERVABILITY / TRACING                       │
│  log tool call, token usage, biaya per sesi, error rate        │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Komponen Inti

### 2.1 Session Manager
Bertanggung jawab atas satu unit percakapan/tugas. Menyimpan:

```json
{
  "session_id": "uuid",
  "mode": "plan",
  "current_plan": null,
  "history": [],
  "project_root": "/path/to/project",
  "approved_at": null,
  "token_usage": { "input": 0, "output": 0 }
}
```

Mode **tidak** disimpan sebagai instruksi di prompt saja — harus jadi field yang bisa dicek secara programatis sebelum tool dieksekusi.

**Context window management**: histori percakapan yang panjang harus di-compact/summarize otomatis saat mendekati limit token model, supaya sesi panjang tidak error atau kehilangan konteks penting. Strategi umum: ringkas N pesan terlama jadi satu ringkasan, pertahankan pesan terbaru secara verbatim.

### 2.2 Prompt Assembler
Rakit system prompt dari beberapa slot terurut, mirip Hermes:

| Slot | Isi | Sumber |
|---|---|---|
| 1 | Identitas & gaya agent | `SOUL.md` / config statis |
| 2 | Instruksi mode aktif | template plan.md / build.md |
| 3 | Cara pakai tools yang tersedia | tool registry |
| 4 | Ringkasan memory relevan | memory store |
| 5 | Skill yang relevan dengan tugas | skills manifest |
| 6 | Aturan/konteks project | `AGENTS.md` di root project |

Prinsip: identitas & gaya terpisah dari fakta/aturan. Jangan campur "siapa agent ini" dengan "aturan project X" dalam satu file.

### 2.3 Tool Registry
Setiap tool didefinisikan dengan metadata eksplisit, termasuk **klasifikasi risiko** (tiga tingkat, bukan biner):

```js
const TOOLS = {
  read_file:    { risk: "read_only" },
  search_code:  { risk: "read_only" },
  list_dir:     { risk: "read_only" },
  web_search:   { risk: "read_only" },

  write_file:   { risk: "mutating" },   // diterapkan sebagai diff, bukan overwrite
  edit_file:    { risk: "mutating" },

  run_shell:    { risk: "ask" },        // selalu minta konfirmasi granular
  delete_file:  { risk: "ask" },
  git_push_force: { risk: "ask" },

  subagent_delegate: { risk: "mutating" },
};
```

Klasifikasi ini adalah **sumber kebenaran tunggal** untuk Permission Gate.

### 2.4 Permission Gate
Bagian paling kritikal. Dieksekusi **sebelum** tool call benar-benar jalan, di level kode.

```js
function checkPermission(toolName, mode) {
  const risk = TOOLS[toolName].risk;

  if (mode === "plan" && risk !== "read_only") {
    return {
      allowed: false,
      message: "Blocked: plan mode is read-only. Propose this as a plan step instead."
    };
  }
  if (risk === "ask") {
    return { allowed: "pending_user_confirmation" };
  }
  return { allowed: true };
}
```

Kalau model tetap mencoba, tool executor mengembalikan pesan penolakan terstruktur ke model — bukan crash diam-diam.

**Konfirmasi granular**: bahkan di build mode, aksi destruktif (`rm -rf`, `git push --force`, `DROP TABLE`) tetap masuk kategori `ask` dan selalu minta konfirmasi eksplisit dari user, terlepas dari mode aktif.

### 2.5 Mode Definitions

**Plan Mode**
- Semua tool selain `read_only` diblokir di Permission Gate.
- System prompt mengarahkan ke: eksplorasi, analisis trade-off, output berupa daftar langkah terstruktur.
- Output plan disimpan sebagai objek terpisah:

```json
{
  "goal": "Tambah fitur checkout",
  "steps": [
    { "id": 1, "title": "Buat migration tabel orders", "status": "pending" },
    { "id": 2, "title": "Implement OrderController", "status": "pending" }
  ]
}
```

**Build Mode**
- Tool `mutating` diizinkan otomatis; tool `ask` tetap minta konfirmasi.
- Perubahan file diterapkan sebagai **diff**, bukan overwrite mentah — dan idealnya terintegrasi git, sehingga setiap perubahan bisa direview (`git diff`) dan di-rollback (`git revert`/checkout) kapan saja.
- System prompt mengarahkan ke eksekusi sesuai plan yang sudah disetujui, dengan plan disuntikkan sebagai referensi di context.

### 2.6 Alur Handoff (Plan → Build)

```
User buat request
     │
     ▼
[Plan Mode] Agent eksplorasi (read-only) → hasilkan plan terstruktur
     │
     ▼
User review plan → edit/reject/approve
     │
     ▼ (approve)
Session.mode = "build"
Session.current_plan = plan_yang_disetujui  (disuntikkan ke context)
     │
     ▼
[Build Mode] Agent eksekusi step demi step (diff per perubahan,
              commit git per step disarankan), update status tiap step
```

Approval bisa berupa kata kunci eksplisit ("approved"), tombol UI, atau command (`/approve`). Jangan biarkan transisi mode terjadi implisit dari asumsi model sendiri.

---

## 3. Eksekusi Aman: Sandboxing

`run_shell` dan tool sejenis **wajib** dijalankan dalam lingkungan terisolasi, bukan langsung di host:

- Container per sesi (Docker/Podman) dengan filesystem terbatas ke `project_root`.
- Batasi akses jaringan (allowlist domain, seperti proxy egress).
- Timeout keras per eksekusi command.
- Resource limit (CPU/memory) supaya satu command runaway tidak melumpuhkan sistem.

Tanpa sandboxing, satu command yang salah (baik dari bug maupun dari prompt injection) bisa merusak sistem host.

---

## 4. Reliabilitas

### 4.1 Error Handling & Retry
- Retry dengan backoff eksponensial untuk kegagalan transient (timeout jaringan, rate limit API, file lock).
- Bedakan error yang bisa di-retry otomatis vs error yang harus dilaporkan ke user/model untuk diputuskan.

### 4.2 Streaming Response
- Output token-by-token ke UI, bukan menunggu respons penuh — penting untuk UX di tugas yang lama.

### 4.3 Observability / Tracing
- Log terstruktur tiap tool call (nama, argumen, hasil, durasi).
- Tracking token usage & estimasi biaya per sesi.
- Metric error rate dan penolakan Permission Gate — berguna untuk audit dan debugging saat mode "bocor".

---

## 5. Memory & Skill Layer

Meniru pola Hermes:
- **Identity** (persisten, jarang berubah) — analog SOUL.md.
- **Episodic memory** (fakta per sesi/project) — analog MEMORY.md, disimpan di DB ringan (SQLite cukup).
- **Skills** (prosedur yang berhasil, di-capture otomatis setelah tugas selesai, dipakai lagi di sesi berikutnya).

---

## 6. Subagent / Delegasi

Untuk tugas besar, agent utama bisa mendelegasikan sub-tugas ke subagent dengan context terisolasi (mis. satu subagent khusus riset, satu khusus eksekusi test). Ini mencegah context window utama penuh oleh detail yang tidak relevan untuk keputusan level atas.

---

## 7. Testing & Evaluasi

Sebelum deploy perubahan ke prompt, permission logic, atau tool baru:
- Siapkan suite skenario uji (mis. "plan mode harus menolak semua write", "build mode harus minta konfirmasi untuk rm -rf").
- Jalankan eval otomatis tiap ada perubahan, bandingkan hasil sebelum/sesudah.
- Simpan skenario yang pernah gagal sebagai regression test.

---

## 8. Keamanan & Hardening (checklist)

1. Jangan pernah percaya prompt saja — semua pembatasan mode ditegakkan di layer eksekusi tool.
2. Scan file yang bisa diedit user (SOUL.md, AGENTS.md, dll.) untuk pola prompt-injection sebelum disuntikkan ke system prompt.
3. Fallback wajib — file identitas/config gagal dibaca → agent tetap jalan dengan identitas default.
4. Logging tiap penolakan tool call untuk audit.
5. Kebijakan `ask` untuk aksi destruktif, terlepas dari mode aktif.
6. Reload konfigurasi hanya di boundary sesi baru.
7. Sandboxing eksekusi shell/command (lihat bagian 3).
8. Diff + git integration untuk semua perubahan file (lihat 2.5).

---

## 9. Rekomendasi Tumpukan Teknologi (starter)

| Kebutuhan | Opsi |
|---|---|
| Bahasa | Node.js/TypeScript atau Python |
| LLM Provider | Anthropic API (tool use / function calling), dengan streaming |
| Penyimpanan sesi & memory | SQLite (ringan, portable) |
| CLI framework | Ink (Node) atau Typer/Rich (Python) |
| Format plan | JSON schema + renderer markdown checklist |
| Sandboxing | Docker/Podman per sesi |
| Version control changes | Git otomatis per step build |
| Observability | Structured logging (pino/loguru) + dashboard sederhana |

---

## 10. Roadmap Implementasi Bertahap

**Fase MVP (fungsional, aman secara dasar):**
1. Agent loop dasar (single mode, tool calling jalan)
2. Tool registry + klasifikasi risiko 3 tingkat
3. Session state dengan field `mode`
4. Permission Gate (plan mode read-only enforced di kode)
5. Prompt Assembler bertingkat (identity → mode → tools → memory → project)
6. Format plan terstruktur + alur approval
7. Toggle mode (shortcut/command) + handoff otomatis

**Fase Hardening (menuju level profesional):**
8. Sandboxing eksekusi shell
9. Diff-based file editing + integrasi git (rollback)
10. Context window compaction untuk sesi panjang
11. Error handling & retry/backoff
12. Streaming response
13. Observability/tracing (log, token usage, biaya)
14. Kebijakan `ask` granular untuk aksi destruktif

**Fase Lanjutan (skala & pembelajaran):**
15. Memory & skill capture persisten
16. Subagent/delegasi untuk tugas besar
17. Testing/eval framework untuk perubahan prompt & permission logic
18. Multi-provider/model routing (model murah utk plan, kuat utk build)

---

*Dokumen ini adalah kerangka rancangan lengkap — implementasi detail (skema tool, prompt template lengkap, dsb.) dikembangkan sesuai bahasa/platform yang dipilih.*

---

## 11. Rancangan Hybrid: Claude Code (Plan/Build) + Hermes (Memory/Skills/Autonomous)

Kombinasi ini masuk akal karena keduanya menyelesaikan masalah berbeda:
- **Claude Code** → kontrol keamanan eksekusi (kapan boleh mengubah sesuatu).
- **Hermes** → keberlanjutan lintas sesi (agent yang "ingat" dan "belajar").

Digabung, agent punya **rem** (plan/build) dan **ingatan jangka panjang** (memory/skills) sekaligus.

### 11.1 Perubahan pada Session Manager

Session sekarang punya dua sumbu independen: **mode** (plan/build) dan **run type** (interactive/autonomous):

```json
{
  "session_id": "uuid",
  "mode": "plan",
  "run_type": "interactive",
  "trust_level": "supervised",
  "current_plan": null,
  "history": [],
  "project_root": "/path/to/project"
}
```

- `run_type: "interactive"` → user hadir, approval plan dilakukan manual.
- `run_type: "autonomous"` → agent jalan tanpa user hadir (dipicu scheduler/event), approval plan mengikuti `trust_level`.
- `trust_level` → `"supervised"` (semua plan tetap perlu approval walau autonomous, ditunda sampai user cek), `"semi_autonomous"` (plan low-risk auto-approve, high-risk tetap menunggu), `"full_autonomous"` (semua auto-approve, hanya aksi kategori `ask` yang tetap berhenti).

Ini penting: **jangan biarkan mode autonomous otomatis berarti bypass permission gate**. Autonomous cuma mengubah *siapa* yang menyetujui plan (scheduler/aturan vs manusia), bukan menghapus lapisan keamanannya.

### 11.2 Skill Layer: Struktur Konkret (folder + SKILL.md, mengikuti agentskills.io)

Bukan satu file skill besar, tapi tiap skill punya **foldernya sendiri** dengan `SKILL.md` wajib di dalamnya — supaya skill bisa punya helper script, referensi, dan template pendukung tanpa membengkakkan file instruksi utamanya:

```
skills/                                  ← primary directory, source of truth
├── deploy-python-fly/
│   ├── SKILL.md                         ← wajib
│   ├── scripts/                         ← opsional: helper deterministik
│   ├── references/                      ← opsional: tabel panjang/dokumen vendor
│   └── templates/                       ← opsional: skeleton output
└── github-pr-workflow/
    └── SKILL.md
```

**Format SKILL.md:**

```markdown
---
name: deploy-python-fly
description: Use when deploying a Python app to Fly.io. Covers build, secrets, rollback.
version: 1.0.0
metadata:
  tags: [deployment, python, fly-io]
  related_skills: [github-pr-workflow]
required_environment_variables: [FLY_API_TOKEN]
---

# Deploy Python App to Fly.io

## Overview
Apa dan kenapa skill ini ada.

## When to Use
- Trigger yang jelas
- "Don't use for:" counter-trigger

## Steps
1. Langkah paling umum dulu, edge case ditaruh lebih ke bawah
```

**Prinsip desain kunci:**
- **Field wajib** di frontmatter cuma `name` dan `description` — field lain konvensi tapi disarankan konsisten antar skill.
- **Progressive disclosure**: agent awalnya cuma melihat index ringkas (nama + description tiap skill) di Prompt Assembler slot #5, bukan seluruh isi. Full `SKILL.md` baru dimuat ke context saat skill itu terpilih relevan dengan tugas — mencegah context window membengkak walau skill-nya banyak.
- **Batas ukuran**: description ≤1024 karakter, isi SKILL.md dibatasi (mis. ~100.000 karakter); kalau kepanjangan, pecah ke `references/*.md` dan dirujuk dari SKILL.md, bukan ditaruh semua di satu file.
- **Kredensial tidak pernah hardcoded** — dideklarasikan lewat `required_environment_variables` (API key/token) atau `required_credential_files` (OAuth token, service account JSON). Nilai rahasia tidak pernah masuk ke context model, hanya nama variabelnya.
- **Prinsip pembeda dari memory**: kalau isinya layak jadi dokumen referensi/prosedur, itu skill; kalau cuma catatan singkat, itu memory (MEMORY.md). Skill harus fokus sempit — "deploy Python app ke Fly.io" oke, "semua tentang DevOps" terlalu luas.
- **Auto-creation dengan approval**: setelah build mode sukses menuntaskan plan, Skill Extractor menawarkan skill baru. Skill yang baru dibuat/diedit agent disimpan dulu sebagai *pending* (bukan langsung aktif) — user review lewat diff sebelum approve, memakai jalur approval yang sama seperti aksi berisiko lain di Permission Gate.

**Alur lengkap (memperbarui diagram 11.2 sebelumnya):**

```
[Build Mode selesai] → evaluasi hasil (test pass? user konfirmasi sukses?)
        │
        ▼ (sukses)
   Skill Extractor: ringkas plan+langkah jadi draft SKILL.md
        │
        ▼
   Simpan sebagai pending (belum aktif) → user review diff
        │
        ▼ (approve)
   Pindah ke skills/<nama-skill>/SKILL.md → masuk index skill aktif
        │
        ▼
   Tersedia di Prompt Assembler slot #5 (index ringkas) untuk plan berikutnya
```

### 11.3 Persistent Memory: Struktur 4-File (konkret, meniru pola Hermes)

Daripada satu tabel/file memory generik, pisahkan jadi 4 file dengan pemilik dan scope berbeda — ini yang membuat memory tidak saling "mengotori" satu sama lain:

| File | Isi | Yang menulis | Scope | Batas ukuran |
|---|---|---|---|---|
| `SOUL.md` | Identitas agent: gaya bicara, prinsip kerja, apa yang dihindari | User (manual) | Global, ikut semua project | Bebas, tapi ringkas (masuk slot #1 tiap sesi) |
| `USER.md` | Profil user: nama, preferensi komunikasi, level skill, hal yang perlu dihindari | Agent (otomatis, trigger "remember that...") | Global | ~1.500 karakter (cap keras, cegah bengkak) |
| `MEMORY.md` | Fakta yang dipelajari agent: konvensi project, kebiasaan tool, pelajaran dari kesalahan | Agent (otomatis, trigger sama) | Global (lintas project) atau per-project, tergantung desain | ~2.200 karakter (cap keras) |
| `AGENTS.md` | Instruksi project: struktur, konvensi, arsitektur | User (manual) | Per-project, progressive discovery ke subfolder | Bebas |

**Prinsip desain kunci:**
- File yang **user kontrol** (SOUL.md, AGENTS.md) dan file yang **agent tulis sendiri** (USER.md, MEMORY.md) dipisah tegas — supaya identitas tidak ikut ter-drift saat agent menulis fakta baru.
- Semua file dimuat sebagai **frozen snapshot** saat sesi mulai (bukan live-reload) — perubahan baru berlaku di sesi berikutnya. Ini menjaga prompt tetap stabil/cache-able selama satu sesi berjalan.
- Cap ukuran keras di USER.md/MEMORY.md memaksa agent (atau proses pruning berkala) untuk terus meringkas, bukan menumpuk log mentah selamanya.
- Tiap entry yang agent tulis diberi timestamp comment (mis. `<!-- written 2026-09-13 -->`) — dipakai nanti untuk proses reflektif (memutuskan entry mana yang masih relevan) dan supaya user bisa audit "apa yang baru ditambahkan minggu ini".

**Trigger otomatis** — agent menulis ke USER.md/MEMORY.md saat mendeteksi frasa seperti "ingat bahwa...", "catat...", "next time kalau ketemu X, lakukan Y..." — bukan menyimpan semua yang dibahas.

**Pemakaian per mode:**

| Jenis memory | Dipakai di Plan Mode | Dipakai di Build Mode |
|---|---|---|
| SOUL.md | Menentukan gaya penyusunan plan | Menentukan gaya laporan progres |
| USER.md | Menyesuaikan level detail plan dengan skill user | Menyesuaikan gaya komunikasi progres |
| MEMORY.md | Preferensi project, keputusan masa lalu, kebiasaan tool | Konteks spesifik file yang sedang dikerjakan |
| AGENTS.md | Batasan/konvensi project saat menyusun langkah | Aturan konkret saat eksekusi (mis. style guide) |
| Skills | Pola solusi yang pernah berhasil | Detail teknis implementasi dari skill terkait |

Memory disuntikkan sebagai **ringkasan relevan**, bukan dump seluruh riwayat — pakai retrieval (keyword dulu, embedding kalau perlu skala) supaya context window tidak membengkak.

**Pemulihan dari korupsi:** karena file ini plaintext, backup rutin (mis. snapshot harian) memudahkan restore kalau ada section yang tidak sengaja terhapus/rusak.

### 11.4 Autonomous Loop (Scheduler + Trigger)

Agent Hermes-style bisa jalan tanpa dipicu chat langsung — lewat scheduler (cron-like) atau event (webhook, file change, pesan masuk):

```
Trigger (schedule/event)
     │
     ▼
Buat session baru, run_type = "autonomous"
     │
     ▼
[Plan Mode] otomatis: susun rencana untuk tugas terjadwal
     │
     ▼
Approval check (berdasar trust_level)
     │
     ├─ perlu approval → simpan plan, kirim notifikasi ke user, PAUSE
     │
     └─ auto-approve (low-risk & trust cukup) → lanjut
     │
     ▼
[Build Mode] eksekusi, log hasil
     │
     ▼
Skill Extractor (jika sukses) + laporan ringkas ke user
```

Prinsip kunci: **autonomous run tetap melewati Permission Gate yang sama** seperti sesi interactive. Yang berubah hanya siapa yang memegang tombol approve.

### 11.5 Diagram Gabungan (ringkas)

```
Trigger ─┬─ interaktif (user chat)
         └─ autonomous (scheduler/event)
              │
              ▼
     Session Manager (mode + run_type + trust_level)
              │
              ▼
     Prompt Assembler ← Identity + Memory + Skills + Project Context
              │
              ▼
        LLM (Plan Mode: read-only reasoning)
              │
              ▼
     Plan tersimpan → Approval Gate (manual / rule-based sesuai trust_level)
              │
              ▼
        LLM (Build Mode: eksekusi via tools, sandboxed)
              │
              ▼
   Permission Gate + Tool Executor + Observability
              │
              ▼
   Skill Extractor → simpan skill baru → tersedia utk plan berikutnya
              │
              ▼
     Episodic Memory update (state.db)
```

### 11.6 Penambahan Roadmap (Fase Hybrid)

Tambahkan setelah Fase Lanjutan di bagian 10:

19. Tambahkan field `run_type` dan `trust_level` di session state
20. Bangun Scheduler/Trigger layer (cron + event-based) terpisah dari UI chat
21. Implementasi Skill Extractor otomatis pasca build-mode sukses
22. Implementasi retrieval memory & skill (keyword dulu, embedding kalau perlu skala)
23. Buat kebijakan approval berbasis `trust_level` (bukan cuma biner auto/manual)
24. Notifikasi ke user untuk plan yang menunggu approval saat autonomous run


---

## 12. Multi-Provider Layer (Model Router)

Supaya agent tidak terkunci ke satu LLM provider, tambahkan lapisan abstraksi di antara Prompt Assembler dan pemanggilan model — mirip pola OpenRouter (satu interface, banyak backend).

### 12.1 Provider Registry

Setiap provider didaftarkan dengan tipe autentikasi dan endpoint-nya sendiri, bukan hardcoded:

```json
{
  "providers": {
    "anthropic": {
      "auth_type": "api_key",
      "endpoint": "https://api.anthropic.com/v1/messages",
      "models": ["claude-opus-5", "claude-sonnet-5"]
    },
    "openai": {
      "auth_type": "api_key",
      "endpoint": "https://api.openai.com/v1/chat/completions",
      "models": ["gpt-5"]
    },
    "google": {
      "auth_type": "oauth",
      "endpoint": "https://generativelanguage.googleapis.com/v1",
      "models": ["gemini-3-pro"]
    },
    "local-vllm": {
      "auth_type": "none",
      "endpoint": "http://localhost:8000/v1/chat/completions",
      "models": ["custom-model-name"]
    },
    "custom-openrouter-compatible": {
      "auth_type": "api_key",
      "endpoint": "user_defined",
      "models": ["user_defined"]
    }
  }
}
```

### 12.2 Tiga Jalur Autentikasi

| Tipe | Cara kerja | Contoh |
|---|---|---|
| **API Key** | Disimpan terenkripsi di local credential store, dikirim sebagai header saat request | Anthropic, OpenAI, OpenRouter |
| **OAuth** | Flow standar (authorization code + refresh token), token disimpan & di-refresh otomatis saat expired | Google, provider yang mendukung login akun |
| **Custom endpoint** | User mendefinisikan base URL + skema request sendiri (untuk self-hosted model / provider baru yang belum didukung native) | vLLM lokal, LM Studio, provider baru |

### 12.3 Adapter Layer (normalisasi format)

Karena tiap provider punya format request/response yang beda (Anthropic messages API ≠ OpenAI chat completions ≠ custom endpoint), butuh adapter yang menormalkan semuanya ke satu interface internal:

```js
interface ChatAdapter {
  formatRequest(internalMessages, tools): ProviderSpecificPayload;
  parseResponse(providerResponse): InternalResponse;
  parseStreamChunk(chunk): InternalStreamEvent;
}

const adapters = {
  anthropic: new AnthropicAdapter(),
  openai: new OpenAIAdapter(),
  "custom-openrouter-compatible": new OpenAICompatibleAdapter(), // banyak custom endpoint ikut skema OpenAI
};
```

Ini penting supaya Permission Gate, Tool Executor, dan Prompt Assembler tidak perlu tahu provider mana yang sedang dipakai — mereka bekerja dengan format internal yang seragam.

### 12.4 Model Routing per Mode

Menyambung ke bagian 2.2 dan Milestone sebelumnya — user bisa menentukan provider/model berbeda untuk plan vs build:

```json
{
  "mode_routing": {
    "plan": { "provider": "openai", "model": "gpt-5-mini" },
    "build": { "provider": "anthropic", "model": "claude-opus-5" }
  }
}
```

Berguna untuk optimasi biaya (model murah untuk eksplorasi/plan, model kuat untuk eksekusi kritis) atau fallback otomatis kalau satu provider down.

### 12.5 Keamanan Kredensial

- API key & OAuth token **tidak pernah** masuk ke system prompt atau log.
- Simpan di local secret store terenkripsi (mis. OS keychain, atau file terenkripsi dengan passphrase) — bukan plaintext di config biasa.
- Custom endpoint perlu validasi tambahan (SSL cert check, opsional allowlist domain) karena risiko mengirim data ke endpoint yang tidak tepercaya lebih tinggi dibanding provider resmi.

### 12.6 Fallback & Failover

Kalau provider utama gagal/rate-limited, router bisa otomatis mencoba provider cadangan yang terdaftar untuk model setara — dicatat di observability layer supaya user tahu kapan fallback terjadi.

