# Rancangan Arsitektur General-Purpose AI Agent
Menggabungkan Coding Agent + Chatbot — Setara Hermes, dengan Plan/Build Gate yang Hermes Tidak Punya

Dokumen ini menyatukan `rancangan-ai-agent.md` (coding agent: plan/build mode, permission gate, sandboxing) dan `rancangan-chatbot.md` (chatbot: plan mode kondisional, memory, persona) jadi satu arsitektur general-purpose — mencakup tools berisiko tinggi (code execution, shell, SSH) *dan* interaksi percakapan multi-channel, tanpa kompromi di sisi keamanan.

---

## 1. Mengapa Digabung (bukan dipilih salah satu)

Dari analisis Hermes sebelumnya: agent general-purpose butuh **tools kelas coding agent** (code execution, SSH, file mutation) tapi **cara interaksi kelas chatbot** (multi-channel, percakapan natural, tidak selalu formal plan/build). Masalahnya, Hermes sendiri punya tools berisiko tinggi itu **tanpa** plan/build gate yang keras — itu gap yang rancangan ini tutup.

Prinsip inti: **level keamanan mengikuti tool yang dipanggil, bukan mengikuti "jenis agent"**. Satu sistem, satu gate, berlaku konsisten baik dipicu dari chat santai maupun dari scheduler otomatis.

---

## 2. Unified Tool Risk Taxonomy

Gabungkan skema `mutating` (dari coding agent) dan `action` (dari chatbot) jadi satu skema 4-tingkat:

```js
const TOOLS = {
  // Tingkat 1 — read_only: selalu bebas jalan, di mode/channel apa pun
  read_file:       { risk: "read_only" },
  search_code:     { risk: "read_only" },
  web_search:       { risk: "read_only" },
  fetch_document:   { risk: "read_only" },
  read_calendar:    { risk: "read_only" },

  // Tingkat 2 — action: efek ke dunia luar, tapi terisolasi & reversible
  send_email:       { risk: "action" },
  create_event:     { risk: "action" },
  make_purchase:    { risk: "action" },

  // Tingkat 3 — mutating: mengubah sistem/file, SELALU wajib plan mode dulu
  write_file:       { risk: "mutating" },
  edit_file:        { risk: "mutating" },
  run_shell:        { risk: "mutating" },   // gap yang Hermes tidak punya gate-nya
  execute_code:     { risk: "mutating" },
  ssh_connect:      { risk: "mutating" },
  subagent_delegate:{ risk: "mutating" },

  // Tingkat 4 — ask: destruktif/ireversibel, SELALU minta konfirmasi granular
  delete_file:      { risk: "ask" },
  git_push_force:   { risk: "ask" },
  drop_database:    { risk: "ask" },
  delete_data:      { risk: "ask" },
};
```

`run_shell` dan `execute_code` sengaja dinaikkan ke `mutating` (bukan `action` ringan seperti kirim email) — inilah yang menambal celah Hermes.

---

## 3. Unified Plan Detector

```js
function needsPlan(request, detectedTools, sessionMode) {
  const risk = getHighestRisk(detectedTools); // read_only < action < mutating < ask

  if (sessionMode === "explicit_plan_build") {
    // dipakai saat user eksplisit kerja di satu project/codebase (mirip Claude Code)
    return risk !== "read_only";
  }

  // default: percakapan umum, mode kondisional (mirip chatbot)
  if (risk === "read_only") return false;
  if (risk === "action") return isSignificant(request);
  if (risk === "mutating" || risk === "ask") return true; // TIDAK BISA dimatikan user

  return false;
}
```

Dua sub-mode operasional:
- **`conversational` (default)** — plan mode kondisional seperti chatbot; hanya muncul untuk action signifikan atau tool berisiko tinggi.
- **`explicit_plan_build`** — user secara sadar masuk ke konteks kerja project (mis. buka folder tertentu, mulai sesi coding), plan mode jadi eksplisit sepanjang sesi seperti Claude Code.

Poin krusial: untuk risk `mutating`/`ask`, plan mode **tidak bisa dimatikan lewat preferensi user** — beda dari action ringan yang boleh di-skip kalau user memilih "langsung eksekusi tanpa nanya".

---

## 4. Multi-Channel Input Layer (elemen baru dari Hermes, belum ada di 2 dokumen sebelumnya)

```
Trigger Sources
├── Interactive chat (CLI/web/app)
├── Messaging platforms (Telegram, Discord, Slack, dst.)
└── Scheduler/event (cron, webhook, file-change)
        │
        ▼
   Channel Adapter — normalisasi ke format Request internal seragam
   { text, attachments, channel_id, user_id, trigger_type }
        │
        ▼
   Session Manager
```

Channel Adapter penting supaya Permission Gate/Plan Detector/Tool Executor di belakangnya **tidak perlu tahu** request datang dari Telegram atau dari CLI — semua diperlakukan sama lewat format internal seragam.

---

## 5. Session Manager (gabungan semua sumbu keputusan)

```json
{
  "session_id": "uuid",
  "channel": "telegram",
  "session_mode": "conversational",
  "plan_state": { "active": false, "current_plan": null },
  "run_type": "interactive",
  "trust_level": "supervised",
  "project_root": null,
  "history": [],
  "token_usage": { "input": 0, "output": 0 }
}
```

- `channel` — dari mana request datang (untuk routing notifikasi balik).
- `session_mode` — `conversational` atau `explicit_plan_build` (section 3).
- `plan_state` — status plan aktif, terpisah dari mode supaya bisa dilacak per-request dalam sesi conversational.
- `run_type` + `trust_level` — sama seperti rancangan coding agent (section 11.1 di `rancangan-ai-agent.md`), berlaku sama persis di sini untuk autonomous run lewat scheduler/event.
- `project_root` — `null` untuk sesi percakapan biasa, terisi saat `session_mode = "explicit_plan_build"`.

---

## 6. Alur Lengkap (menyatukan semua bagian)

```
Trigger (chat/messaging/scheduler)
        │
        ▼
Channel Adapter → normalisasi Request
        │
        ▼
Session Manager → tentukan/lanjutkan session_mode
        │
        ▼
Deteksi tools yang relevan dari request
        │
        ▼
needsPlan(request, tools, session_mode)?
        │
   ┌────┴────┐
   │ Tidak     │ Ya
   ▼           ▼
Jawab      [Plan Mode]
langsung    Prompt Assembler (Identity + Memory + Skills + Project Context bila ada)
             │
             ▼
        LLM susun rencana (read-only reasoning)
             │
             ▼
        Approval:
        - run_type interactive → user approve manual
        - run_type autonomous → sesuai trust_level (section 11.1 rancangan-ai-agent.md)
             │
             ▼ (approve)
        [Build Mode] eksekusi via Tool Executor
             │
             ▼
        Permission/Action Gate per tool (unified taxonomy, section 2)
        - read_only → langsung jalan
        - action → sudah di-approve di plan (atau skip kalau non-significant)
        - mutating → HARUS lewat plan mode (tidak ada jalur pintas)
        - ask → konfirmasi granular tambahan, apa pun mode-nya
             │
             ▼
        Tool Executor (sandboxed untuk shell/code execution)
             │
             ▼
        Skill Extractor (jika sukses & signifikan) → pending → user approve
             │
             ▼
        Memory Update (MEMORY.md/USER.md) sesuai trigger
             │
             ▼
        Respons dikirim balik lewat channel asal
```

---

## 7. Persistent Memory & Skill (tidak berubah, sudah unified sejak awal)

Struktur 4-file (SOUL.md/USER.md/MEMORY.md/AGENTS.md) dan skill library (folder + SKILL.md, progressive disclosure, approval flow) dari `rancangan-ai-agent.md` section 11.2–11.3 **dipakai apa adanya** — tidak ada perbedaan antara konteks chatbot dan coding di layer ini. AGENTS.md hanya relevan saat `project_root` terisi (`session_mode = explicit_plan_build`).

---

## 8. Privacy, Moderasi & Sandboxing (gabungan kebutuhan keduanya)

| Kebutuhan | Sumber | Tetap berlaku di general agent? |
|---|---|---|
| Sandboxing eksekusi shell/code | coding agent | Ya — wajib, karena tools `mutating` sama persis dipakai di sini |
| Diff-based editing + git integration | coding agent | Ya, untuk tool `write_file`/`edit_file` |
| Privacy filter sebelum tulis memory | chatbot | Ya — berlaku universal, tidak peduli channel/mode |
| Moderasi konten | chatbot | Ya — terutama penting karena multi-channel (Telegram/Discord publik-facing) |
| Kontrol user atas memory (lihat/edit/hapus) | chatbot | Ya |

---

## 9. Multi-Provider (tidak berubah)

Provider registry, adapter layer, tiga jalur auth (API key/OAuth/custom endpoint), mode routing — dari `rancangan-ai-agent.md` section 12, dipakai apa adanya. Tambahan: routing bisa juga berdasarkan `channel` (mis. respons cepat di Telegram pakai model murah, sesi coding di CLI pakai model kuat).

---

## 10. Roadmap Implementasi

**Fase 1 — Fondasi Unified**
1. Unified Tool Risk Taxonomy (section 2) + registry
2. Session Manager dengan semua field gabungan (section 5)
3. Unified Plan Detector (section 3), default `conversational` mode dulu

**Fase 2 — Gate & Eksekusi Aman**
4. Permission/Action Gate 4-tingkat, ditegakkan di kode
5. Sandboxing shell/code execution
6. Diff-based editing + git integration untuk tool `mutating`

**Fase 3 — Memory & Skill**
7. Struktur 4-file (SOUL/USER/MEMORY/AGENTS)
8. Skill library (folder + SKILL.md) dengan approval flow
9. Privacy filter sebelum penulisan memory

**Fase 4 — Multi-Channel & Autonomous**
10. Channel Adapter untuk minimal 1 platform messaging (mis. Telegram) + CLI
11. Scheduler/event trigger + `run_type`/`trust_level`
12. Notifikasi plan pending lintas channel

**Fase 5 — Kematangan**
13. Multi-provider routing (termasuk per-channel)
14. Moderasi konten
15. Observability lintas channel + eval/regression test

---

## 11. Perbandingan Akhir

| | Coding Agent (`rancangan-ai-agent.md`) | Chatbot (`rancangan-chatbot.md`) | General Agent (dokumen ini) |
|---|---|---|---|
| Plan mode | Selalu eksplisit | Kondisional per-request | Kondisional, tapi eksplisit saat `session_mode=explicit_plan_build` |
| Tool berisiko tinggi (shell/code) | Ya, dengan gate keras | Tidak ada | Ya, dengan gate keras (warisan coding agent) |
| Multi-channel | Tidak | Tidak eksplisit | Ya — elemen baru |
| Memory & Skill | Ya | Ya (skill lebih sederhana) | Ya, unified |
| Autonomous + trust_level | Ya | Tidak dibahas | Ya |
| Cocok untuk | Satu project/codebase | Percakapan umum | Keduanya sekaligus, seperti Hermes tapi lebih aman |

---

*Dokumen ini adalah sintesis akhir. Detail masing-masing komponen yang tidak diulang di sini tetap dirujuk dari `rancangan-ai-agent.md` (section 2–12) dan `rancangan-chatbot.md` (section 5–7).*

---

## 12. Approval Flow per Channel

Channel (Telegram, CLI, dashboard web, dst.) hanya lapisan I/O — cara approval "terlihat" bisa beda-beda, tapi Permission Gate di Tool Executor selalu memakai aturan yang sama: cek `session.mode === "build"` dan `tool.risk` sesuai kebijakan (section 2). Channel tidak tahu dan tidak perlu tahu detail gate-nya — dia hanya mengubah `session.mode`, lalu Tool Executor yang menentukan apa yang boleh jalan.

### 12.1 Bentuk Approval di Channel Chat (contoh: Telegram)

```
Bot: 📋 Rencana untuk "deploy fitur checkout ke staging":
     1. Buat migration tabel orders
     2. Update OrderController
     3. Jalankan test suite
     4. Deploy ke staging

     [✅ Approve] [✏️ Edit] [❌ Reject]
```

Dua cara approval yang didukung:
- **Inline keyboard button** (`InlineKeyboardMarkup` di Telegram Bot API) — lebih andal karena payload callback-nya terstruktur (`callback_data: "approve:plan_id_xxx"`), tidak bergantung parsing teks bebas.
- **Reply teks bebas** ("ya", "approved", "lanjut") sebagai fallback — butuh NLU ringan untuk menangkap variasi bahasa informal.

### 12.2 Mapping Approval ke Session yang Tepat

Approval harus terikat ke `plan_id` spesifik, bukan asumsi "pesan terakhir di chat ini" — supaya tidak nyasar kalau user kirim beberapa request beruntun sebelum yang pertama di-approve.

```js
async function handleTelegramCallback(callbackQuery) {
  const [action, planId] = callbackQuery.data.split(":");
  const session = await getSessionByPlanId(planId);

  // validasi kritis: yang approve harus user yang sama/authorized
  if (callbackQuery.from.id !== session.telegram_user_id
      && !isAuthorizedApprover(callbackQuery.from.id, session)) {
    return replyUnauthorized(callbackQuery);
  }

  if (action === "approve") {
    session.mode = "build";
    session.plan_state.active = false;
    await persistSession(session);
    await startBuildExecution(session);
  }
}
```

### 12.3 Di Mana Build Mode Benar-Benar Dieksekusi

Channel cuma jalur komunikasi — eksekusi sebenarnya tetap terjadi di Tool Executor (sandboxed, section 3 `rancangan-ai-agent.md`), bukan di server bot channel itu sendiri:

```
Channel Server / Bot (I/O layer)
        │  approve diterima
        ▼
Session Manager → ubah mode ke "build"
        │
        ▼
Enqueue job ke Tool Executor (proses/worker terpisah,
    async karena build mode bisa berjalan lama)
        │
        ▼
Tool Executor jalan di sandbox (container/VM)
        │  progress per step
        ▼
Kirim update balik ke channel asal lewat API channel tsb.
    (editMessageText / kirim pesan baru untuk Telegram,
     update UI untuk dashboard web/CLI)
```

Karena build mode bisa berjalan lama, **jangan blocking** di dalam webhook/request handler channel — pakai job queue, channel cuma kirim update progres secara berkala.

### 12.4 Update Progres

```
Bot: 🔨 Eksekusi dimulai...
Bot: ✅ Step 1/4: Migration tabel orders — selesai
Bot: ✅ Step 2/4: Update OrderController — selesai
Bot: ⏳ Step 3/4: Menjalankan test suite...
Bot: ⚠️ Step 3/4 gagal — 2 test tidak lulus. Lanjutkan ke step 4? [Lanjut] [Stop & rollback]
```

Step yang gagal di tengah jalan menjadi **checkpoint approval baru** — bukan otomatis lanjut, bukan juga otomatis stop total. User yang memutuskan.

### 12.5 Kasus Khusus per Channel

| Kasus | Penanganan |
|---|---|
| User approve tapi baru direspons lama setelah plan dibuat | Plan punya `expires_at`; kalau sudah kedaluwarsa, tolak dan minta susun ulang (konteks/kode mungkin sudah berubah) |
| Plan datang dari autonomous run (bukan direct chat) | Channel adapter kirim pesan/notifikasi proaktif ke channel_id yang terdaftar, bukan menunggu user chat duluan |
| User approve dari device berbeda dari tempat project berada (mis. approve dari HP, project di server) | `project_root` terikat ke environment tempat Tool Executor jalan (server/daemon yang selalu nyala), bukan ke device tempat user approve |
| Beberapa user berbagi akses ke satu channel/bot | `isAuthorizedApprover()` mengecek eksplisit siapa boleh approve plan tertentu — wajib untuk tool `mutating`/`ask` |

### 12.6 Prinsip yang Tetap Tidak Berubah

Permission Gate di Tool Executor tidak tahu dan tidak peduli approval datang dari tombol Telegram, command CLI, klik di dashboard web, atau auto-approve trust_level — dia hanya mengecek apakah `session.mode === "build"` dan `tool.risk` sesuai kebijakan (section 2). Inilah yang menjaga konsistensi keamanan lintas channel sebagai prinsip inti sistem (section 1) — channel boleh beragam bentuknya, tapi gate keamanannya satu dan sama untuk semuanya.
