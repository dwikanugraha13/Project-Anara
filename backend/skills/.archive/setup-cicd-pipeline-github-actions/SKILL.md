---
name: Setup CI/CD Pipeline GitHub Actions
category: devops
description: Mengonfigurasi alur kerja otomasi pengujian, linting, dan build pada
  repositori GitHub menggunakan GitHub Actions.
trigger_keywords:
- github actions
- ci/cd
- pipeline
- workflow
- automation
required_environment_variables: []
required_credential_files: []
status: active
learned_from_experience: false
created_at: '2026-09-18T17:59:29.264263'
updated_at: '2026-09-18T17:59:29.264263'
---

# Setup CI/CD Pipeline GitHub Actions

## Overview
Mengonfigurasi alur kerja otomasi pengujian, linting, dan build pada repositori GitHub menggunakan GitHub Actions.

## When to Use
Gunakan keahlian ini saat diminta atau mendeteksi tugas dengan kata kunci: github actions, ci/cd, pipeline, workflow, automation.

## Steps
1. Buat folder .github/workflows di root proyek
2. Susun berkas ci.yml dengan environment matrix Node.js dan Python
3. Tambahkan langkah automated testing dan type checking
4. Konfigurasi branch protection dan push trigger
