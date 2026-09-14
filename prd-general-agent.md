# PRD: General-Purpose AI Agent
Setara Hermes — Multi-Channel, Autonomous, dengan Plan/Build Gate

**Versi:** 0.1 (Draft)
**Status:** Draft — belum diimplementasikan
**Pemilik:** AGNANN
**Dokumen terkait:** `rancangan-general-agent.md` (spesifikasi teknis), `prd.md`/`rancangan-ai-agent.md` (coding agent), `prd-chatbot.md`/`rancangan-chatbot.md` (chatbot)

---

## 1. Ringkasan Eksekutif

Membangun satu AI agent yang bisa dipakai baik sebagai asisten percakapan sehari-hari (multi-channel: CLI, messaging platform) maupun sebagai coding agent (code execution, shell, SSH) — mengikuti scope Hermes Agent, tapi menutup gap keamanan yang Hermes tidak punya: tidak ada plan/build gate untuk tools berisiko tinggi.

---

## 2. Latar Belakang & Masalah

Agent general-purpose seperti Hermes menggabungkan kemampuan luas (code execution, SSH, messaging, autonomous run) dalam satu sistem yang langsung eksekusi tanpa tahap rencana yang bisa direview. Ini menciptakan risiko: tool berisiko tinggi (shell, SSH) dipanggil dengan level keamanan yang sama longgarnya dengan tool percakapan biasa. Dibutuhkan sistem yang punya cakupan kemampuan setara, tapi dengan level keamanan yang mengikuti risiko tool, bukan mengikuti jenis interaksi.

---

## 3. Tujuan (Goals)

1. Satu sistem yang bisa diakses lewat multi-channel (CLI, minimal satu platform messaging) dengan perilaku aman konsisten di semua channel.
2. Tool berisiko tinggi (shell, code execution, SSH, file mutation) selalu wajib melalui plan mode, tidak peduli dari channel/mode mana request datang.
3. Percakapan biasa tetap natural tanpa friksi plan mode yang tidak perlu.
4. Agent bisa berjalan autonomous (terjadwal/event-triggered) dengan tetap tunduk ke gate keamanan yang sama seperti sesi interaktif.
5. Memory dan skill terakumulasi dan dipakai ulang lintas channel dan lintas jenis tugas (percakapan maupun coding).

### Non-Goals (di luar scope versi ini)
- Multi-user/SaaS multi-tenant.
- Dukungan channel messaging lebih dari 2 platform di versi awal.
- UI web penuh (CLI + minimal satu channel messaging cukup untuk validasi).

---

## 4. Target Pengguna

Pengguna personal yang ingin satu agent yang bisa diajak ngobrol santai lewat messaging app sehari-hari, sekaligus dipercaya mengerjakan tugas coding/otomasi sistem — tanpa harus pindah-pindah tool berbeda untuk tiap kebutuhan.

---

## 5. User Stories

- Sebagai user, saya ingin chat santai dengan agent lewat Telegram tanpa friksi approval untuk pertanyaan biasa.
- Sebagai user, saya ingin agent yang sama bisa saya minta mengerjakan tugas coding di project lokal saya, dengan tetap menyusun rencana dulu sebelum mengubah file.
- Sebagai user, saya ingin yakin bahwa perintah shell/eksekusi kode tidak pernah jalan tanpa saya approve, terlepas dari channel mana saya kirim perintahnya.
- Sebagai user, saya ingin agent bisa dijadwalkan mengerjakan tugas rutin (baik percakapan maupun coding) tanpa saya hadir, dengan tetap berhenti untuk approval pada aksi berisiko.
- Sebagai user, saya ingin skill dan konteks yang dipelajari agent dari sesi coding juga bisa membantu percakapan biasa saya, dan sebaliknya.
- Sebagai user, saya ingin mendapat notifikasi di channel manapun yang sedang saya pakai saat ada plan yang menunggu approval.

---

## 6. Functional Requirements

### 6.1 Unified Tool Risk Taxonomy
- FR-1: Setiap tool terdaftar dengan salah satu dari 4 tingkat risiko: `read_only`, `action`, `mutating`, `ask`.
- FR-2: Tool eksekusi shell/code/SSH diklasifikasikan `mutating`, bukan `action` — selalu wajib plan mode, tidak bisa dimatikan lewat preferensi user.
- FR-3: Tool destruktif/ireversibel (`ask`) selalu minta konfirmasi granular, terlepas dari mode atau hasil plan sebelumnya.

### 6.2 Plan Mode Unified (dua sub-mode)
- FR-4: Sistem punya `session_mode`: `conversational` (default, plan kondisional) atau `explicit_plan_build` (plan selalu eksplisit, dipakai saat user bekerja di project/codebase tertentu).
- FR-5: Di `conversational`, plan mode otomatis aktif untuk tool `mutating`/`ask`, dan kondisional untuk `action` signifikan.
- FR-6: Di `explicit_plan_build`, semua tool selain `read_only` wajib melalui plan mode sepanjang sesi.
- FR-7: User bisa eksplisit meminta plan mode kapan saja, terlepas dari deteksi otomatis.

### 6.3 Multi-Channel Input
- FR-8: Sistem menerima trigger dari minimal: interactive chat (CLI), satu platform messaging, dan scheduler/event.
- FR-9: Semua channel dinormalisasi ke format Request internal seragam sebelum diproses lebih lanjut oleh Session Manager/Plan Detector/Tool Executor.
- FR-10: Notifikasi (mis. plan menunggu approval) dikirim kembali ke channel asal request.

### 6.4 Session & Autonomous Run
- FR-11: Session state mencakup: `channel`, `session_mode`, `plan_state`, `run_type` (`interactive`/`autonomous`), `trust_level`.
- FR-12: Permission/Action Gate berlaku identik di run_type `interactive` maupun `autonomous` — trust_level hanya menentukan siapa yang approve plan, bukan menonaktifkan gate.
- FR-13: Autonomous run yang butuh approval mengirim notifikasi ke channel yang ditentukan user dan menunggu (pause), tidak auto-lanjut untuk tool `mutating`/`ask` kecuali trust_level `full_autonomous` secara eksplisit mengizinkan.

### 6.5 Persistent Memory & Skill (unified)
- FR-14: Struktur memory 4-file (SOUL.md/USER.md/MEMORY.md/AGENTS.md) dipakai sama persis baik untuk sesi percakapan maupun sesi coding; AGENTS.md hanya aktif saat `project_root` terisi.
- FR-15: Skill (folder + SKILL.md) bisa diekstrak dari sesi coding maupun sesi percakapan yang menyelesaikan tugas kompleks berulang.
- FR-16: Skill baru dari agent tetap wajib approval (pending → review → approve) sebelum aktif, tidak peduli dari sesi jenis apa asalnya.

### 6.6 Eksekusi Aman
- FR-17: Tool `mutating` yang melibatkan shell/code execution berjalan dalam sandbox (container terisolasi).
- FR-18: Perubahan file diterapkan sebagai diff dan tercatat via git commit otomatis per step build.

### 6.7 Privacy & Moderasi
- FR-19: Data sensitif difilter sebelum ditulis ke memory, berlaku sama di semua channel.
- FR-20: Layer moderasi konten aktif terutama untuk channel messaging yang berpotensi publik-facing (mis. grup Telegram/Discord).
- FR-21: User bisa melihat, mengedit, dan menghapus entry memory kapan saja.

### 6.8 Multi-Provider
- FR-22: Provider registry mendukung API key, OAuth, dan custom endpoint.
- FR-23: Routing model bisa berdasarkan mode (plan vs build) maupun channel (mis. model cepat untuk chat, model kuat untuk coding).

---

## 7. Non-Functional Requirements

- NFR-1 (Keamanan): Tidak ada jalur di channel manapun yang memungkinkan tool `mutating`/`ask` dieksekusi tanpa melalui plan mode/konfirmasi, bahkan dari autonomous run trust_level tinggi.
- NFR-2 (Konsistensi): Perilaku gate keamanan identik di semua channel — tidak ada channel yang "lebih longgar" dari yang lain.
- NFR-3 (UX): Percakapan non-risiko tetap natural tanpa friksi tambahan, di semua channel.
- NFR-4 (Reliabilitas): Autonomous run yang gagal/crash bisa di-resume dari state terakhir.
- NFR-5 (Auditability): Semua tool call, lintas channel, tercatat di log terstruktur yang bisa ditelusuri per sesi.

---

## 8. Scope Bertahap (Milestone)

### Milestone 1 — Fondasi Unified
Tool Risk Taxonomy, Session Manager gabungan, Plan Detector dengan default `conversational`.
**DoD:** Agent bisa menjawab percakapan biasa dan mendeteksi kapan butuh plan, di satu channel (CLI dulu).

### Milestone 2 — Gate & Eksekusi Aman
Permission/Action Gate 4-tingkat, sandboxing, diff+git integration.
**DoD:** Tool shell/code/file-mutation tidak pernah jalan tanpa approval, dan aman dieksekusi terhadap sistem nyata.

### Milestone 3 — Memory & Skill
Struktur 4-file, skill library dengan approval flow, privacy filter.
**DoD:** Agent mengingat konteks lintas sesi dan bisa mengekstrak skill dari tugas yang berhasil, baik dari percakapan maupun coding.

### Milestone 4 — Multi-Channel
Channel Adapter untuk minimal satu platform messaging, notifikasi lintas channel.
**DoD:** User bisa berinteraksi dari CLI maupun messaging app dengan perilaku dan memory yang konsisten.

### Milestone 5 — Autonomous
Scheduler/event trigger, trust_level policy, resume dari crash.
**DoD:** Agent bisa dijadwalkan mengerjakan tugas tanpa user hadir, tetap aman dan bisa dipulihkan kalau gagal di tengah jalan.

### Milestone 6 — Kematangan
Multi-provider routing per channel/mode, moderasi konten, observability lintas channel, eval/regression test.
**DoD:** Sistem siap dipakai harian dengan visibilitas penuh dan biaya terkontrol.

---

## 9. Metrik Keberhasilan

- 0 insiden tool `mutating`/`ask` dieksekusi tanpa approval, di channel/mode manapun (non-negotiable).
- Persentase percakapan biasa yang tidak terkena friksi plan mode yang tidak perlu.
- Jumlah skill yang berhasil dipakai ulang lintas jenis sesi (percakapan ↔ coding).
- Waktu rata-rata dari trigger autonomous sampai selesai atau menunggu approval.
- Konsistensi persona/perilaku yang dirasakan user di lintas channel (feedback kualitatif).

---

## 10. Risiko & Mitigasi

| Risiko | Mitigasi |
|---|---|
| Channel messaging (Telegram/Discord) jadi celah — user lain di grup memicu tool berisiko | Action/Permission Gate tetap identik di semua channel; pertimbangkan whitelist user_id yang boleh trigger tool `mutating` dari channel publik |
| Kompleksitas gabungan (dua sub-mode, multi-channel, autonomous) membuat sistem sulit di-debug | Observability lintas channel wajib sejak Milestone 2, bukan ditunda ke akhir |
| Skill dari sesi coding "bocor"/tidak relevan dipakai di sesi percakapan biasa, atau sebaliknya | Skill tetap ditag dengan konteks asal (coding/percakapan) untuk membantu retrieval yang tepat sasaran |
| Autonomous run di channel messaging publik mengirim notifikasi/aksi ke tempat yang salah | Validasi channel/user_id tujuan sebelum kirim aksi apapun dari sesi autonomous |

---

## 11. Open Questions

- Platform messaging mana yang jadi prioritas Milestone 4 — Telegram, Discord, atau WhatsApp?
- Apakah `session_mode` berpindah otomatis (mis. terdeteksi dari isi pesan) atau selalu eksplisit dari user/command?
- Untuk channel publik/grup, siapa yang punya wewenang approve plan — hanya owner akun, atau bisa didelegasikan?

---

*PRD ini adalah sintesis dari `prd.md` (coding agent) dan `prd-chatbot.md` (chatbot). Untuk requirement detail yang tidak diulang di sini, rujuk kedua dokumen tersebut beserta `rancangan-general-agent.md` untuk spesifikasi teknis.*
