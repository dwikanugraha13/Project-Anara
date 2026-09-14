# PRD: AI Coding Agent dengan Plan/Build Mode & Autonomous Memory

**Versi:** 0.1 (Draft)
**Status:** Draft — belum diimplementasikan
**Pemilik:** AGNANN

---

## 1. Ringkasan Eksekutif

Membangun AI agent coding sendiri yang menggabungkan dua model desain:
- **Claude Code / OpenCode** — kontrol eksekusi lewat plan mode (read-only) dan build mode (eksekusi), dengan permission gate yang ditegakkan di level kode.
- **Hermes Agent** — keberlanjutan lintas sesi lewat persistent memory, skill library yang bertambah dari waktu ke waktu, dan kemampuan berjalan autonomous (dipicu scheduler/event, bukan hanya chat interaktif).

Tujuan akhir: agent yang aman untuk dipercaya melakukan perubahan kode (karena selalu merencanakan dulu sebelum eksekusi), sekaligus terasa "belajar" dan makin efektif tiap kali dipakai.

---

## 2. Latar Belakang & Masalah

Agent coding yang cuma langsung eksekusi (tanpa plan mode) berisiko membuat perubahan yang tidak diinginkan tanpa kesempatan review. Sebaliknya, agent yang cuma menyusun rencana tanpa memori tidak pernah belajar dari sesi sebelumnya — pola yang sudah berhasil harus disusun ulang dari nol tiap kali. Tidak ada solusi open-source/pribadi yang menggabungkan keduanya secara utuh untuk kebutuhan personal.

---

## 3. Tujuan (Goals)

1. Agent tidak pernah mengubah file/sistem tanpa melalui tahap rencana yang bisa direview.
2. Permission dibatasi mode ditegakkan di layer eksekusi tool, bukan hanya instruksi prompt.
3. Agent mengingat konteks project dan preferensi pengguna antar sesi (tidak reset tiap kali).
4. Agent bisa mengekstrak pola yang berhasil jadi skill reusable, dipakai otomatis di tugas serupa berikutnya.
5. Agent bisa dijalankan tanpa kehadiran user langsung (autonomous/terjadwal) dengan tetap aman.

### Non-Goals (di luar scope versi ini)
- Multi-user / SaaS multi-tenant.
- UI web penuh (fokus awal: CLI).

---

## 4. Target Pengguna

Pengguna tunggal (personal use) — developer yang mengerjakan beberapa project (web, embedded, dsb.) dan ingin asisten coding yang bisa dipercaya untuk perubahan otomatis maupun dijalankan di background.

---

## 5. User Stories

- Sebagai user, saya ingin agent menyusun rencana dulu sebelum mengubah kode, supaya saya bisa review sebelum ada perubahan nyata.
- Sebagai user, saya ingin menolak/mengedit rencana sebelum agent eksekusi.
- Sebagai user, saya ingin agent mengingat keputusan/preferensi project dari sesi sebelumnya tanpa saya jelaskan ulang.
- Sebagai user, saya ingin agent otomatis memakai pola yang pernah berhasil untuk tugas serupa.
- Sebagai user, saya ingin bisa menjadwalkan agent mengerjakan tugas rutin tanpa saya hadir, tapi tetap aman dari perubahan berisiko tanpa persetujuan.
- Sebagai user, saya ingin bisa melihat log setiap aksi yang dilakukan agent (audit trail).
- Sebagai user, saya ingin bisa membatalkan (rollback) perubahan yang sudah diterapkan agent.

---

## 6. Functional Requirements

### 6.1 Mode Management
- FR-1: Sistem punya dua mode eksplisit: `plan` dan `build`, disimpan sebagai field di session state.
- FR-2: User bisa berpindah mode kapan saja lewat command/shortcut.
- FR-3: Di plan mode, seluruh tool berkategori `mutating`/`ask` ditolak oleh Permission Gate sebelum eksekusi.
- FR-4: Output plan mode berupa daftar langkah terstruktur (JSON), bukan free text.
- FR-5: Transisi plan → build hanya terjadi setelah approval eksplisit dari user (kata kunci/command/tombol).

### 6.2 Tooling
- FR-6: Setiap tool terdaftar di registry dengan klasifikasi risiko: `read_only`, `mutating`, atau `ask`.
- FR-7: Tool kategori `ask` selalu minta konfirmasi eksplisit, terlepas dari mode aktif.
- FR-8: Perubahan file diterapkan sebagai diff dan tercatat lewat git commit otomatis per step build.
- FR-9: Eksekusi shell command berjalan dalam sandbox (container) dengan batas resource dan timeout.

### 6.3 Persistent Memory (struktur 4-file)
- FR-10: Sistem menyimpan memory dalam 4 file terpisah dengan pemilik dan scope berbeda:
  - `SOUL.md` (identitas agent, user-edit, global)
  - `USER.md` (profil user, agent-write, global, cap ~1.500 karakter)
  - `MEMORY.md` (fakta yang dipelajari agent, agent-write, cap ~2.200 karakter)
  - `AGENTS.md` (instruksi project, user-edit, per-project)
- FR-11: File yang agent tulis (USER.md, MEMORY.md) hanya diupdate saat mendeteksi trigger eksplisit ("ingat bahwa...", "catat...") — bukan menyimpan seluruh isi percakapan.
- FR-12: Semua file memory dimuat sebagai snapshot saat sesi mulai (bukan live-reload); perubahan berlaku di sesi berikutnya.
- FR-13: Setiap entry yang ditulis agent otomatis diberi timestamp, untuk keperluan audit dan proses pruning/reflektif di kemudian hari.
- FR-14: Saat menyusun plan, agent mengambil ringkasan memory yang relevan dengan tugas (retrieval keyword-based minimal untuk MVP).

### 6.4 Skill Library (folder + SKILL.md, mengikuti agentskills.io)
- FR-15: Tiap skill disimpan sebagai folder tersendiri berisi `SKILL.md` wajib (plus opsional `scripts/`, `references/`, `templates/`) — bukan satu file skill datar.
- FR-16: `SKILL.md` memakai YAML frontmatter dengan minimal field `name` dan `description`; body markdown berisi Overview, When to Use, dan Steps.
- FR-17: Sistem menerapkan progressive disclosure — hanya index ringkas (nama + description tiap skill) yang masuk system prompt secara default; isi penuh SKILL.md baru dimuat saat skill terpilih relevan dengan tugas.
- FR-18: Kredensial yang dibutuhkan skill (API key, OAuth token) dideklarasikan lewat field terpisah (`required_environment_variables` / `required_credential_files`), tidak pernah hardcoded di isi SKILL.md atau masuk ke context model.
- FR-19: Setelah build mode sukses menuntaskan plan, sistem menawarkan ekstraksi skill baru secara otomatis.
- FR-20: Skill baru/edit dari agent disimpan sebagai *pending* dan butuh approval eksplisit dari user (review diff) sebelum aktif — memakai jalur approval yang sama dengan Permission Gate.

### 6.5 Autonomous Mode
- FR-21: Agent bisa dipicu tanpa chat langsung, lewat scheduler (cron) atau event.
- FR-22: Session autonomous punya `trust_level` (`supervised` / `semi_autonomous` / `full_autonomous`) yang menentukan apakah plan butuh approval manual atau bisa auto-approve untuk tugas low-risk.
- FR-23: Permission Gate tetap berlaku sama persis di autonomous run seperti di interactive run — trust_level hanya mengubah siapa yang approve, bukan menonaktifkan gate.
- FR-24: User mendapat notifikasi saat ada plan autonomous yang menunggu approval.

### 6.6 Multi-Provider Model Support
- FR-25: Sistem mendukung lebih dari satu LLM provider lewat provider registry (bukan hardcoded ke satu provider).
- FR-26: Autentikasi provider mendukung tiga jalur: API key, OAuth (login akun), dan custom endpoint (self-hosted/provider baru).
- FR-27: Kredensial (API key, OAuth token) disimpan terenkripsi di local secret store, tidak pernah muncul di log atau system prompt.
- FR-28: User bisa menentukan provider/model berbeda untuk plan mode dan build mode secara terpisah (mode routing).
- FR-29: Jika provider utama gagal/rate-limited, sistem bisa failover otomatis ke provider cadangan yang terdaftar, dan mencatatnya di log.
- FR-30: Custom endpoint melewati validasi tambahan (mis. cek SSL) sebelum dipakai, karena tingkat kepercayaannya tidak sama dengan provider resmi.

### 6.7 Observability
- FR-31: Setiap tool call (nama, argumen, hasil, durasi, allow/deny) dicatat ke log terstruktur.
- FR-32: Token usage dan estimasi biaya dicatat per sesi.

---

## 7. Non-Functional Requirements

- NFR-1 (Keamanan): Tidak ada jalur yang memungkinkan tool `mutating`/`ask` dieksekusi di plan mode, bahkan jika model mencoba memanggilnya langsung.
- NFR-2 (Reliabilitas): Kegagalan tool transient (network/rate limit) di-retry otomatis dengan backoff, maksimal N percobaan.
- NFR-3 (Recoverability): Sesi yang terhenti paksa (crash) bisa di-resume dari state terakhir yang tersimpan.
- NFR-4 (Performa): Context window dikelola otomatis (compaction/summarization) supaya sesi panjang tidak gagal karena limit token.
- NFR-5 (Auditability): Semua perubahan file bisa ditelusuri dan di-rollback lewat git history.
- NFR-6 (Biaya): Ada batas token/biaya harian untuk autonomous run supaya tidak membengkak tanpa terkontrol.

---

## 8. Arsitektur (Ringkasan)

Lihat dokumen `rancangan-ai-agent.md` untuk detail arsitektur lengkap (Session Manager, Prompt Assembler, Permission Gate, Tool Executor, Memory & Skill Layer, Autonomous Loop). PRD ini merujuk ke dokumen tersebut sebagai spesifikasi teknis pendukung.

---

## 9. Scope Bertahap (Milestone)

### Milestone 1 — MVP Fungsional
Agent loop dasar, tool registry + klasifikasi risiko, permission gate, plan/build mode, format plan + approval flow, toggle mode manual.
**Definition of Done:** Agent bisa diminta mengerjakan tugas coding sederhana, selalu berhenti di plan mode dulu, tidak bisa mengubah file tanpa approval eksplisit.

### Milestone 2 — Hardening
Sandboxing eksekusi shell, diff-based editing + git integration, context compaction, error retry, streaming, logging dasar.
**Definition of Done:** Agent aman dijalankan terhadap project nyata tanpa risiko merusak sistem host, dan semua perubahan bisa di-rollback.

### Milestone 3 — Memory & Skill
Persistent memory (SQLite), skill extraction otomatis, retrieval memory/skill saat plan mode.
**Definition of Done:** Agent tidak perlu dijelaskan ulang konteks project di sesi baru, dan bisa memakai pola yang pernah berhasil.

### Milestone 4 — Autonomous
Scheduler/trigger layer, trust_level & approval policy, notifikasi plan pending.
**Definition of Done:** Agent bisa dijadwalkan mengerjakan tugas rutin tanpa user hadir, dengan tetap berhenti untuk approval pada aksi berisiko.

### Milestone 5 — Observability & Eval
Tracing lengkap, dashboard biaya, eval/regression test suite untuk permission logic dan kualitas plan.
**Definition of Done:** Ada visibilitas penuh atas perilaku agent dan cara mengukur regresi sebelum deploy perubahan.

### Milestone 6 — Multi-Provider
Provider registry, adapter layer (normalisasi format request/response), tiga jalur auth (API key/OAuth/custom endpoint), mode routing, failover otomatis.
**Definition of Done:** Agent bisa berpindah/menggabungkan provider (mis. Anthropic untuk build, model lain untuk plan) tanpa mengubah logic inti (permission gate, tool executor tetap sama), dan kredensial tersimpan aman.

---

## 10. Metrik Keberhasilan

- 0 insiden perubahan file tanpa approval di plan mode (target: 0, non-negotiable).
- Persentase plan yang disetujui tanpa revisi (indikator kualitas plan dari waktu ke waktu).
- Jumlah skill yang berhasil dipakai ulang di tugas berikutnya (indikator efektivitas skill layer).
- Rata-rata token/biaya per tugas selesai (indikator efisiensi).
- Waktu rata-rata dari trigger autonomous sampai tugas selesai atau menunggu approval.

---

## 11. Risiko & Mitigasi

| Risiko | Mitigasi |
|---|---|
| Model mencoba bypass permission gate lewat prompt injection | Permission gate di level kode, bukan cuma prompt; scan file konfigurasi yang bisa diedit user |
| Autonomous run membuat perubahan tak terduga saat user tidak hadir | trust_level default `supervised` di awal; aksi `ask` selalu tetap perlu approval manual |
| Context window penuh di tugas panjang, agent lupa instruksi awal | Context compaction otomatis + simpan instruksi kritikal di memory persisten |
| Skill yang tersimpan jadi usang/salah seiring project berubah | Skill baru/edit dari agent wajib lewat approval (pending → review diff → approve) sebelum aktif, bukan otomatis langsung dipakai |
| Biaya API membengkak dari autonomous run yang sering triggered | Budget cap harian, alert saat mendekati limit |
| Kredensial provider (API key/OAuth token) bocor lewat log atau config plaintext | Wajib local secret store terenkripsi; audit rutin memastikan tidak ada kredensial masuk system prompt/log |
| Custom endpoint mengarah ke server tidak tepercaya, berpotensi kebocoran data project | Validasi SSL, opsional allowlist domain, peringatan eksplisit ke user saat menambah custom endpoint baru |

---

## 12. Open Questions

- Retrieval memory/skill: cukup keyword matching, atau perlu embedding + vector store sejak awal?
- Skill yang saling bertentangan: siapa/apa yang memutuskan prioritas?
- Apakah butuh UI selain CLI di fase awal, atau CLI cukup untuk validasi konsep?
- Adapter layer dibangun native per provider dari awal, atau manfaatkan endpoint yang sudah OpenAI-compatible (banyak provider ikut skema ini) untuk mempercepat cakupan?
- OAuth flow butuh local callback server (redirect ke localhost) — apakah ini prioritas Milestone 1 atau bisa ditunda dan mulai dari API key saja dulu?

---

*Dokumen ini adalah requirement level produk. Untuk detail implementasi teknis, lihat `rancangan-ai-agent.md`.*
