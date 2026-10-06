---
category: autonomous-ai-agents
name: messaging-gateway-lifecycle
description: Use when managing agent gateway lifecycle and recovery.
---

# Messaging Gateway Lifecycle and Operations

Use this skill when auditing, operating, or troubleshooting agent messaging gateways (Telegram, Discord, Slack) across process crashes, cold boots, and background service lifecycles.

## Core Operational Invariants

### 1. Cold-Boot Stale Update Dropping vs User Feedback
- In messaging gateways recovering from downtime (e.g. Telegram polling adapters), enabling `drop_pending_on_cold_boot: true` or calling `deleteWebhook(drop_pending_updates=True)` prevents message queue stampedes, duplicate turn replays, and execution cascades.
- **Pitfall:** Messages sent by users while the gateway was offline are discarded with zero feedback. Users immediately assume the bot is still down or broken ("masih belum bisa") because their previous prompt received no answer.
- **Workflow:** Whenever an offline gateway boots or reconnects, inspect recent session records and dispatch an explicit reconnect broadcast (`Sent restart notification to chat_id`) to inform active users that the gateway is back online and prompt them to re-send dropped messages.

### 2. Multi-Step Exploration Latency Masking
- When a messaging user's prompt triggers FTS database searches, subagent delegations, or multi-step tool loops (e.g. 10+ tool iterations searching past session transcripts), execution time can easily reach 30–60 seconds.
- Maintain an active platform typing indicator (`sendChatAction(action="typing")`) in an async recurring heartbeat loop throughout tool execution. Without this, messaging platforms look completely unresponsive during heavy queries.

### 3. Gateway Environment Credential Inheritance
- When custom or local model proxies (e.g. `localhost:20128/v1`) are defined in `config.yaml` using dynamic environment references (`key_env`), ensure the background service environment explicitly sources `.env`.
- If `key_env` points to a variable missing from the background process environment, requests silently fall back to placeholder credentials, triggering HTTP 401 Unauthorized errors on authentication-gated endpoints.

### 4. Windows Background Job Object Process Termination
- On Windows hosts, background gateways spawned from interactive shells that belong to a Windows Job Object terminate automatically when the parent console exits (`#91675`).
- Use dedicated service runners (`schtasks` onlogon or detached startup VBScript launchers) rather than foreground shell spawns to ensure persistent survivability across terminal closures.

### 5. Two-Tier Authorization & Gateway Reload via In-Chat Slash Commands
- **GUI Setting Scope Distinction:** In desktop management interfaces, messaging configuration panels commonly expose basic conversation whitelists (`allow_from` / "Allowed User IDs") designed to prevent unsolicited DMs from strangers. Privileged capabilities—such as cross-session inspection (`/sessions all`) and cross-origin resumption (`/resume --all`)—require explicit registration in the administrative tier (`platforms.<platform>.extra.allow_admin_from`).
- **Reloading via Native In-Chat `/restart`:** Mutating `config.yaml` (directly or via `anara config set`) does not hot-apply security tier changes to an actively running gateway daemon in RAM. Attempting to execute `anara gateway restart` from within an agent terminal tool fails closed because terminating the parent gateway kills child process trees.
- **Workflow:** Set configuration keys via CLI (`anara config set platforms.<platform>.extra.allow_admin_from '["<id>"]'`), then instruct the user or trigger the platform's native in-chat `/restart` slash command directly within the messenger DM. The gateway gracefully drains active turns, reboots its process, and reloads security policies without manual process-tree killing.
