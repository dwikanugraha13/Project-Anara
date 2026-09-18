---
name: Auto-Test Regression Suite
category: testing
description: Menjalankan pengujian regresi komprehensif pada seluruh subsistem backend
  dan frontend secara mandiri.
trigger_keywords:
- test
- regression
- pytest
- uji
- pengujian
required_environment_variables: []
required_credential_files: []
status: active
learned_from_experience: false
created_at: '2026-09-18T17:59:29.270984'
updated_at: '2026-09-18T17:59:29.270984'
---

# Auto-Test Regression Suite

## Overview
Menjalankan pengujian regresi komprehensif pada seluruh subsistem backend dan frontend secara mandiri.

## When to Use
Gunakan keahlian ini saat diminta atau mendeteksi tugas dengan kata kunci: test, regression, pytest, uji, pengujian.

## Steps
1. Jalankan python -m pytest backend/tests/test_subsystems.py
2. Jalankan npx tsc --noEmit pada frontend Next.js
3. Evaluasi output dan identifikasi subsistem yang bermasalah
4. Laporkan ringkasan hasil uji lulus ke pengguna
