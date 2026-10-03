# Project Anara — Frontend & Omnichannel Design System (DESIGN.md)

Dokumen ini adalah **single source of truth** untuk standar arsitektur UI/UX, prinsip desain visual, kontrak komponen, dan aturan penyajian pesan di seluruh platform Project Anara (Web Studio, Desktop, dan Omnichannel Gateway).

Aturan utama: **Tokens over literals, flat over boxed, zero AI slop.**

---

## 1. Prinsip Utama (Core Principles)

1. **Liquid Glass Aesthetic:**
   * Latar belakang: Deep cosmic obsidian (`#030712` dan `#060913`).
   * Material: Frosted glass blur (`backdrop-blur-xl` hingga `backdrop-blur-3xl`) dengan specular hairlines (`border-white/[0.08]`).
   * Aksen: Subtle luminous cyan (`#22d3ee`) dan indigo/violet (`#6366f1`) sebagai penanda status aktif, telemetry, dan interaksi.
   * Zero raw emojis di komponen inti: Gunakan ikon grafis SVG modern berpresisi tinggi (Lucide / Codicon style).

2. **Flat, Not Boxed (Anti Card-in-Card Nesting):**
   * Dilarang keras membuat kartu di dalam kartu dengan border berlapis-lapis (*nested boxed cards*).
   * Pemisahan hierarki visual wajib mengandalkan whitespace konsisten, kontras tipografi, dan satu hairline 1px halus (`border-white/[0.08]`).

3. **Contextual Split-Pane (50/50 Workspace):**
   * Aktivitas membaca berkas, menulis kode, diff review, dan terminal PTY tidak boleh membuang konteks obrolan chat.
   * Saat agen berinteraksi dengan berkas atau terminal, Anara membuka **docked split-pane 50/50** di samping timeline obrolan.

4. **Intent Before Automation:**
   * Penelusuran file dan eksekusi tool menampilkan pill progres yang ringkas.
   * Panel samping hanya terbuka otomatis jika ada aksi mutasi berkas atau permintaan eksplisit dari pengguna.

---

## 2. Standar 3D Avatar Engine (Photorealistic Humanoid Stage)

1. **Focal Framing & Kamera:**
   * Portrait focal framing 85mm (`FOV: 34`, `position: [0, -0.06, 1.82]`) untuk proporsi anatomis wajah manusia yang natural tanpa distorsi lensa wide-angle.
2. **6-Point Studio Portrait Lighting:**
   * Key Light (Daylight hangat, `intensity: 1.35`).
   * Fill Light (Soft daylight, `intensity: 0.85`).
   * Front Beauty Glow (Radiant skin glow, `intensity: 0.65`).
   * Golden Rim Light (Aksen rambut & bahu kanan, `intensity: 2.0`).
   * Edge Light (Siluet bahu kiri, `intensity: 1.6`).
   * Under-chin Bounce (Subsurface scattering bounce, `intensity: 0.60`).
3. **Engine Robustness & WebGL Lifecycle:**
   * Texture decoding wajib menggunakan `HTMLImageElement` `TextureLoader` asli (bukan `ImageBitmapLoader`) untuk mencegah pemblokiran blob concurrency dan proteksi sidik jari browser.
   * Render loop React-Three-Fiber wajib berjalan di default `priority 0` agar canvas auto-render di 60 FPS tanpa jeda.
   * Zero Fallback Hijacking: Error boundary hanya merespons kegagalan hardware GPU fatal, tidak boleh membunuh canvas 3D hanya karena probe context sementara.

---

## 3. Komponen Chat & Tool Execution Cards

1. **Thinking Card:**
   * Tampil sebagai single-line hairline pill di atas balasan asisten.
   * Membawa timer durasi berpikir (`Thought for X.Xs`) dan chevron disclosure untuk melihat proses reasoning lengkap.
2. **File Mutation & Diff Card:**
   * Terbuka default (*expanded*) saat pembuatan atau modifikasi berkas.
   * Tabel diff membawa nomor baris ganda (`oldLine` / `newLine`), badge statistik ringkas (`+added -deleted`), dan syntax highlighting bersih.
   * Tombol aksi kontekstual: `View` (buka di Code Studio) dan `Revert` (rollback checkpoint instan).
3. **Terminal Run Card:**
   * Prompt baris tunggal `$ <command>` dengan badge exit code (`0` hijau / `1` merah) dan durasi eksekusi dalam milidetik.
   * Log output monospace dapat di-scroll secara independen (`overscroll-y: auto`) tanpa mengunci scroll timeline obrolan.
4. **CardStack / Status Stack:**
   * Status progress agen di atas input dock tampil sebagai baris tipis bertingkat (*hairline pills*) dengan status dot detak napas (*breathe dot*).

---

## 4. Standar Omnichannel Presenter (Telegram, Discord, WhatsApp)

1. **Live Tool Progress Bubble:**
   * Single-message in-place dynamic editing: bot mengirim 1 pesan status yang diperbarui berkala dengan debounce (minimal jeda 0.8s) agar aman dari batas rate limit Telegram API HTTP 429.
   * Perintah terminal wajib diformat ke dalam fenced code block native:
     ```shell
     <perintah_shell>
     ```
     atau
     ```powershell
     <perintah_powershell>
     ```
   * Operasi berkas disajikan dengan verb yang jelas:
     * `📖 Reading <file> L<range>`
     * `🔍 Searching files for <keyword>`
     * `✏️ Editing <file>`
     * `📂 Listing <folder>`
   * Zero Status Fluff: Dilarang memuntahkan baris `✓ Complete` atau status dummy yang mengotori riwayat chat.
2. **Consecutive Deduplication:**
   * Jika tool yang sama membaca berkas berkali-kali secara berturut-turut, sistem tidak mencetak baris baru melainkan mengumpulkan counter: `(×2)`, `(×3)`.
3. **Natural Message Chunking:**
   * Pembagian pesan panjang wajib mengalir secara natural per batas paragraf dan blok kode.
   * Dilarang menambahkan header robotik buatan seperti `[Bagian 1/2]` atau `[Part 1/2]`.
   * Jawaban naratif final dikirim sebagai pesan baru terpisah tepat di bawah bubble riwayat eksekusi tool.

---

## 5. Background Self-Improvement & Lifelong Learning

1. **Pemisahan Penyimpanan 3 Jalur:**
   * **Profil & Persona:** Disimpan ke `backend/cognition/USER.md`.
   * **Fakta Lingkungan & Sistem:** Disimpan ke `backend/cognition/MEMORY.md`.
   * **SOP & Prosedur Teknis:** Disimpan ke `%LOCALAPPDATA%\anara\skills\<category>\<name>\SKILL.md`.
2. **Zero Junk Skills:**
   * Reviewer background dilarang membuat skill sampah untuk obrolan kasual. Skill baru hanya dibuat jika ada alur prosedur teknis yang diselesaikan secara tuntas dan reusable.
3. **Resilient JSON Parser:**
   * Parser output LLM auxiliary wajib memiliki auto-repair untuk tag unclosed brackets (`[` dan `{`) serta string literals guna menjamin receipt *`💾 Self-improvement review`* terbit tanpa silent failure.
