---
category: autonomous-ai-agents
name: agent-database-and-state-store-engineering
description: Use when designing or resetting agent SQLite state stores.
---

# Agent Database and State Store Engineering

Use this skill when designing, migrating, auditing, or resetting autonomous AI agent persistent state stores, SQLite databases (`state.db`, `anara_brain.db`), session ledgers, and cognitive memory stores.

## Core Architectural Invariants

### 1. Ephemeral vs Durable Data Store Partitioning
- In autonomous agent architectures, SQLite databases combine high-churn ephemeral interaction logs with critical durable system configurations.
- Categorize tables strictly into two distinct tiers:
  1. **Ephemeral Tiers (Wipeable):** `conversations`, `chat_sessions`, `delivery_obligations`, `memories_fts`, `token_usage_logs`, and transient task scratchpads. These accumulate conversational debris, legacy prompt context, and historical session bindings that cause context bleed-over if left unpruned.
  2. **Durable Tiers (Critical — Must Preserve):** `speakers` (biometric voice embeddings, acoustic sample counts, preferred tone), `custom_providers` (local proxies, base URLs, prefix routes), `ai_accounts` (API keys, account labels, status), and core `app_settings` (bot tokens, channel admin IDs, active AI model selections).
- **Pitfall:** Blindly deleting database files without selective table recovery wipes all registered bot credentials and biometric profiles, requiring manual re-enrollment and breaking active messaging integrations.

### 2. Zero-Downtime Safe Database Reset Procedure
When an agent database accumulates stale context, corrupted session mappings, or legacy workspace bindings, execute a 5-step surgical reset:
1. **Halt Daemon Supervision:** Stop running background daemons (`cli.py daemon stop`) before touching database files to release file locks on Windows (`WinError 32`) and prevent concurrent write corruption.
2. **Atomic Timestamped Backup:** Copy `.db`, `-wal`, and `-shm` files into an isolated backup folder (`backup_pre_reset_<timestamp>/`) before removal, ensuring instant zero-data-loss rollback.
3. **Pristine Schema Bootstrap:** Remove the active database files and start the agent service (`cli.py daemon start`). Allow the migration engine to recreate clean tables, default indexes, and baseline seeds from code.
4. **Selective Durable State Migration:** Execute a parameterized SQLite migration script transferring durable rows (`speakers`, `custom_providers`, `ai_accounts`, and core `app_settings`) from the backup database into the freshly initialized active database.
5. **Regression Verification:** Run the full invariant test harness (`run_tests.py` and unit test suites) to verify database connectivity, provider discovery, and zero-dropped configuration.

### 3. Explicit External Workspace Flagging in Session Records
- Database session tables (`chat_sessions`) storing project workspace metadata (`workspace_info_json`) must enforce an explicit boolean flag (`"is_external": true`) for user-attached folders.
- Never write default repository paths (e.g. the agent's host development repo) into session workspace columns with implicit or false flags (`"is_external": false`).
- Session resolution queries must verify `is_external is True` before binding workspace paths. If unflagged or null, resolve to a clean neutral context (e.g. User Home `~`) rather than falling back to historical database paths.
- **Pitfall:** Storing legacy or default repository paths in session records causes new chat sessions to load outdated workspace snapshots, misleading the model into claiming it is operating inside the agent's internal source tree.

### 4. Canonical Session Key Indexing vs Mutable Titles
- Omnichannel inbound sessions (Telegram, WhatsApp, Discord) must bind to database records using unique indexed canonical keys (`session_key = "channel_{platform}_{channel_id}"`), never by matching patterns inside mutable `title` columns.
- LLM title summarizers dynamically overwrite session titles after initial turns (e.g. renaming "Telegram Chat" to a topic summary).
- Matching incoming messages by title substring creates fragmented duplicate sessions on subsequent turns whenever the title changes.
- **Pitfall:** Querying channel sessions via `WHERE title LIKE '%[telegram:12345]%'` breaks persistence as soon as an auto-titling worker renames the conversation, causing split-brain session creation.

### 5. Durable Outbox Delivery Obligations Ledger
- Network dispatches across messaging adapters must be recorded in an SQLite ledger (`delivery_obligations`) with explicit state transitions (`pending` -> `attempting` -> `delivered` / `failed`).
- When the gateway daemon restarts, the startup lifecycle must execute a sweep (`sweep_recoverable`) for obligations left in `attempting` or `pending` states from the previous run.
- Replay unacknowledged messages to the target channel with a clear recovery prefix (`♻️ [Pesan terpulihkan — server sempat restart saat pengiriman]`), preventing silent drops of replies during host reboots, container updates, or unhandled exceptions.
- **Pitfall:** Fire-and-forget message dispatches without persistent state tracking permanently drop outgoing replies whenever the daemon restarts or crashes while waiting for LLM completion.

### 6. SQLite WAL Mode Concurrency & Checkpointing
- In multi-threaded agent runtimes where background task workers, web listeners, and model streaming consumers access SQLite concurrently, configure Write-Ahead Logging (`PRAGMA journal_mode = WAL;`) and busy timeouts (`PRAGMA busy_timeout = 15000;`).
- On server shutdown or clean daemon stops, execute `PRAGMA wal_checkpoint(TRUNCATE);` to flush WAL pages back into the main database file.
- **Pitfall:** Defaulting to standard rollback journaling causes `sqlite3.OperationalError: database is locked` crashes when background telemetry loggers write while turn runners read conversation history.

## Diagnostic Audit Checklist

1. **Partitioning Audit:** Are durable settings (API keys, bot tokens, biometrics) separated from ephemeral conversation logs during database maintenance?
2. **Safe Backup:** Are `.db`, `-wal`, and `-shm` files copied to a timestamped backup directory prior to executing schema updates or resets?
3. **Workspace Flagging:** Does the session manager check `"is_external": true` before treating a stored workspace path as an active user project folder?
4. **Canonical Keys:** Are incoming messaging sessions resolved strictly via unique `session_key` indexes rather than mutable `title` columns?
5. **Outbox Ledger:** Are outgoing channel dispatches tracked in a persistent delivery ledger and swept for recovery upon reboot?
6. **WAL Checkpointing:** Is SQLite configured with WAL mode and a 15-second busy timeout to prevent multi-threaded database lockouts?
