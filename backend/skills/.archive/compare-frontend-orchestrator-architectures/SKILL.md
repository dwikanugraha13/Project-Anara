---
name: compare-frontend-orchestrator-architectures
category: coding
description: Compare frontend orchestrator patterns between two codebases by identifying
  core files and mapping counterparts.
trigger_keywords:
- bedah orchestrator
- compare frontend
- bandingkan arsitektur
- frontend orchestrator
- anara vs anara
required_environment_variables: []
required_credential_files: []
status: active
learned_from_experience: true
created_at: '2026-10-03T17:45:48.866256'
updated_at: '2026-10-03T17:45:48.866256'
---

# compare-frontend-orchestrator-architectures

## Overview
Compare frontend orchestrator patterns between two codebases by identifying core files and mapping counterparts.

## When to Use
Use this skill when requested or when detecting tasks with keywords: bedah orchestrator, compare frontend, bandingkan arsitektur, frontend orchestrator, anara vs anara.

## Steps
1. Step 1: Identify the orchestration layer in each codebase — may not be a literal 'orchestrator' folder; check lib/, store/, app/, hooks/ directories.
2. Step 2: List top 5 core files by orchestration responsibility (message engine, session router, app router, queue/transport, status engine).
3. Step 3: For each file, note: line count, primary role, key patterns (state mgmt, transport, persistence).
4. Step 4: Map counterpart files across codebases by functional role, not by name.
5. Step 5: Summarize architectural differences: state management approach, transport (WS vs localStorage sync), separation of concerns, native integrations (e.g. git-native vs backend-dependent).
