---
name: Codebase Inspection & Discovery
category: exploration
description: Investigasi mendalam struktur repositori, dependensi, dan arsitektur
  kode menggunakan grep dan glob tanpa asumsi.
trigger_keywords:
- inspect
- codebase
- arsitektur
- pemetaan kode
- eksplorasi repo
required_environment_variables: []
required_credential_files: []
status: active
learned_from_experience: false
created_at: '2026-09-18T17:59:29.300451'
updated_at: '2026-09-18T17:59:29.300451'
---

# Codebase Inspection & Discovery

## Overview
Investigasi mendalam struktur repositori, dependensi, dan arsitektur kode menggunakan grep dan glob tanpa asumsi.

## When to Use
Gunakan keahlian ini saat diminta atau mendeteksi tugas dengan kata kunci: inspect, codebase, arsitektur, pemetaan kode, eksplorasi repo.

## Steps
1. Pindai pohon hierarki berkas menggunakan glob_find_files
2. Baca konfigurasi dependensi (package.json, requirements.txt, pyproject.toml)
3. Cari pola arsitektur kunci dan titik masuk aplikasi (main entrypoints)
4. Petakan aliran data dan modul ketergantungan sebelum melakukan perubahan
