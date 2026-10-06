---
category: autonomous-ai-agents
name: agent-subagent-and-swarm-engineering
description: Use when designing subagents, swarms, worktrees, or MCP.
---

# Agent Subagent and Swarm Engineering

Use this skill when designing, implementing, auditing, or hardening multi-agent delegation pipelines, specialized swarm roles, Model Context Protocol (MCP) clients, ephemeral Git worktrees, and durable execution ledgers.

## 1. Multi-Agent Swarm Topology & Principle of Least Privilege

Never grant full, unconstrained toolsets to every delegated worker. Partition subagents into specialized roles with strict tool permission boundaries:

### Explorer / Reconnaissance Role (`role="explorer"`)
- **Permission:** Strictly read-only (`read_file`, `search_files`, `extract_code_outline`, `grep_search_code`).
- **Safety Gate:** Hard-block all mutating file modifications and shell execution commands that alter state.
- **System Prompt:** Instruct the worker to map the codebase, locate symbol definitions, extract structural outlines, and report factual file paths with `path:line` citations.
- **Pitfall:** Giving write or delete permissions to reconnaissance agents risks accidental file corruption or premature code edits during the exploration phase.

### Implementer / Coder Role (`role="implementer"`)
- **Permission:** Focused code mutation tools (`patch`, `write_file`, `read_file`, `extract_code_outline`).
- **System Prompt:** Instruct the worker to implement minimal, clean diffs adhering to existing codebase patterns, formatting, and invariants without unrequested refactoring.
- **Pitfall:** Unchecked implementers tend to rewrite surrounding working code or rename public interfaces, causing widespread regression.

### Verifier / Adversarial Gatekeeper Role (`role="verifier"`)
- **Permission:** Read-only inspection tools + deterministic test execution commands (`pytest`, `npm test`, `cargo test`).
- **Safety Gate:** Block direct file editing tools (`patch`, `write_file`).
- **System Prompt:** Instruct the worker to act as an adversarial reviewer. Never accept claims of success without real test runner execution output. Require explicit PASS/FAIL verdicts backed by execution logs.
- **Pitfall:** Allowing the verifier to edit files leads to circular self-certification, where failing tests are edited to pass rather than finding real code bugs.

---

## 2. Ephemeral Git Worktree Sandboxing

Isolate mutating missions and subagent experiments from the user's primary working tree:

- **Worktree Initialization & Stale Branch Cleanup:** When delegating a mutating task, create an isolated worktree under `.anara/worktrees/wt-<task_id>` on an ephemeral branch (`anara/wt-<task_id>`). Before invoking `git worktree add -b <branch>`, check if the branch name already exists in Git references when the worktree folder is absent from disk, and delete the stale ref (`git branch -D <branch>`). Otherwise, `git worktree add -b` fails with exit code 255 (`fatal: a branch named '...' already exists`).
- **Zero Dirty Workspace:** Execute all edits and test suites inside the worktree directory.
- **Affirmative Proof Pruning Rule:** Destructive cleanup (`git worktree remove --force` and `git branch -D`) requires affirmative proof that no uncommitted modifications or new commits exist. Both probes (`git status --porcelain` is empty AND `git rev-list --count <base>..HEAD == 0`) must exit with code 0. If either probe fails, times out, or encounters errors, enforce fail-safe retention: retain the directory and branch on disk for manual review.
- **Preserve Worktrees on Commit Failures:** In `apply_and_merge_worktree`, after attempting `git commit`, verify `git status --porcelain`. If uncommitted changes remain (e.g. commit failed due to missing author identity or pre-commit hook) and the branch diff against base is empty, DO NOT delete the worktree! Deleting the worktree folder when uncommitted files exist permanently destroys subagent modifications while falsely reporting success. Keep the worktree on disk and return failure for inspection.
- **Windows File Lock Pre-requisite:** Release active Language Server Protocol (LSP) and daemon process handles in the worktree directory before invoking `git worktree remove`. Windows enforces mandatory NTFS file locks on open files that cause worktree removal to fail with Access Denied.
- **Atomic Merge & Squash Conflict Recovery:** Only upon 100% test pass verification, squash-merge verified changes back to the primary workspace (`git merge --squash <branch>`). If a conflict occurs during squash merge, NEVER run `git merge --abort` — because `--squash` does not generate `MERGE_HEAD`, `git merge --abort` fails with `fatal: There is no merge to abort` and leaves the working tree corrupted with unmerged conflict markers. Recover using `git reset --merge`.
- **Pitfall:** Running `git merge --abort` on failed squash merges leaves the primary repository permanently tainted with conflict markers. Deleting a worktree after an empty diff without checking for failed commits permanently destroys subagent code changes. Stale branches left in Git refs cause worktree initialization to fail.

---

## 3. Native Model Context Protocol (MCP) Client Architecture

Connect agent runtimes dynamically to external tool servers (PostgreSQL, GitHub, Notion, Browser):

- **Wire Transport:** Implement standards-compliant JSON-RPC 2.0 over both `stdio` (subprocess pipes) and `http` (`httpx.AsyncClient`).
- **Handshake Sequence:**
  1. Client sends `initialize` (declaring protocol version, clientInfo, capabilities).
  2. Server responds with serverInfo and capabilities.
  3. Client sends notification `notifications/initialized`.
  4. Client queries `tools/list` to fetch tool schemas dynamically.
- **Host Environment Isolation:** When spawning stdio MCP subprocesses, NEVER pass the entire host `os.environ`. Scrub all API keys, access tokens, and cloud credentials. Pass only an approved OS baseline whitelist (`PATH`, `HOME`, `USER`, `SYSTEMROOT`, `COMSPEC`, `TEMP`) plus explicitly configured server-specific `env` variables.
- **Credential Scrubbing on Tool Output:** Pass all raw MCP stdout and stderr responses through credential regex redaction covering the full enterprise token spectrum (`AIza*` Google, `sk-ant-*` Anthropic, `sk-*` OpenAI, `ghp_*` and `github_pat_*` GitHub, bearer headers, and parameter keys).
- **Future Leak & Transport Resilience:** In stdio `_send_request`, wrap request future registration in `try...finally` *before* `stdin.drain()`. If `stdin.drain()` raises `BrokenPipeError` or `ConnectionResetError`, the future is guaranteed to be popped from `_pending_requests` rather than leaking in memory. Track and cancel background stderr drain tasks on `close()`, and on Windows execute `taskkill /PID /F /T` to prevent orphaned child processes.
- **Dynamic Tool Deregistration on Teardown:** When an MCP server disconnects or shuts down, deregister all its tools from the central `ToolRegistry` (`registry.unregister_tool(canonical_name)`) to prevent zombie tool calls in subsequent agent turns.
- **Tool Registry Bridge:** Register discovered MCP tools into the central tool registry using canonical names (`mcp_{server}_{tool}`).
- **Pitfall:** Blindly passing `os.environ` to external MCP servers exposes host API keys to untrusted packages. Failing to wrap `stdin.drain()` in `try...finally` leaks request futures permanently on broken subprocess pipes. Leaving disconnected tools in the registry causes subsequent turns to fail with unhandled transport exceptions.

---

## 4. AST Outline & Symbolic Code Navigation

Optimize LLM token consumption when exploring large codebases:

- **Structural Outlining:** Before loading a 500–2,000 line file into prompt context, parse its Abstract Syntax Tree (Python `ast.parse`) or regex symbol map (TypeScript, JavaScript, Go, Rust, Markdown).
- **Extracted Metadata:** Extract class names, method signatures (async/sync), parameter lists, line number ranges (`lines start-end`), and the first line of docstrings.
- **Token Efficiency:** A 2,000-line file (~10,000 tokens) compresses into a 50-line structural outline (~200 tokens). The agent inspects the outline and uses targeted `read_file` with precise `offset` and `limit`.
- **Pitfall:** Reading full large files for simple symbol lookups consumes 80%+ of the agent's turn context budget and triggers premature compaction.

---

## 5. Durable Background Cron & Execution Run Ledger

Maintain reliable 24/7 background task supervision:

- **Persistent Task Table:** Store scheduled tasks in SQLite with trigger type (`interval`, `cron`, `once`), interval seconds, target channel, and next run timestamp.
- **Execution Run Ledger:** Maintain a separate `autonomous_task_runs` table logging every execution attempt: `task_id`, `status` (`success`/`failed`), output summary, error message, and execution duration.
- **LIFO Timestamp Safety:** In SQLite, `created_at DATETIME DEFAULT CURRENT_TIMESTAMP` has 1-second resolution. Always sort historical runs by `ORDER BY rowid DESC` or `ORDER BY created_at DESC, rowid DESC` to prevent nondeterministic ordering of sub-second sequential runs.
- **Inspection Action (`runs`):** Expose `cronjob_manage(action='runs', task_id=...)` to let agents and users audit execution logs and failure backoffs.
- **Pitfall:** Storing only `last_run` timestamp on the task row destroys debugging audit trails when scheduled jobs intermittently fail.

---

## 6. Dynamic Multi-Provider Auto-Discovery & Capability Handshake

Avoid static vendor whitelists and hardcoded model parameters:

- **Declarative YAML Merging:** In addition to database/UI forms, parse custom providers from `config.yaml` (`model.custom_providers`) and `.env`. Seamlessly merge both sources with deduplication by `prefix`.
- **Dynamic Capability Handshake:** When querying `/v1/models` or catalog endpoints, inspect vendor metadata directly:
  - Multimodal Vision: Check `modalities` (`"image"`, `"vision"`), `architecture.modality` (`"text+image->text"`), or model family details (Ollama `clip`, `mllama`).
  - Audio / Realtime: Check for `"audio"`, `"voice"`, or `"bidi"` in methods.
  - Reasoning: Check for `"reasoning"` in capabilities or architecture.
- **Zero Whitelist Gating:** Never reject a model name because it is absent from an internal enum. If an endpoint returns the model or the user specifies it, dispatch it through the universal provider wire protocol.
- **Pitfall:** Hardcoding model names or static capability regexes prevents the agent from adopting newly released models without code deployments.

---

## 7. Native Codebase Sovereignty

- Maintain clean, self-contained project architecture and identity.
- Avoid littering production code with external vendor parity tags (e.g. `(Vendor Parity)`).
- Let the engineering patterns, schemas, and invariants stand on their own merit under the native project's architectural standards.

---

## 8. Multi-Agent Kanban Task Orchestration & CAS Concurrency Gates

Coordinate parallel swarm tasks across persistent kanban boards:

- **Atomic Status Transitions (CAS):** When autonomous subagents update task statuses (e.g. `todo` -> `in_progress` -> `review` -> `done`), enforce Compare-And-Swap (CAS) concurrency gates: `UPDATE kanban_tasks SET status = ?, review_notes = COALESCE(?, review_notes), updated_at = CURRENT_TIMESTAMP WHERE id = ? AND (? IS NULL OR status = ?)`.
- **Conflict Detection:** If rows updated == 0 when `expected_status` was provided, reject the transition with a structured conflict error (`conflict: true`) rather than blindly overwriting the state. This prevents an earlier slower worker from overwriting the review/done status set by an adversarial verifier.
- **HUD Projection Synchronization:** Emit visual telemetry events (`hud_project` with `type: "kanban_card"`) whenever a task is created or moved, keeping client dashboards synchronized in real time.
- **Pitfall:** Unchecked status updates without CAS allow a slow explorer or implementer to blindly overwrite the verdict of a verifier, corrupting the multi-agent task pipeline.

---

## 9. Multi-Bot Profile Isolation & Inter-Agent Messaging Protocol (`message_agent`)

When orchestrating multiple specialized agents across domains (e.g. `frontend` agent + `backend` agent):

- **Profile-Level Isolation:** Configure each specialized bot with its own independent profile under `profiles/<name>/` (`profile.yaml`, `config.yaml`, `SOUL.md`, memory, and skills). Never share a single bloated context window or mutate shared memory across distinct personas.
- **Canonical Bot Chat & Teammate DM Injection:** In Bot Mode sessions (e.g. canonical "Bot Chat"), inject an asynchronous peer messaging tool (`message_agent(target="<bot-name>", message="<text>")`):
  - **Fire-and-Forget Texting Semantics:** The caller composes an actionable message (never raw user dump), receives an immediate delivery acknowledgement, and completes its turn.
  - **Attribution & Delivery:** The messaging gateway prefixes caller attribution (`Message from <sender>: ...`), writes the payload to an isolated temporary queue, and launches a background runner into the recipient's session.
  - **Wake on Completion:** The target bot executes its turn independently, and its completion notification re-enters the caller's session to deliver the outcome or response.
- **Live Terminal Multiplexing:** When driving multiple live agents locally, run each instance in an isolated Git worktree (`-w`) inside terminal multiplexer sessions (e.g. `tmux new-session -d -s bot-fe 'anara -p frontend -w'`), capturing panes to relay structured interfaces.
- **Pitfall:** Attempting to force multi-bot collaboration through a single shared prompt causes context bloat, persona dilution, and toolset interference. Failing to isolate worktrees leads to git conflict crashes.
