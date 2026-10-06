---
category: autonomous-ai-agents
name: agent-runtime-engineering
description: Use when building or auditing AI agent loops and runtimes.
---

# Agent Runtime Engineering

Use this skill when auditing, designing, implementing, or hardening autonomous AI agent architectures, ReAct execution loops, subagent delegation frameworks, and tool execution engines.

## Core Architectural Invariants

### 1. Dynamic Reasoning Over Keyword Gating
- Rely on native model tool calling, JSON schema contracts, and semantic model classification rather than hardcoded string keywords, slang dictionaries, or artificial binary modes ("plan" vs "build").
- Never gate conversational intent or approval flows behind hardcoded token arrays (e.g. `AFFIRMATIVE_TOKENS = {"yes", "ok", "lanjut", "setuju"}`) or prefix checks (`clean.startswith(...)`). Natural conversation contains multilingual variations, negations (*"jangan lanjutkan"*), and conditional clauses. Route conversational approvals through auxiliary LLM semantic classification with cached verdicts (`_INTENT_CACHE`), reserving single-character tokens (`[y/N]`, `1/0`) strictly for non-conversational raw CLI machine prompts.
- Enforce permissions and safety at the tool execution boundary, not by stripping exploratory read tools or pre-empting the model's reasoning loop.
- **Pitfall:** Gating tool access or plan approvals via naive regex or keyword checks blinds the agent to user intent nuances and causes false-positive approvals on negated/conditional inputs or false refusals on benign phrases in other languages.

### 2. Persist-Before-Execute Durability
- Flush model tool call intentions and arguments to persistent storage (SQLite/WAL) *before* invoking tool dispatchers.
- Append tool results and observations to the database immediately upon execution completion.
- **Pitfall:** Logging conversations only at turn completion loses all intermediate tool actions and failure states if a process restarts, crashes, or is killed by an external command.

### 3. Negative Verification Stop-Gate & Test Execution Rigor
- Do not accept terminal narrative text from the model if verifiable code or configuration files were mutated during the turn without passing test/build evidence.
- Intercept the stop reason; if code was modified without fresh test execution, inject a synthetic verification nudge compelling the agent to run project verification commands before concluding.
- Verification command classification must strictly filter out file and directory inspection commands (`ls`, `dir`, `cat`, `head`, `tail`, `grep`, `find`). Do not match tests via generic keyword tokens (`test`, `check`, `spec`) without validating command intent; otherwise, running `ls tests` or `cat test.py` falsely satisfies the verification ledger.
- Never deduce test passage solely from exit code 0 when standard output lacks affirmative test runner indicators (e.g. `passed`, `ok`, `0 failed`) or contains unexecuted assertions.
- **Pitfall:** Naive substring matching on verification commands allows passive inspection tools (`ls tests`) to fool the stop gate, permitting code changes to exit unverified while falsely reporting success.

### 4. Subagent Headroom Budgeting & Disk Spilling
- Never return raw, unbounded subagent outputs directly into the parent model's prompt.
- Calculate dynamic summary budgets based on parent context headroom (e.g. 50% remaining context window divided by subagent count, capped at 24,000 characters).
- Snap head (75%) and tail (25%) slices to newline boundaries; persist complete uncompressed output to disk cache and provide a paging retrieval hint (`read_file`).
- **Pitfall:** Unbounded subagent responses cause instant parent context blowout and HTTP 429/413 errors when multiple subagents run concurrently.

### 5. Atomic Task Claiming & Crash Resiliency
- In background task schedulers and cron daemons, claim due tasks using atomic conditional updates (`UPDATE tasks SET status='running' WHERE id=? AND status IN ('idle', 'failed') AND next_run <= ?`).
- On daemon startup, recover stale `running` tasks back to `idle` so crashed tasks do not become permanent zombies.
- **Pitfall:** Querying tasks via `SELECT` and later setting `status='running'` causes race conditions and duplicate concurrent runs in multi-worker environments.

### 6. Leased Session Locks & Reentrant Deadlock Immunity
- Apply reentrant asyncio locks to session turns with explicit lease timeouts (e.g. 300s) to prevent permanent deadlocks if an async worker hangs.
- When acquiring underlying mutexes (`_lock.acquire()`), always wrap acquisition in bounded timeout waits (`asyncio.wait_for(timeout=lease_timeout)`). If an acquisition times out, break the stale lease, reset task ownership, and force lease takeover instead of suspending waiting coroutines indefinitely.
- Never use destructive `git reset --hard HEAD~1` as an automated rollback fallback; use `git revert --abort` to keep the working tree clean without wiping uncommitted work.
- **Pitfall:** Unbounded waits on `asyncio.Lock.acquire()` cause permanent lock starvation across the entire session if an in-flight worker hangs or encounters an unhandled exception before releasing the lock.

### 7. Channel Anti-Leak Gating & Interrupt Lock Bypass
- When an LLM leaks raw unexecuted tool markup (`<tool_call>` or `{"action": "tool_call"}`), scrub it and check risk before execution. Never auto-dispatch mutating tools unvetted; route mutating calls into a pending proposal state requiring explicit human confirmation. Harmless read-only calls can execute directly.
- User `/stop`, `/cancel`, or interrupt signals must NEVER wait on the active turn's session lock. Bypass turn locks immediately for interrupt routing so hanging workers can be cleanly halted.
- **Pitfall:** Waiting on the session lock for `/stop` causes an unrecoverable deadlock when the turn itself is blocked in an infinite tool cycle or hanging network socket.

### 8. Idempotent Provider Key Rotation & Concurrency Protection
- Provider key management must be thread/async-safe (`threading.Lock`).
- Pure read calls (`get_active_key()`) must be strictly idempotent and must NOT rotate keys as a side effect.
- In single-key deployments, provide multi-attempt exponential backoff on transient quota/overload errors (429/503) instead of failing immediately.

### 9. Semantic Code-Fence Streaming Chunking
- When chunking long agent outputs for multi-channel egress (Telegram, WhatsApp, Slack, Discord), inspect open markdown code blocks (` ``` `).
- If a chunk cuts through a code fence, append a closing fence (` ``` `) to the current chunk and re-open the next chunk with the exact language specifier (` ```python `) from the last active fence.

### 10. Indivisible Tool-Call / Tool-Result Compaction Boundaries
- When performing mid-turn context compaction or summarizing earlier history, never slice between an assistant turn emitting `tool_calls` and the subsequent `tool` / `tool_result` messages.
- Both Anthropic (`invalid_request_error: tool_use_id not found`) and OpenAI strictly require that every `tool` response is immediately preceded by the assistant turn that called it, and every emitted tool call has a corresponding result.
- Snap compaction slice points to an index where the tail does NOT begin with a tool result (`role in ('tool', 'function')` or `function_response`).
- **Pitfall:** Slicing history at an arbitrary offset (e.g. `history[-4:]`) relegates the assistant tool call to the summarized middle while leaving its result in the tail, causing instant HTTP 400 rejection from modern API gateways.

### 11. Stateful Streaming Think Scrubber
- Do not rely on stateless regexes per chunk delta to strip reasoning tokens (`<think>`, `<thought>`, `<thinking>`).
- A chunk delta can split opening/closing tags or deliver thought monologues across hundreds of deltas without inline tags.
- Implement a stateful streaming scrubber that buffers tag prefixes across chunk boundaries, tracks block depth, supports multilingual thinking tags (`think`, `thought`, `reasoning`, `thinking`, `思考`, `反思`, `推理`, `推敲`), and flushes only sanitized narrative prose to the user interface.
- **Pitfall:** Applying `re.sub(r'<think>.*?</think>', '', delta)` per chunk matches the opening tag in delta 0, but lets all subsequent deltas bypass the regex, streaming internal model reasoning directly to the user UI.

### 12. Non-Destructive Multi-Tool Stall Handling
- In native multi-tool turns, when a loop-breaker or stall-guard trips on tool $i$, do NOT truncate `parsed_calls` to only that single tool.
- The assistant turn in provider history already emitted $N$ tool calls; truncating execution to 1 tool result violates the API protocol and triggers fatal HTTP 400 errors on subsequent turns.
- Append a structured error message (`[LOOP BREAKER INTERVENTION]: ...`) for the stalled tool and continue parsing the remaining tools so every emitted `tool_call_id` receives a valid response.

### 13. Atomic File Memory & Configuration Swaps
- When persisting agent memory files (`MEMORY.md`, `USER.md`, `SOUL.md`), configuration files, or state manifests, never use plain `open(path, "w")`.
- Plain `open(..., "w")` immediately truncates the file to 0 bytes (`O_TRUNC`); a process crash, interrupt, or power loss before flushing permanently corrupts the file.
- Write to a unique temporary file (`.tmp_*`) in the same directory, call `flush()`, invoke `os.fsync(fileno)` to force physical disk sync, and perform an atomic swap via `os.replace`.
- **Pitfall:** Unbuffered `open("w")` on memory files causes irreversible 0-byte memory loss whenever an agent process is killed or interrupted mid-turn.

### 14. SQLite Connection Lifecycle & Pragmas Enforcement
- Every runtime SQLite connection must execute `PRAGMA foreign_keys = ON;`, `PRAGMA synchronous = NORMAL;`, and `PRAGMA busy_timeout = 15000;`. In SQLite, foreign key cascades (`ON DELETE CASCADE`) are disabled by default per connection unless explicitly enabled.
- In Python `sqlite3`, `with sqlite3.connect(...) as conn:` manages transaction commit/rollback, but does NOT close the underlying connection handle. Wrap all SQLite connections in a context manager that guarantees `conn.close()` inside a `finally` block.
- **Pitfall:** Omitting connection closure leaks OS file descriptors on every query, eventually causing `sqlite3.OperationalError: database is locked` on Windows due to file lock contention.

### 15. Zero Heuristic Content Filtering in Session History
- Never filter or drop conversation history turns based on heuristic string inspections of user text (such as dropping messages starting with `{` and containing `"type"`).
- Legitimate user prompts frequently contain JSON schemas, API specs, GraphQL queries, or debug payloads. Heuristic filtering silently discards real user messages from the conversation history.
- Isolate internal system control frames or synthetic agent prompts via explicit database metadata columns (`is_internal = 1`), preserving user messages verbatim.

### 16. Dynamic Multi-Provider Resolution & Zero Model Lock-In
- Never hardcode vendor-specific model strings (e.g. `"gemini-2.5-flash"`, `"gpt-4o"`, `"claude-3-5-sonnet-20241022"`) as fallback literals inside auxiliary functions (STT, audio synthesis, visual HUD, auto-title generation).
- Route auxiliary calls through capability-based resolvers (`get_fast_auxiliary_model()`, `ProfileRegistry`, or `call_universal_chat_model`) that query the active user configuration and fall back across healthy registered providers.
- Maintain separate handling for API-specific model identifiers versus internal proxy aliases: never send unverified or forward-looking speculative model names to vendor SDKs without dynamic discovery validation.
- Avoid date-stamped model snapshots (e.g. `20241022`) in fallback payloads: resolve against the user's active model family (`get_active_model_id()`) or canonical vendor aliases without locking the user out of newer releases (such as Claude 3.7 Sonnet).
- Build tiered multimodal cascades: when implementing vision, STT, or TTS tools, never assume the user has a specific vendor's API key (such as Google or OpenAI). Support multi-provider fallback checking (1) active custom/local providers, (2) the user's active provider, and (3) universal chat completions, allowing the platform to run 100% on any single provider key (Anthropic-only, OpenAI-only, or Ollama-only).
- **Pitfall:** Hardcoding proprietary model names or dated snapshots in fallback handlers causes fatal HTTP 404 errors on upstream APIs when the vendor lacks that exact string, or complete feature failure if the user operates without that vendor's API key.

### 17. Conversational Mode Separation & Forced Conclusion Tool-Stripping
- Clearly separate conversational interaction modes from mutating build/engineer modes. Do not default every turn to a tool-demanding build mode (`mode="build"`). In conversational mode, instruct the model to respond directly in natural language to inquiries and status checks without calling tools.
- When an agent execution loop triggers loop-breaker convergence, timeout, or stall mitigation, the final closing pass (`closing_narrative`) MUST strip tool definitions from the model payload (`tools=None` or `tool_choice="none"`).
- Provide robust non-empty fallback synthesis: if all executed turns in the loop were tool calls without narrative prose, synthesize a coherent completion summary from the executed tool results rather than emitting an empty turn error.
- **Pitfall:** Leaving tools active during a forced convergence/closing pass invites the model to emit yet another tool call instead of narrative text. When that occurs at the turn limit without generating text, caller routines fall through to empty-turn notices ("No response was generated for this turn").

### 18. Cross-Process OS-Level File Locks & Memory Ambiguity Guards
- Multi-process agent architectures (background daemons, CLI runners, and web APIs sharing the same `USER.md` or `MEMORY.md`) cannot rely on thread locks (`threading.RLock`) alone. Thread locks only synchronize threads within the same Python process.
- Implement kernel-level file locking on an auxiliary `.lock` file (`msvcrt.locking` on Windows, `fcntl.flock` on POSIX) surrounding read-modify-write cycles.
- When performing memory updates or deletions via substring needles, check match cardinality: if a needle matches multiple lines, abort with a structured ambiguity error rather than mutating the wrong entry.
- **Pitfall:** Using intra-process `RLock` for shared agent memory files causes race conditions and file clobbering when CLI sessions and background daemon workers access memory concurrently.

### 19. Dynamic Schema Contract Coercion at Registry Dispatch
- LLM tool calling frequently produces stringified primitives (e.g. `"true"` for boolean fields, `"42"` for integer fields, or stringified JSON for arrays and objects).
- Perform dynamic schema coercion at the tool registry layer prior to handler dispatch, inspecting the tool's declared JSON schema `properties` and converting types safely.
- If required parameters are missing or non-nullable, return a structured error with the missing keys and schema property list instead of letting Python throw unhandled `TypeError` or `KeyError` exceptions.
- **Pitfall:** Dispatching raw LLM argument dictionaries without schema coercion causes runtime crashes on typed handlers, or triggers uninformative error messages that prevent the LLM from self-correcting.

### 20. Git Worktree Merge Collision Preservation & Clean Abort
- When subagents perform isolated work in git worktrees and squash-merge changes back into the main workspace (`git merge --squash`), merge conflicts may arise.
- If the merge fails, run `git reset --merge` on the main workspace immediately. In Git, `--squash` does NOT produce a `MERGE_HEAD`, so calling `git merge --abort` fails with `fatal: There is no merge to abort` and leaves conflicting status markers (`UU`). Use `git reset --merge` to cleanly clear the conflicting index.
- Never delete the worktree or the working branch on merge conflict: preserve both on disk so the developer or agent can inspect the conflict and salvage code changes.
- **Pitfall:** Silently deleting the worktree after a failed merge squash destroys all work generated by the subagent without giving the user a chance to resolve the conflict.

### 21. Pure Project-Native Branding & Commit Hygiene
- In private or customized agent orchestrator codebases, never leak upstream framework names or competitor tool branding in git commit titles, commit messages, or internal code comments.
- Enforce project-native naming conventions (e.g. `[PROJECT] Standard`, `[PROJECT] Autonomous Parity`) across all codebases and internal documentation.
- Never execute direct remote pushes (`git push`) without explicit user review and directive; maintain all verified changes on the local branch first.
- **Pitfall:** Leaking upstream agent brand names in commit logs or code diffs creates repository confusion, violates project identity invariants, and leaks development scaffolding into production history.

### 22. Strict Tool-Use Enforcement & Anti-Roleplay Stop-Gate (Anara Parity)
- In conversational channels (Telegram, WhatsApp, Slack, Web), models frequently lapse into narrative roleplay when executing mutating tasks, printing simulated action strings in asterisks or parentheses (e.g. `*(Ngeksekusi perintah...)*` or `*(Closing application...)*`) instead of issuing valid tool calls.
- Inject strict `TOOL_USE_ENFORCEMENT_GUIDANCE` and `TASK_COMPLETION_GUIDANCE` across all platform prompts: models must never describe an action without executing it, must never end a turn with unexecuted promises of action, and must never fabricate simulated execution.
- Implement an Anti-Fabrication Stop-Gate in both native and text agent loops: detect simulated action narration emitted with 0 tool calls, intercept the turn completion, and inject an immediate synthetic user nudge compelling the model to invoke the actual tool or report an authentic blocker.
- **Pitfall:** Accepting narrative text with 0 tool calls as a successful turn when the user asked for a physical action tricks the user into believing tasks succeeded while background processes remain running and files remain untouched.

### 23. Fail-Fast Diagnostic Recovery Over Silent Degradation
- Never silently catch API or tool protocol errors (such as HTTP 4xx client errors, missing auth, or missing protocol signatures like `thought_signature`) to downgrade to dumb text ReAct loops where small/lite models hallucinate pretend execution.
- Multi-turn thinking models (such as Gemini 2.5/3.x with reasoning) produce encrypted reasoning snapshots (`thought_signature`) on function calls in native SDKs; if the runtime does not roundtrip these signatures identically on the subsequent turn, the API rejects the request with HTTP 400. Routing such models through OpenAI-compatible proxies (e.g. 9Router) avoids SDK signature validation bottlenecks.
- If a provider is unreachable (e.g. connection refused on local gateway port), fail fast and emit clear diagnostic telemetry warnings (`status="warning"`) to the UI/channel before engaging fallback ladders.
- If both primary and fallback providers fail, raise a transparent error citing both failure reasons rather than masking the root cause behind generic fallback crashes.
- **Pitfall:** Silently catching provider or tool errors and degrading to low-parameter fallback models in conversational mode causes the model to abandon structured tool execution entirely and fabricate plausible-looking conversational responses.

### 24. Administrative Tool Parity, Anti-Hunt Scoping, and Resilient Closing Fallback
- Provide native model tools for administrative environment actions (such as `switch_workspace`, `set_model`, or `session_config`) rather than restricting them exclusively to CLI slash commands. When users make natural-language requests (e.g. *"ganti workspace ke Downloads"* or *"C: download"*), an agent lacking a dedicated tool enters a runaway **Architectural Hunt Loop** — scanning internal runtime source code, inspecting command routers, and attempting rogue database mutations via CLI commands until exhausting the loop step budget.
- Implement fuzzy path resolution on workspace and file tools: normalize ambiguous Windows/POSIX inputs (e.g. `"C: download"`, `"~/Downloads"`, `"downloads"`) to canonical absolute user directory paths.
- Enforce **Bounded System Scope & Zero Lazy Delegation**:
  - Prohibit agents in operational guidelines from grepping or modifying the runtime's own internal architecture or database files when answering user tasks, restricting self-inspection strictly to explicit development/debugging prompts.
  - When a user asks to perform an action (e.g. *"ganti direktori kerja lu ke download"*), the agent **MUST directly execute the corresponding tool** (`switch_workspace`). Never instruct the user to copy-paste or manually run slash commands (`/workspace <path>`) when the agent has the tool to perform the action autonomously.
- **Single-Source Posture Toolset Synchronization**:
  - When filtering or pruning tools per platform/posture (e.g. `PlatformToolRegistry.get_pruned_tools_for_execution`), never initialize active tools from an isolated hardcoded set (such as `CODING_TOOLS`) that diverges from `CORE_TOOLS`. Ensure newly registered administrative and file tools are present in all baseline posture sets; otherwise, tools exist in specifications but are silently stripped from chat channels.
- **Prompt Snapshot State Synchronization**:
  - When an environment tool mutates active session state (such as switching the workspace folder), it must immediately update both in-memory session tracking (`_session_active_paths`) and database persistence (`chat_sessions.workspace_info_json`). The subsequent turn's prompt assembler must immediately read this updated state so when the user asks "where is our workspace?", the model reflects the ground-truth updated location without requiring session resets.
- When the tool iteration budget is exhausted or a closing pass is triggered on an unclosed tool call, **compact the closing pass context** (preserve developer prompt and recent observations) to prevent token window overflow. If closing narrative synthesis fails, never emit a blank/empty turn notice ("No response was generated"); extract recent tool execution observations and deliver a transparent factual summary of completed actions.
- **Pitfall:** Missing native tools for common environment operations causes agents to spend 25+ tool steps hacking their own database, resulting in context blowout, failed closing passes, and cryptic "No response was generated" errors. Furthermore, omitting tools from posture sets leads the agent to lazily tell users to copy-paste slash commands instead of acting autonomously.

### 25. Systematic 5-File Batch Orchestrator Auditing & Cross-Architecture Benchmark
- When conducting an enterprise agent orchestrator audit or refactor, structure work strictly into sequential 5-file/folder batches to maintain deep forensic focus and avoid context truncation.
- For each batch, establish a ground-truth factual baseline by comparing directly against proven reference architectures (e.g. Anara production engine and Anara Coding Agent query/coordinator patterns).
- Dispatch parallel subagents (`delegate_task`) for isolated forensic autopsies: one subagent inspecting reference repositories and another dissecting target implementation files line-by-line. Never make speculative claims or conclusions without verified line numbers and executed tool proof.
- Enforce pure dynamic LLM reasoning and schema contracts: ruthlessly eliminate hardcoded keyword gates, static slang token arrays, and artificial mode locks.
- Maintain all changes strictly on local branches or worktrees; never execute `git push` without explicit user review.
- **Pitfall:** Conducting broad, unbatched reviews across dozens of files results in superficial analysis that overlooks hidden keyword gates, brittle schema contracts, and subtle state leaks between agent components.

### 26. Dynamic Reasoning Effort Monotonic Step-Down Clamping
- When normalizing user reasoning effort across heterogeneous model providers (OpenAI, Anthropic, Gemini, DeepSeek), preserve standard ladder tiers (`EFFORT_LADDER = ["none", "low", "medium", "high", "max"]`) before evaluating alias dictionaries.
- If a provider's allowed set does not support the requested tier (e.g. requesting `"max"` on a provider that only supports `["low", "medium", "high"]`), monotonically step down to the nearest lower supported tier (`"high"`) instead of dropping to the default index 0 (`"low"`).
- **Pitfall:** Relying solely on alias maps causes valid higher ladder tiers to evaluate as undefined aliases, collapsing `"max"` down to the weakest allowed tier (`"low"`).

### 27. Fixed-Width Regex Lookbehinds & Scoped Credential Masking
- In standard regex engines (Python `re`), lookbehinds require strictly fixed-width patterns. Variable-width lookbehind patterns (e.g. `(?<=[?&]|\b--|\b-)`) throw fatal compilation errors (`re.PatternError: look-behind requires fixed-width pattern`).
- When masking secrets in query parameters or CLI arguments, strictly anchor patterns to URL parameter delimiters (`(?<=[?&])(token=|api_key=|key=|password=)`) or dedicated option prefixes (`\b(api_key=|password=)`).
- Never match bare unanchored assignment substrings like `key=[^&\s]+`, which aggressively corrupts standard code kwargs (`key=item_name`, `key=lambda x: x`) into `key=[REDACTED]`.
- **Pitfall:** Unanchored key scrubbing destroys legitimate application code and debugging logs containing common keyword arguments.

### 28. Canonical Session Key Regex End-Anchoring
- Regex patterns validating session identifiers or persistent keys must explicitly include an end-of-string anchor (`\Z` or `$`).
- Validating solely on prefix patterns (e.g. `^\d{8}_\d{6}_[a-f0-9]{6}`) allows path traversal payloads (e.g. `<key>/../../evil`) or SQL injection fragments to pass validation.
- **Pitfall:** Omitting `\Z` on session key validation allows malicious filesystem path traversal and database injection attacks to bypass validation checks.

### 29. Recursive Protobuf Unpacking for Native Function Calling
- Native provider SDKs (such as Google GenAI) return tool call arguments as SDK-specific composite structures (`MapComposite`, `RepeatedCompositeContainer`).
- A shallow `dict(fc.args)` only converts top-level keys. Furthermore, checking `isinstance(obj, (list, tuple))` fails on `RepeatedCompositeContainer` (used when tools accept arrays of objects/structs) because protobuf repeated containers do not inherit from `list` or `tuple`, leaving raw protobuf objects inside tool arguments and causing downstream JSON serialization crashes (`TypeError: Object of type RepeatedCompositeContainer is not JSON serializable`).
- Recursively unpack tool arguments (`_deep_to_dict`) using `collections.abc.Mapping` and `isinstance(obj, collections.abc.Sequence) and not isinstance(obj, (str, bytes))` to guarantee that all nested dictionaries, objects, and repeated sequences are converted into native Python `dict` and `list` primitives before registry dispatch.
- **Pitfall:** Shallow dictionary conversion or naive `(list, tuple)` checks on SDK tool arguments leave nested protobuf repeated containers unconverted, crashing downstream JSON serializers and typed tool handlers.

### 30. Provider Prefix Exclusion & Proxy Model Hijacking Defense
- When specialized vendor provider profiles evaluate model eligibility (`can_handle(model_id)`), never match solely on broad generic substrings (e.g. `"gemini" in clean` or `clean.startswith("models/")`) without explicitly excluding third-party proxy prefixes (`ag/`, `9router/`, `openrouter/`, `groq/`, `deepseek/`, `xai/`).
- If a vendor profile hijacks a proxy model (e.g. `ag/gemini-3.8-flash-high`), requests are erroneously dispatched to the vendor's official cloud endpoints rather than the local gateway proxy, triggering fatal HTTP 404/401 errors.
- Inside provider profiles, active credential retrieval must filter enabled accounts (`is_enabled == 1`) and healthy cooldown states (`cooldown_until <= now`), rather than naively grabbing the first account index.
- **Pitfall:** Broad substring matching in vendor profiles hijacks local proxy and router models, routing them to vendor cloud endpoints where the model name does not exist.

### 31. Module-Level Attribute Delegation (PEP 562) for Singleton Modules
- In Python package namespaces, importing a submodule (e.g. `import core.key_manager`) binds `core.key_manager` on the parent package to the *module* object itself, shadowing any singleton instance with the same name.
- Implement module-level `__getattr__(name: str)` in the submodule (PEP 562) to transparently forward instance attribute lookups (`total_keys`, `execute_with_failover`, `get_active_key`) to the underlying singleton instance.
- This ensures both `from core.key_manager import key_manager` and `from core import key_manager` (as a module) function identically without throwing `AttributeError`.
- **Pitfall:** Omitting PEP 562 attribute forwarding causes singleton instance methods and attributes to be missing when callers import the submodule through the parent package.

### 32. Hybrid Dual-Identity Session Key Resolution
- In architectures supporting both integer SQLite database IDs (for frontend stability) and canonical string session keys (`YYYYMMDD_HHMMSS_<hex>`), all mutation and deletion methods (`set_workspace_info`, `set_pending_plan`, `attach_visual`, `delete_session`) must resolve keys through a canonical hybrid resolver (`_resolve_session_id`).
- Direct SQL lookups (`WHERE id = ?` or `WHERE session_id = ?`) fail when passed canonical string keys from REST endpoints, dropping workspace updates or causing foreign key cascading delete orphan leaks in secondary tables (`project_adr`, `app_settings`).
- **Pitfall:** Bypassing hybrid key resolution causes REST endpoints using canonical string keys to fail silently or leave orphaned data in secondary tables.

### 33. Multi-Strategy Fuzzy File Patching & Universal Newline Invariance
- Never rely exclusively on exact substring matching (`old_string in content`) for in-place file editing tools.
- On Windows or mixed-platform codebases, line endings frequently differ (CRLF `\r\n` vs LF `\n`), causing exact matches to fail 100% of the time.
- Implement multi-tier fuzzy replacement: (1) exact match, (2) universal newline normalization (`\r\n` <-> `\n`) while preserving the file's original line endings, and (3) trailing-whitespace normalized sliding-window line matching.
- Generate standard unified diffs (`difflib.unified_diff`) instead of naive line loops, and perform file writes via atomic tempfile replacement (`.tmp_*` in the same directory, `f.flush()`, `os.fsync()`, `os.replace()`) to prevent 0-byte file truncation on interruption.
- **Pitfall:** Exact substring patching fails on platform line ending differences, while non-atomic writes truncate files to 0 bytes if a process crashes mid-edit.

### 34. Tool Registry Thread-Safe Mutation & RLock Snapshot Copying
- Dynamic tool registries accessed by concurrent workers or subagents must protect all registration and lookup methods with a reentrant lock (`threading.RLock`).
- When serializing declarations or tool catalogs (`get_all_declarations`, `get_tools_catalog`), iterate over shallow copies of dictionary items (`list(self._tools.items())`) within the lock rather than iterating the live dictionary.
- **Pitfall:** Mutating or registering tools dynamically while concurrent turns query tool declarations causes fatal `RuntimeError: dictionary changed size during iteration`.

### 35. Windows OpenBLAS & NumPy Virtual Memory Thread Pool Clamping
- On Windows hosts executing audio STT/SER, vision inspection, or tensor computations, NumPy's underlying OpenBLAS engine dynamically attempts to allocate large thread pools per virtual core, exhausting system memory tables and crashing with `OpenBLAS error: Memory allocation still failed after 10 retries, giving up`.
- Always clamp thread pools at the earliest bootstrap boundary before importing NumPy: `os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")` and `os.environ.setdefault("OMP_NUM_THREADS", "1")`.
- **Pitfall:** Importing NumPy without OpenBLAS thread clamping on Windows causes test suites and audio pipelines to abort with uncatchable OpenBLAS C-level memory allocation failures.

### 36. PowerShell Terminal Execution via Base64 `-EncodedCommand`
- In agent runtimes executing user or generated shell commands via PowerShell on Windows, string-interpolating commands into `-Command "[Console]::OutputEncoding = ...; {cmd}"` corrupts quotes (e.g. `git commit -m "feat: msg"`), breaks on PowerShell variables (`$var`), and permits syntax injection.
- Convert the command to UTF-16LE bytes, Base64-encode it, and invoke `powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -EncodedCommand <base64>`. This guarantees 100% quotation, punctuation, and newline preservation without escaping errors.
- **Pitfall:** Raw string interpolation into PowerShell `-Command` strips inner quotes or chokes on backticks and dollar signs, breaking standard git and package manager commands.

### 37. Terminal UI Stream Decoupling & Prompt Toolkit Tearing Prevention
- In terminal CLI platforms using `prompt_toolkit.PromptSession` for interactive REPL loops, background events, subagent progress spinners, and token streams write directly to stdout, corrupting the active prompt and duplicating the cursor.
- Wrap prompt ingestion in `prompt_toolkit.patch_stdout.patch_stdout()`.
- Stream renderers must be idempotent and guaranteed to close framing (`finish()`) inside `finally:` blocks and prior to interactive plan approval gates, preventing leaked open UI boxes or torn frames on subsequent turns.
- When parsing terminal UI arguments or diffs with Rich, always escape file paths and dynamic labels with `rich.markup.escape()` to prevent bracketed paths (e.g. Next.js `app/[id]/page.tsx`) from being stripped or throwing `MarkupError`.
- **Pitfall:** Omitting `patch_stdout` results in terminal prompt tearing when background agent events arrive, while unescaped brackets in file paths corrupt Rich UI panels.

### 38. Async Non-Blocking Route Handlers & Thread Offloading Invariant
- In FastAPI or async web frameworks, synchronous I/O operations (SQLite queries, `subprocess.run`, file system traversals, synchronous third-party SDK calls) inside `async def` routes block the entire asyncio event loop.
- Offload all blocking calls to worker threads via `await asyncio.to_thread(...)`. Calling `await` directly on synchronous non-coroutine functions raises fatal `TypeError: object bool can't be used in 'await' expression`.
- **Starlette `BaseHTTPMiddleware` + WebSocket Deadlock:** `BaseHTTPMiddleware` wraps each request in `run_in_threadpool(self.dispatch, ...)`. With active WebSocket connections holding thread pool slots, new HTTP requests starve and timeout indefinitely. Replace `BaseHTTPMiddleware` subclasses with pure ASGI middleware (`__call__` pattern) that passes WebSocket/lifespan scope through and only intercepts `http.response.start` for header injection.
- **SQLite `busy_timeout` in async context:** Setting `sqlite3.connect(timeout=15)` or `PRAGMA busy_timeout=15000` inside an `async def` handler (even via `asyncio.to_thread`) blocks the calling coroutine for up to 15 seconds when the DB is locked by another process (e.g., Telegram daemon). Use short timeouts (2s) in async contexts and retry at the application layer instead.
- **Git subprocess CRLF spam on Windows:** `subprocess.run(["git", ...])` emits CRLF conversion warnings on Windows that flood stdout. Pass `-c core.safecrlf=false` and `env={"GIT_TERMINAL_PROMPT": "0"}` to suppress warnings that would otherwise stall or bloat output.
- **Pitfall:** Blocking the main event loop in an async web service freezes real-time WebSocket heartbeats and triggers client timeouts across all connected sessions. The `BaseHTTPMiddleware` deadlock is especially insidious because the first HTTP request succeeds (filling the last thread pool slot), then all subsequent requests hang silently.

### 39. Server-Sent Events (SSE) & WebSocket Lifecycle Shielding Invariant
- Long-lived streaming connections (SSE telemetry, WebSocket turn pumps) must implement periodic keepalive pulses (e.g. `: keepalive <timestamp>\n\n` comments every 15s) to prevent intermediate reverse proxies (Cloudflare, NGINX, AWS ALB) from abruptly dropping idle streams.
- When supervising concurrent read/write coroutines on WebSockets via `asyncio.wait(..., return_when=FIRST_COMPLETED)`, wrap the teardown in a `finally:` block that cancels and drains lingering background tasks. Never leave send pumps hanging on `queue.get()`, which crash with `RuntimeError: Cannot call "send" once a close message has been sent` when downstream events arrive on a closed socket.
- Safely serialize non-primitive telemetry payloads with recursive conversion or `default=str` to prevent unexpected types (UUID, datetimes, custom exceptions) from terminating streaming pipelines with unhandled `TypeError`s.

### 40. SSRF & DNS Rebinding Egress Defense on Web & Webhook Tooling
- Validating URLs solely with `url.startswith("http")` is an existential SSRF vulnerability. Outbound web fetchers, media downloaders, and webhook dispatchers must resolve the destination hostname to IP addresses via non-blocking DNS lookups (`loop.getaddrinfo`), validating resolved IPs against private subnets (RFC 1918), loopback (`127.0.0.1`), link-local/cloud metadata (`169.254.169.254`, `169.254.170.2`, `metadata.google.internal`), multicast, unspecified (`0.0.0.0`), and CGNAT (`100.64.0.0/10`).
- In HTTP clients supporting redirects (`follow_redirects=True`), attach redirect event hooks (`event_hooks={"response": [_check_redirect]}`) to inspect the `Location` header on every hop. An external URL can easily redirect an unsuspecting agent into internal infrastructure.

### 41. Universal Hybrid Session Key Typing in Web API Schemas (`Union[int, str]`)
- In architectures supporting both integer SQLite database IDs (for frontend stability) and canonical string session keys (`YYYYMMDD_HHMMSS_<hex>`), never type API request models or route query parameters as `session_id: Optional[int] = None`.
- When clients pass canonical session keys, FastAPI immediately rejects requests with `422 Unprocessable Entity: value is not a valid integer`.
- Type all session parameters as `Optional[Union[int, str]] = None` and resolve via the canonical hybrid ID resolver (`_resolve_session_id`).
- **Pitfall:** Typing `session_id: Optional[int]` in REST schemas breaks API interoperability for any client or worktree runner passing canonical session strings.

### 42. Model-Aware Reasoning Parameter Translation (HTTP 400 Prevention)
- When generating reasoning effort or thinking configurations (e.g. `reasoning_effort` for OpenAI, `thinking` for Anthropic), always verify that the target model actually supports extended reasoning before injecting payload parameters.
- Standard conversational chat models (e.g. `gpt-4o`, `gpt-4o-mini`, `claude-3-5-sonnet`) do not accept thinking parameters and reject requests with fatal HTTP 400 Bad Request errors.
- Conditionally omit reasoning blocks (`return {}`) when target models lack reasoning capabilities.
- **Pitfall:** Unconditionally injecting thinking parameters across all models causes API gateways to reject standard chat models with HTTP 400 errors.

### 43. PowerShell User PATH Null-Coalescing Guard
- When permanently appending directories to Windows User Environment PATH (`[Environment]::GetEnvironmentVariable('Path', 'User')`), if the variable is unset or empty, PowerShell returns `$null`.
- Calling `.TrimEnd(';')` on `$null` triggers a fatal `NullReferenceException`.
- Always guard with null-coalescing logic: `$old = if ($old) { $old } else { '' }`.
- **Pitfall:** Unchecked `.TrimEnd(';')` calls in PowerShell user path setup scripts crash on fresh Windows user profiles with uninitialized PATH variables.

### 44. POSIX Path Normalization in Windows Git Bash CLI Shims
- When authoring POSIX wrapper scripts (`anara`) for Windows CLI tools, convert Windows drive paths (`C:/...` or `C:\...`) to POSIX mount paths (`/c/...`) for BOTH the python interpreter executable AND the target entrypoint script.
- Converting only the python binary while leaving the target script as `C:/...` causes script resolution failures in strict MSYS2 / Git Bash environments where path translation is disabled.
- **Pitfall:** Incomplete path conversion in shell shims leaves target scripts formatted with Windows drive letters, causing `No such file or directory` errors under Git Bash.

### 45. Longest-Prefix Token Pricing & Rate Matching Invariance
- In token usage accounting and cost estimation modules matching model IDs against pricing tables (`MODEL_PRICE_PER_M`), never iterate pattern dictionaries in arbitrary insertion order.
- Shorter model prefixes (e.g. `"gpt-4o"`) that appear before longer, more specific model variants (e.g. `"gpt-4o-mini"`) collide during substring checks (`pattern in model_id`), falsely matching the expensive model rate ($2.50/$10.00) instead of the lighter rate ($0.15/$0.60) and inflating cost calculations by over 1600%.
- Sort rate dictionary patterns descending by pattern length (`sorted(rates.items(), key=lambda x: len(x[0]), reverse=True)`) so the longest, most specific model identifier is evaluated first before falling back to shorter base models or default tiers.
- **Pitfall:** Iterating pricing tables without length-descending sorting causes shorter model prefixes to match before longer variants, drastically distorting token cost accounting.

### 46. Case-Insensitive Dynamic Schema Type Coercion at Registry Dispatch
- When performing dynamic schema coercion on LLM tool call arguments (converting stringified `"true"` to `bool`, `"10"` to `int`, or stringified JSON to `dict`/`list`), always normalize declared parameter types with `str(prop.get("type") or "").strip().lower()`.
- Many tool specification schemas declare types in uppercase (`"type": "BOOLEAN"`, `"type": "INTEGER"`).
- Exact lowercase equality comparisons (`expected_type == "boolean"`) evaluate to `False` against uppercase specifications, causing type coercion to be silently skipped and passing raw string arguments to typed handlers that raise runtime `TypeError`s.
- **Pitfall:** Comparing schema types without case normalization bypasses type coercion on uppercase schemas, causing typed tool handlers to crash on stringified arguments.

### 47. Fuzzy Patching Trailing Newline Splicing Invariance
- In sliding-window fuzzy file patch replacement engines (such as trailing-whitespace tolerance ladders), the file's original lines retain trailing newline characters (`splitlines(keepends=True)`).
- When slicing replacement lines into the file line array (`res_lines[match_idx:match_idx + window_size] = new_lines`), if the original block being replaced terminated with a newline (`\n` or `\r\n`) but `new_lines[-1]` does not, inherit and append the original block's newline terminator to `new_lines[-1]`.
- Omitting the trailing newline causes the subsequent line in the file to be concatenated directly onto the end of the last replacement line, corrupting file structure and code syntax.
- **Pitfall:** Splicing replacement lines without inheriting trailing newline endings from the target slice merges adjacent lines together, corrupting the patched source file.

### 48. SQLite UPSERT Column Constraint Alignment & NULL Uniqueness
- In SQLite, the target column list in an `INSERT ... ON CONFLICT (cols) DO UPDATE` clause MUST match an existing `UNIQUE` or `PRIMARY KEY` constraint exactly. If the table is declared with `UNIQUE(source_type, source_id, speaker_name)` but the query executes `ON CONFLICT(source_type, source_id)`, SQLite raises `OperationalError: ON CONFLICT clause does not match any PRIMARY KEY or UNIQUE constraint`.
- Furthermore, in SQLite, `NULL != NULL`. A composite `UNIQUE(name, speaker_name)` constraint does not prevent duplicate rows when `speaker_name IS NULL`.
- In composite entities where secondary attributes may be `NULL` (such as playlists or user preferences), execute an explicit pre-query checking `WHERE name = ? AND (speaker_name IS NULL OR speaker_name = '')` before inserting, ensuring idempotent updates without phantom duplicate rows.
- **Pitfall:** Column mismatches between table `UNIQUE` constraints and `ON CONFLICT` clauses cause UPSERT queries to fail completely, while relying on SQLite `UNIQUE` constraints on nullable columns creates duplicate rows.

### 49. MCP Subprocess Future Leak Prevention & Stderr Lifecycle
- When dispatching JSON-RPC 2.0 requests over stdio subprocesses, wrap request future registration in `try...finally` immediately *before* calling `stdin.drain()`.
- If `stdin.drain()` raises an exception (`ConnectionResetError`, `BrokenPipeError`), the request ID remains orphaned in `_pending_requests` indefinitely unless popped in `finally`.
- Track and cancel background stderr drain tasks on session close to prevent dangling coroutines, and escalate teardown via `taskkill /PID /F /T` on Windows to reap child processes spawned by node/python runners.
- **Pitfall:** Failing to enclose `stdin.drain()` in `try...finally` permanently leaks request futures when a server subprocess crashes mid-request, causing subsequent requests to time out or exhaust memory.

### 50. Dynamic MCP Tool Deregistration Lifecycle
- When disconnecting an MCP server or shutting down the manager, implement and invoke `registry.unregister_tool(canonical_name)` for all tools associated with that session.
- Leaving disconnected tools registered in the core registry produces zombie tools that throw unhandled connection errors when called by the LLM in subsequent turns.
- **Pitfall:** Failing to unregister MCP tools on disconnect leaves dead declarations in the LLM's function list, causing turn crashes when the model invokes them.

### 51. Multi-Agent Kanban CAS (Compare-And-Swap) Status Transitions
- In multi-agent environments where autonomous subagents update a shared Kanban or task board, status updates must accept an `expected_status` parameter and execute conditional atomic updates (`UPDATE kanban_tasks SET status = ? WHERE id = ? AND (? IS NULL OR status = ?)`).
- Without CAS gates, a slower subagent finishing later blindly overwrites the status of a subsequent workflow step (e.g. overwriting `review` or `blocked` back to `in_progress`), corrupting the multi-agent task state machine.
- **Pitfall:** Unconditional task status updates in multi-agent swarms allow stale workers to overwrite verified task states, breaking pipeline convergence.

### 52. Event-Loop Non-Blocking Offload for Native OS Tooling (Computer Use / Vision)
- Synchronous OS operations (such as `PIL.ImageGrab.grab(all_screens=True)` or full-disk scanning) executed directly in async coroutines freeze the entire Python asyncio event loop on multi-monitor systems, dropping WebSocket connections and causing gateway heartbeat timeouts.
- Always offload blocking OS calls to worker threads via `await asyncio.to_thread(...)`, and sanitize application paths/names against shell metacharacters (`&`, `|`, `;`, `` ` ``, `$`, `>`, `<`, newlines) before passing them to OS launch helpers.
- **Pitfall:** Invoking synchronous desktop captures directly in async handlers blocks the event loop, freezing real-time streaming and dropping client network connections.

### 53. Thread-Safe Event Bus & Telemetry Registry Invariant
- In multi-threaded agent runtimes where worker threads emit telemetry while async loops read them, `asyncio.get_running_loop()` fails in worker threads with `RuntimeError: no running event loop`.
- The event bus must store a reference to the main event loop at initialization and provide a dedicated `emit_threadsafe()` method utilizing `asyncio.run_coroutine_threadsafe()`.
- Protect session queue registries, listener lists, and sequence counters with `threading.RLock()`.
- Shield event listeners so an exception in one subscriber does not abort the event loop or drop remaining deliveries.
- **Pitfall:** Discarding event loop handles or calling `get_running_loop()` from worker threads causes silent telemetry loss across background threads.

### 54. Self-Correction Error Classification Without Static Substring Traps
- Never flag tool failures by checking for naive string substrings (`"error:"`, `"exception:"`, `"failed:"`) inside stringified tool outputs. Exploratory reads (e.g. `read_file("errors.py")`, `grep_search_code("exception:")`) legitimately contain these words; naive matching falsely increments failure counts and trips the circuit breaker on benign inspection tasks.
- Rely on structured return codes/status keys or pass raw error strings through a dedicated `ErrorClassifier` that checks error taxonomies, while explicitly bypassing failure counting for read-only / failure-tolerant tools.
- **Pitfall:** Naive substring matching on tool returns trips circuit breakers when an agent simply inspects error logs or code containing exception keywords.

### 55. Multi-Tier Protocol-Driven Capability Handshake & Zero-Day Model Discovery
- Never lock model capabilities (multimodal vision, video comprehension, bidirectional audio, extended reasoning, tool calling) behind static hardcoded whitelists or rigid name-matching regexes alone. When upstream providers release novel zero-day models, a hardcoded agent blinds itself to the new model's capabilities.
- Implement a 3-layer dynamic capability handshake:
  1. *Protocol & Parameter Introspection (Upstream Metadata First):* Inspect provider metadata directly from `/v1/models` endpoints (OpenRouter, LM Studio, vLLM, Ollama, Google GenAI):
     - `supported_parameters` / `parameters`: The presence of `"reasoning"`, `"include_reasoning"`, `"thinking"`, `"reasoning_effort"`, or `"effort"` dynamically enables extended thinking; `"tools"`, `"functions"`, or `"tool_choice"` enables function calling.
     - `architecture.modality`: String patterns like `"text+image->text"` or `"text+image+video->text"` dynamically enable `supports_vision` and `supports_video`.
     - `architecture.instruct_type`: Tags like `"thinking"` or `"reasoning"` enable reasoning.
     - `capabilities` / `tags` (Ollama, HuggingFace): Arrays containing `"thinking"`, `"tools"`, `"vision"` dynamically populate capabilities.
     - Upstream Reasoning Ladders (`reasoning_effort_levels`, `reasoning_options`, `allowed_effort`): Dynamically map and normalize custom provider strings (`minimal`, `standard`, `extreme`) into standard tiers (`low`, `medium`, `ultra`).
  2. *Zero-Day Semantic Token Analyzer:* For novel models on proxy or minimal endpoints lacking rich metadata payloads, analyze word-boundary semantic tokens (`think`, `thought`, `thinker`, `reasoner`, `cot`, `qwq`, `r1`, `vision`, `vl`, `pixtral`, `omni`, `video`) so unlisted future models inherit proper capabilities without code modifications.
  3. *Universal Formatter & Reactive Contract:* Display model names via boundary-aware casing without baking reasoning tags into the title string, and expose dynamic capability arrays (`modalities: ["text", "image", "video", "reasoning"]`, `supported_reasoning_levels`) so user interfaces render exact options reactively from server metadata.
  4. *Ceiling Token Budget & Provider Parameter Conformance (HTTP 400 Defense):* Enforce reasoning effort ceilings strictly per model architecture. Sending unsupported wire levels (e.g. sending `"max"` or `"ultra"` to OpenAI `o1`/`o3` which strictly only accepts `"low" | "medium" | "high"`, or sending `"max"` to Gemini which tops out at `24576` tokens / OpenRouter `high`) triggers fatal HTTP 400 Bad Request errors or silent downgrades. Always clamp effort to the model's true ceiling before wire dispatch, and expose these exact boundaries in discovery responses (`supported_reasoning_levels: ["off", "low", "medium", "high"]`) so clients never request unsupported wire levels.
- **Pitfall:** Relying solely on static model name strings blinds the runtime when providers release novel reasoning or vision models, forcing manual code patches for every upstream release and breaking agent autonomy.

### 56. Non-Blocking Async SSRF & Redirect Event Hooks
- Validating external URLs solely via `url.startswith("http")` is an existential security vulnerability.
- Outbound fetch tools and webhooks must perform non-blocking asynchronous DNS resolution (`loop.getaddrinfo`), validating resolved IP addresses against loopback (`127.0.0.0/8`, `::1`), private subnets (RFC 1918), link-local/cloud metadata (`169.254.169.254`, `169.254.170.2`, `metadata.google.internal`), CGNAT (`100.64.0.0/10`), and IPv4-mapped IPv6 ranges.
- In HTTP clients supporting redirects (`follow_redirects=True`), attach redirect inspection event hooks (`event_hooks={"response": [_check_redirect]}`) to inspect the `Location` header on every intermediate hop, preventing open redirect chains into internal network services.
- **Pitfall:** Pre-validating the initial URL without redirect hooks allows external web servers to issue HTTP 302 redirects targeting private cloud metadata or local microservices, bypassing SSRF guards.

### 57. Cascading Output Truncation & Token Explosion Prevention
- Line-based output truncation (`max_lines=60`) alone fails to protect the model's context window when individual lines contain minified JavaScript bundles, base64 payloads, or multi-megabyte JSON arrays.
- If a line-truncated output candidate still exceeds `max_chars`, execution must cascade into character-based head/tail windowing (e.g. 40% head / 60% tail) snapped to newline boundaries, while offloading the full raw output to an atomic disk log file with pagination retrieval hints.
- **Pitfall:** Truncating solely by line count allows single lines of minified code to overwhelm context token budgets and trigger HTTP 413 context blowout crashes.

### 58. Server Lifespan Background Task Retention & Out-of-Loop Supervision
- In async application lifespans (such as FastAPI), background coroutines spawned via `asyncio.create_task` (e.g. model discovery refresh, MCP server connections) must be stored in a strong module-level reference set (`_BACKGROUND_TASKS.add(task)`) paired with `task.add_done_callback(_BACKGROUND_TASKS.discard)`.
- In Python 3.11+, unreferenced background tasks are liable to premature garbage collection mid-execution.
- Long-running SQLite shutdown checkpoints (`PRAGMA wal_checkpoint(TRUNCATE)`) must be offloaded to worker threads via `asyncio.to_thread` with an explicit timeout leash; if background workers or crons are still active when the shutdown leash expires, skip connection closure rather than closing while threads write, allowing SQLite to safely replay the WAL on the next startup.
- **Pitfall:** Unheld background tasks get silently garbage-collected mid-run, while closing SQLite connections during shutdown while background threads write corrupts WAL state.

### 59. Frontend React Hook Integrity & API Contract Synchronization
- In client user interfaces with dynamic model switching or conditional modes, never place conditional early returns (`if (disabled || !items.length) return null`) before React hook declarations (`useEffect`, `useCallback`, `useRef`). Doing so violates the React Rules of Hooks and causes runtime hydration crashes and unmounted hook errors when switching between models.
- Maintain strict synchronization between client API libraries (`apiClient`) and backend HTTP methods: calling a FastAPI `@router.patch` endpoint with `method: "POST"` triggers HTTP 405 Method Not Allowed.
- **Pitfall:** Violating React hook order breaks client rendering on model changes, while HTTP method mismatches in frontend API clients cause silent mutation failures.

### 60. Pagination-Aware Canonical Target in Trajectory Convergence
- In trajectory convergence and saturation detectors (`ConvergenceDetector`), canonical target extraction for file inspection tools (`read_file`, `read_local_file`) MUST incorporate pagination parameters (`offset`, `limit` or slice identifier `path#offset:limit`).
- Treating repeated reads of the same file across sequential offsets (e.g. offsets 1, 101, 201, 301, 401) as visits to an identical target falsely increments redundant inspection counters and prematurely halts legitimate exploratory reading with false-positive `information_saturated` convergence.
- **Pitfall:** Normalizing file inspection targets solely to the base file path causes multi-page reads of large files to trigger false-positive saturation stalls, abruptly terminating the agent mid-investigation.

### 61. High-Assurance Conversational Synthesis Fallback on Empty Loops
- When an agent loop concludes where every turn executed tools and produced zero narrative text, the closing pass MUST be strictly decoupled from tool definitions (`allow_tools=False`, `tools=[]`, `tool_choice="none"`).
- If the closing turn still yields empty text or encounters an API error, never immediately return a robotic empty-turn notice (*"No response was generated for this turn"* / *"Belum ada respons teks yang dihasilkan"*).
- Execute a dedicated non-tool auxiliary synthesis call (`call_universal_chat_model` with `read_only=True`) summarizing recent observations, actions taken, and clarifying questions, guaranteeing the user always receives a coherent natural response.
- **Pitfall:** Falling back to static empty-turn notices when a model emits tool calls on a closing pass presents the agent as broken or unresponsive after extensive work was already performed.

### 62. Verify-First Ground-Truth Autonomous Introspection (Anara Parity)
- When an agent is asked about its own capabilities, current codebase state, recent features, or architecture, it must NEVER answer from stale conversational context, static system prompts, or memory alone.
- Overly restrictive operational guidelines (e.g. telling an agent "respond in conversational prose for Q&A, do not invoke tools" or "do not inspect your own internal source code") cause autonomous agents to fail to observe physical reality on disk, falsely claiming newly built features do not exist.
- The runtime guidance MUST mandate **Verify First**: whenever asked about features, tools, or repo status, the agent must immediately invoke tools (`git log`, `read_local_file`, `glob_find_files`, `grep_search_code`) to observe the physical ground truth on disk before answering.
- **Pitfall:** Overly aggressive conversational gating prevents the agent from inspecting its own live workspace on Q&A turns, causing it to hallucinate that freshly committed features are absent.

### 63. Structured Output Outer Brace Preservation in Chat Cleaners
- Chat text sanitizers that strip markdown fences or stray structural punctuation from conversational replies must never blindly strip outer braces (`text.strip("{}[]\t\r\n")`) from candidate payloads when evaluating structured outputs or background self-improvement JSON.
- Stripping outer braces removes root object boundaries, causing downstream JSON parsers to receive malformed fragments (e.g. `"memory_actions": [...]`) instead of valid objects.
- Background evaluators and structured collectors must inspect and restore stripped outer braces or auto-balance unclosed delimiters before dispatching to JSON parsers.
- **Pitfall:** Blindly stripping punctuation from model responses corrupts valid JSON payloads into partial key-value fragments, silently breaking automated self-improvement and structured data extraction.

### 64. Bounded Filesystem Traversal & Event-Loop Thread Offloading (Freeze Prevention)
- In autonomous agent runtimes, file search and directory traversal tools (`grep_search_code`, `glob_find_files`, `find_files`) must NEVER execute synchronous `os.walk` or file scanning directly on the main `asyncio` event loop thread.
- If an agent issues a search rooted in a broad or top-level directory (e.g. user home `C:\Users\<user>` or drive roots), scanning massive directory trees (like Windows `AppData`, `.cache`, `node_modules`, `.cargo`, `.rustup`, `.conda`) synchronously blocks the Python event loop for minutes or hours, completely freezing API servers, WebSocket streaming, and messaging channel daemons (Telegram, WhatsApp) so the bot stops responding entirely.
- Always offload recursive directory walks to background threads (`matches = await asyncio.wait_for(asyncio.to_thread(_sync_walk), timeout=10.0)`).
- Implement mandatory case-insensitive exclusion lists (`IGNORED_DIRS = {"appdata", ".cache", ".git", "node_modules", "venv", ".cargo", ".rustup", ".conda", ".npm", "local settings", "application data"}`) and snap to a strict timeout leash returning partial results rather than hanging the agent.
- **Pitfall:** Synchronous `os.walk` on broad paths like `C:\Users\<user>` crawls millions of cache files in `AppData`, starving the asyncio event loop and causing the agent gateway to completely freeze and drop user interactions.

### 65. Build-Mode Exploration Convergence Protection & Transition Nudging
- In mutation/build mode (`read_only=False`), reaching exploration step thresholds (e.g. 10–12 inspection steps) must NEVER return `is_converged=True`.
- The mechanism: Returning `is_converged=True` forcibly terminates the execution loop and dispatches the final turn with `allow_tools=False` (`tools=None`), permanently stripping tool calling capabilities right when the agent has finished inspecting context and is about to invoke editing tools (`edit_file`, `write_local_file`). The model is forced into pure conversational prose, leaving it no choice but to emit narrative descriptions or apologies (*"I will now edit X, Y, Z"* / *"Ngedongeng"*), which users perceive as hallucination or refusal to act.
- **Rule:** In build mode, exploration exhaustion and soft saturation must return `is_converged=False` with `should_nudge=True`, injecting an explicit transition directive (`[INSPECTION COMPLETE — PROCEED TO EDIT]: You have gathered sufficient codebase context. Proceed immediately to invoke editing tools (edit_file, write_local_file) to implement the requested modifications.`). Hard termination with tool stripping must only fire when approaching the hard step budget limit (`step >= max_steps - 2`).

### 66. In-Turn Nudge Injection into Native Tool Result Messages
- In native structured function calling (OpenAI, Anthropic, Gemini), dynamic convergence and saturation nudges cannot be injected as separate synthetic user messages while tool executions are pending.
- The mechanism: Modern LLM provider APIs enforce strict conversation turn invariants: every assistant turn that emits `tool_calls` must be answered immediately by corresponding `tool` result messages matching the exact `tool_call_id`s before any new user turn can be appended. Dropping the nudge or failing to append it to the tool results blinds the model to the convergence guidance, causing it to continue passive inspections until the loop hard-aborts.
- **Rule:** Append dynamic convergence and saturation nudges (`\n\n[System Guidance]: ...`) directly to the content payload of the final executed tool result in the current turn before appending to history, ensuring the model immediately perceives the guidance on the very next token generation.

### 67. Canonical Target Directory Resolution in Multi-Tool Loops
- In canonical entity tracking (`extract_canonical_target`), always normalize directory path parameters across directory inspection tools (`list_directory`, `scan_workspace_folder`).
- The mechanism: If `extract_canonical_target` only checks `file_path` or `path` and misses `directory_path` or `folder_path`, directory listing calls evaluate to an empty target (`""`). This prevents multi-tool cycle detectors from detecting repetitive directory listing loops (`Listing . (x6)`) while simultaneously corrupting saturation counts.
- **Rule:** Map all directory inspection parameters (`directory_path`, `folder_path`, `path`) to canonical normalized directory paths, and track windowed line offsets (`#L1-L250`) on file readers so paginated sequential reads of large files do not falsely register as redundant inspections.

## Diagnostic Audit Checklist

1. **Loop Structure:** Does the runner own the ReAct iteration loop, or is it inverted into provider caller adapters?
2. **Persistence:** Are tool calls and observations persisted incrementally to a durable ledger before execution starts, or only on final turn exit?
3. **Verification:** Is there a stop-hook that enforces negative verification on code modifications, resetting staleness upon subsequent edits?
4. **Subagents:** Are recursive depth, context budgets, tool allowlists, and disk spilling strictly implemented?
5. **Scheduler:** Are background task claims atomic and resilient to worker process crashes?
6. **Workspace:** Is user session file access sandboxed to prevent unintentional mutation of the host codebase?
7. **Channel Ingress & Anti-Leak:** Are leaked tool calls scrubbed and mutating actions gated behind human approval, while interrupt signals (`/stop`) bypass turn locks?
8. **Provider Key Pools:** Is key retrieval strictly idempotent without spurious rotation on reads, and concurrency-safe across worker threads?
9. **Stream Chunking:** Are code fences tracked and re-opened across chunk splits to avoid breaking multi-channel markdown syntax?
10. **Compaction Boundaries:** Does in-loop history compaction preserve the atomic pairing of assistant tool calls and their results?
11. **Thinking Isolation:** Is reasoning stream filtering stateful across chunk boundaries with multilingual tag coverage?
12. **Multi-Tool LoopBreaker:** Does stall protection generate error results for stalled calls without dropping sibling tool calls?
13. **Atomic File Swaps:** Are persistent memory and identity markdown files updated via temp-file `fsync` and atomic `os.replace`?
14. **Database Lifecycle:** Are SQLite connections closed in `finally` blocks with `PRAGMA foreign_keys = ON;` and `busy_timeout` set on every connection?
15. **History Verbatim Integrity:** Is conversation history stored and retrieved without destructive heuristic substring filtering on user JSON payloads?
16. **Model Agnosticism:** Are auxiliary features (vision, voice, title, classification) free of hardcoded vendor model strings, resolving polymorphically through universal profiles?
17. **Conversational Tool Suppression:** Are conversational modes separated from tool-demanding build modes, and are tools completely stripped (`tool_choice="none"`) during forced conclusion passes?
18. **Cross-Process OS Locking:** Are multi-process memory file accesses protected by kernel locks (`msvcrt`/`fcntl`) on auxiliary `.lock` files to prevent cross-process corruption?
19. **Schema Coercion:** Does the tool registry perform type coercion and contract validation against JSON Schema definitions prior to handler invocation?
20. **Worktree Merge Abort:** On squash merge conflicts, does the worktree manager run `git merge --abort` on the parent repository and preserve the worktree for inspection instead of discarding work?
21. **Brand Hygiene:** Are commit messages and internal comments strictly scoped to project-native branding without leaking upstream framework names?
22. **Tool-Use Enforcement:** Does the runtime intercept simulated action text in asterisks/parentheses when 0 tool calls were made, forcing tool invocation via stop-gates?
23. **Fail-Fast Error Diagnostics:** Are provider and tool protocol errors surfaced transparently to the user/telemetry rather than silently swallowed into degraded text loops?
24. **Administrative Parity & Resilient Closing:** Are common environment actions (workspace switching) backed by native tools with fuzzy path resolution, and does loop termination summarize recent tool observations instead of falling through to empty-turn notices?
25. **Zero Lazy Slash-Command Delegation:** Does the agent execute tools immediately for environment/workspace changes rather than instructing the user to manually copy-paste slash commands?
26. **Posture Set Synchronization:** Are baseline posture tool sets (`CODING_TOOLS`) kept synchronized with `CORE_TOOLS` to prevent silent tool omission during channel egress pruning?
27. **Prompt Snapshot State Synchronization:** Does environment state mutation immediately synchronize in-memory tracking and database persistence so the next turn's prompt reflects updated paths without restart?
28. **Systematic 5-File Batched Auditing:** Is orchestrator review structured into 5-file batches with multi-subagent delegation benchmarking against reference engines before code changes?
29. **Monotonic Ladder Step-Down:** Does reasoning effort clamping step down to the nearest lower allowed tier instead of collapsing to index 0?
30. **Fixed-Width Lookbehind & Credential Scoping:** Are secret scrubbers constructed with fixed-width lookbehinds and scoped parameter anchors to avoid code keyword corruption?
31. **Anchored Key Validation:** Are session key regex patterns firmly anchored with `\Z` to reject trailing path traversal and injection payloads?
32. **Recursive Protobuf Deserialization:** Are SDK function call arguments converted recursively to native Python dicts and lists?
33. **Provider Prefix Hijacking:** Does `can_handle(model_id)` in vendor profiles exclude proxy prefixes (`ag/`, `9router/`, `openrouter/`, `groq/`) before matching generic names?
34. **Module-Level Attribute Delegation (PEP 562):** Do singleton manager modules implement `__getattr__` to prevent attribute loss when imported as a package attribute?
35. **Hybrid Dual-Identity Resolution:** Are session IDs passed through a canonical resolver (`_resolve_session_id`) across all mutation and deletion methods to prevent secondary table leaks?
36. **Fuzzy Patching & CRLF Normalization:** Does file editing support multi-strategy matching (exact, universal newline CRLF/LF, trailing whitespace tolerance) with atomic temporary file swapping?
37. **Tool Registry Concurrency:** Are all tool registration mutations and catalog iterations protected by reentrant locks and copied snapshots to prevent `RuntimeError: dictionary changed size`?
38. **OpenBLAS Thread Clamping:** Are `OPENBLAS_NUM_THREADS=1` and `OMP_NUM_THREADS=1` exported before importing NumPy on Windows to prevent virtual memory thread pool exhaustion?
39. **PowerShell Base64 Encoding:** Are Windows terminal executions dispatched via UTF-16LE Base64 `-EncodedCommand` to prevent quote corruption and string interpolation breaks?
40. **Prompt Toolkit Stream Decoupling:** Are CLI prompt inputs wrapped in `patch_stdout` with idempotent stream framing to prevent prompt tearing from background agent events?
41. **REST Schema Hybrid Typing:** Are session IDs declared as `Optional[Union[int, str]] = None` in REST API models and routes to support both database integers and canonical strings without 422 errors?
42. **Longest-Prefix Pricing Key Matching:** Are pricing table keys sorted by length descending to prevent shorter model prefixes from collidng with and overcharging longer variants?
43. **Case-Insensitive Dynamic Schema Type Coercion:** Are JSON Schema types normalized via lowercase comparison to prevent uppercase specification types from bypassing argument coercion?
44. **Fuzzy Patching Trailing Newline Splicing:** Does line-sliding fuzzy patching inherit trailing newlines from replaced blocks to prevent merging adjacent file lines?
45. **SQLite UPSERT & NULL Alignment:** Do `ON CONFLICT` column targets exactly match table `UNIQUE` constraints, and are nullable columns explicitly pre-queried to avoid duplicate rows?
46. **MCP Subprocess Future Leak Prevention:** Are stdio JSON-RPC request future registrations wrapped in `try...finally` before `stdin.drain()` to prevent permanent leaks on broken pipes?
47. **Dynamic MCP Tool Deregistration:** Does MCP server disconnect or shutdown explicitly unregister its tools from `ToolRegistry` to prevent zombie tool calls?
48. **Multi-Agent Kanban CAS:** Do task board status transitions enforce CAS via `expected_status` conditional SQL queries to prevent lost updates across subagents?
49. **Non-Blocking OS Tool Execution:** Are heavy synchronous OS calls (desktop screen captures, disk traversals) offloaded via `asyncio.to_thread` with shell metacharacter validation?
50. **Event-Loop Non-Blocking Offload:** Are all synchronous I/O operations (SQLite, subprocesses, file operations) inside async routes and coroutines offloaded via `await asyncio.to_thread(...)`?
51. **Keepalive & Socket Lifecycle Shielding:** Do SSE and WebSocket connections implement heartbeat pulses and structured task cancellation in `finally:` to prevent proxy drops and unhandled runtime errors on closed sockets?
52. **SSRF & Redirect Defense:** Do web fetching and webhook tools perform async DNS resolution against private/reserved/cloud-metadata IP ranges with redirect hooks to prevent TOCTOU and internal scanning?
53. **Thread-Safe Event Bus Loop Binding:** Does the event bus bind the main event loop handle to allow worker threads to dispatch events via `run_coroutine_threadsafe` with exception shielding?
54. **Taxonomy-Based Error Classification:** Does self-correction use structured error taxonomy classification rather than static substring matching (`"error:"`, `"exception:"`) to prevent tripping circuit breakers on legitimate exploratory inspection?
55. **Multi-Tier Protocol Handshake & Wire Ceiling Clamping:** Are model capabilities and reasoning effort ladders resolved through upstream metadata introspection and semantic tokens, and are reasoning levels strictly clamped to model ceilings (e.g. Gemini / o-series capped at `high`) to prevent HTTP 400 wire rejection?
56. **Async SSRF Redirect Hooks:** Do HTTP clients following redirects re-inspect destination `Location` headers on every hop against private and metadata subnets?
57. **Cascading Output Truncation:** Does output truncation cascade into character-based head/tail windowing if line-based truncation still exceeds the maximum character budget?
58. **Strong Background Task Retention:** Are all lifespan background tasks retained in a strong reference set with completion callbacks to prevent premature garbage collection?
59. **React Hook Order Invariance:** Are all React hooks declared unconditionally before any early returns to prevent runtime hydration and reconciliation crashes on model switches?
60. **Pagination-Aware Convergence:** Do saturation detectors distinguish file pagination offsets/slices to prevent multi-page reads of large files from triggering false-positive saturation convergence?
61. **Conversational Synthesis Fallback:** Does the runtime guarantee a non-empty conversational synthesis via auxiliary models when a loop ends with zero narrative text, avoiding empty-turn notices?
62. **Verify-First Ground-Truth Autonomous Introspection:** Does operational guidance mandate calling inspection tools (`git log`, `read_local_file`) on self-capability/architecture questions rather than answering from stale memory?
63. **Structured Output Outer Brace Preservation:** Does JSON parsing auto-balance and restore stripped outer braces if chat text cleaners strip punctuation?
64. **Filesystem Traversal Thread Offloading:** Are recursive search tools (`os.walk`) offloaded to `asyncio.to_thread` with an exclusion list (`AppData`, `.cache`, `node_modules`, `.cargo`) and a hard timeout (10s) to prevent event-loop freezing?
