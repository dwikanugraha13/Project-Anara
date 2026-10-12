---
name: Eksplorasi & Pemetaan Struktur Proyek
category: coding
description: Memindai seluruh hierarki folder proyek (file tree) untuk memahami arsitektur
  kode dan dependensi.
trigger_keywords:
- folder
- proyek
- project
- struktur
- scan folder
- repo
- arsitektur
required_environment_variables: []
required_credential_files: []
status: active
learned_from_experience: false
created_at: '2026-09-15T04:05:01.011385'
updated_at: '2026-09-15T04:05:01.011385'
---

# Eksplorasi & Pemetaan Struktur Proyek

## Overview
Memindai seluruh hierarki folder proyek (file tree) untuk memahami arsitektur kode dan dependensi.

## When to Use
Gunakan keahlian ini saat diminta atau mendeteksi tugas dengan kata kunci: folder, proyek, project, struktur, scan folder, repo, arsitektur.

## Steps
1. Pindai folder proyek menggunakan scan_workspace_folder
2. Filter direktori berat (.git, node_modules, venv)
3. Petakan arsitektur berkas utama dan dependensi package
4. Tampilkan pohon berkas interaktif di layar HUD
