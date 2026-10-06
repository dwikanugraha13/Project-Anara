---
category: autonomous-ai-agents
name: agent-gateway-and-channel-engineering
description: Use when building or auditing agent omnichannel gateways.
---

# Agent Gateway and Channel Engineering

Use this skill when auditing, designing, implementing, or hardening agent omnichannel gateways, multi-platform adapters (Telegram, Discord, WhatsApp, Slack, Terminal CLI), and multi-modal streaming media delivery pipelines.

## Core Architectural Invariants

### 1. Adapter Boundary Secret Scrubbing
- Always filter error strings and diagnostic output through a centralized regex redaction utility (`redact_sensitive_text(str(e))`) before persisting to logs, returning in API dicts, or delivering to chat channels.
- Platform bot tokens and webhook secrets are routinely embedded in HTTP URL paths (e.g. `https://api.telegram.org/bot<TOKEN>/...`, Discord webhook URLs).
- **Pitfall:** Returning raw `str(e)` or logging network error objects leaks bot tokens and webhook credentials directly into chat channels or public log sinks whenever a connection times out.

### 2. Strict Callback Data Ceiling Enforcement
- When generating interactive inline keyboards (approvals, model pickers, wizards), constrain `callback_data` payloads to platform-enforced ceilings (e.g. 64 bytes on Telegram).
- Map long plan IDs, tool argument hashes, or model identifiers through a bounded in-memory short-map or truncated hash (<= 48 characters) rather than raw identifiers.
- **Pitfall:** Emitting `callback_data` exceeding 64 bytes causes the platform API to reject the entire message with fatal HTTP 400 errors (`BUTTON_DATA_INVALID`).

### 3. Rate-Limit Backoff & Burst Flood Ceilings
- Enforce a maximum burst split limit (e.g. `MAX_SPLIT_MESSAGES = 8`) when chunking long agent outputs.
- If output exceeds the burst ceiling, truncate further chunks and append an explicit user notification with an artifact reference hint (`read_file`).
- Inspect HTTP 429 response headers for `retry_after` and apply exponential backoff with jitter instead of aborting the message delivery or spinning in a tight loop.
- **Pitfall:** Emitting dozens of sequential chunks in response to a verbose agent turn triggers platform rate-limit bans (e.g. Discord 5 msgs/5s limit), dropping trailing message parts.

### 4. Platform-Specific Markdown Syntax Translation
- Do not transmit raw GitHub-flavored Markdown to platforms with distinct syntax rules.
- Maintain dedicated formatting converters at the adapter boundary:
  - **WhatsApp:** Stash fenced code blocks in placeholders, then convert `**bold**` to `*bold*`, `# Header` to `*Header*`, and `~~strike~~` to `~strike~`, before restoring fences.
  - **Telegram:** Escape HTML special characters (`<`, `>`, `&`) outside code blocks; convert fenced blocks to `<pre><code>...</code></pre>`.
- **Pitfall:** Sending raw Markdown headers (`### Title`) and double-asterisks (`**text**`) to WhatsApp or Telegram without transformation leaves unrendered markdown syntax visible to users.

### 5. Webhook Preflight & Long-Polling Hygiene
- In long-polling daemons (e.g. Telegram `getUpdates`), always issue an explicit webhook teardown (`deleteWebhook(drop_pending_updates=False)`) during adapter initialization.
- Reuse a persistent `httpx.AsyncClient` session with keep-alive across polling ticks rather than re-instantiating HTTP clients on every poll cycle.
- **Pitfall:** Starting long-polling on a bot previously registered with a webhook endpoint locks the daemon in an infinite HTTP 409 conflict loop (`can't use getUpdates method while webhook is active`).

### 6. Non-Blocking Media & Attachment I/O
- Never perform synchronous file I/O (`open(path, "rb").read()`) directly inside asynchronous platform dispatch handlers.
- Offload file reading to a thread pool (`await asyncio.to_thread(...)`) or use asynchronous file streaming.
- Verify file existence and validate size against platform upload limits (e.g. 50MB on Telegram, 25MB on Discord) before initiating network transfers.
- **Pitfall:** Reading multi-megabyte media attachments synchronously on the asyncio event loop thread freezes active WebSockets, typing indicators, and concurrent turn runners.

### 7. Graceful Server Lifespan & Process Tree Reaping
- Server lifecycle managers (`lifespan`) must coordinate cleanup across all child processes and platform connections upon shutdown.
- Terminate quick tunnels, halt background process registry workers, close active WebSockets with code `1001`, and execute `PRAGMA wal_checkpoint(TRUNCATE);` to flush SQLite write-ahead logs.
- On Windows hosts, register native Win32 console control handlers (`SetConsoleCtrlHandler`) via `ctypes` to intercept `CTRL_CLOSE_EVENT` and `CTRL_SHUTDOWN_EVENT`, triggering clean lifespan teardown when the terminal is closed.

### 8. Acoustic Stream Alignment & Non-Zero Voicing Emotion Classification
- In real-time Speech Emotion Recognition (SER), never classify digital silence or low-energy ambient noise as sadness or depression; require active voiced energy (`overall_rms >= 0.006` and harmonic pitch estimates).
- When calculating parabolic interpolation for fundamental frequency peak refinement, maintain the correct vertex formula $\delta = \frac{\gamma - \alpha}{2(2\beta - \alpha - \gamma)}$ to prevent lag estimation inversion.
- Ensure PCM16 buffer length is an even multiple of 2 before unpacking into NumPy int16 arrays (`buf[:len(buf) - len(buf)%2]`) to eliminate fatal `ValueError` alignment crashes.

### 9. Model-Driven Intent & Approval Dispatch (Zero Keyword Gating)
- Omnichannel approval dispatchers and intent evaluators must never rely on static token sets (e.g. `AFFIRMATIVE_TOKENS = {"yes", "ok", "lanjut", "setuju"}`).
- Channel interactions come from diverse users in multiple languages with informal phrasing, slang, or negated sentences (*"jangan jalankan"*).
- Rely on auxiliary LLM intent classification with cached verdicts (`_INTENT_CACHE`), only accepting single-character machine tokens (`[y/N]`, `1/0`) when interacting with raw headless CLI terminals.
- **Pitfall:** Hardcoded token lists cause immediate false rejections of valid approvals expressed in other languages or informal syntax, and false positive approvals on negated phrases.

### 10. Automated Windows Background Service & Global CLI Shims
- When packaging autonomous agents for desktop distribution on Windows hosts, do not require manual batch execution or manual Task Scheduler configuration.
- Implement dual-path self-registration upon first startup or installation:
  1. **Primary:** Windows Task Scheduler (`schtasks.exe /create /tn "<Agent>_Gateway" /sc onlogon /delay 0000:30 /f`) executing a windowless detached VBScript or runner.
  2. **Fallback:** If non-elevated or blocked by Windows policy, silently drop a `.vbs` launcher into the Windows User Startup folder (`%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\<Agent>.vbs`).
- For global terminal execution (`<agent>` in any shell), generate paired wrapper shims: `.cmd` (for CMD and PowerShell) and extensionless POSIX shell script (for Git Bash, MSYS, and WSL). Persistently register the bin directory into Windows User `PATH` (`HKCU\Environment\Path`) and copy shims to currently active PATH directories for immediate zero-restart access.
- **Pitfall:** Relying solely on `schtasks.exe` fails silently on standard user accounts with restricted Task Scheduler permissions, while omitting POSIX shims leaves Git Bash / WSL terminal users unable to invoke the command without `.cmd` extensions.

### 11. Interactive Terminal TUI & Live Streaming Adapters (CLI Parity)
- For agent CLI channels, provide full interactive TUI parity:
  - **Live Token Streaming:** Stream model response deltas in real-time with clean box framing (`StreamTokenRenderer`), eliminating long silent pauses during generation.
  - **In-Place Animated Tool Spinner:** Render tool execution state with animated braille dots and a live elapsed stopwatch (`\r` carriage return rewrite); resolve cleanly to green checkmarks (`✓`) upon completion to prevent terminal output pollution.
  - **Interactive Shell Navigation:** Use `prompt_toolkit` (`PromptSession`, persistent `FileHistory` at `~/.<agent>/cli_history`, autocompletion for slash commands and workspace `@path` triggers).
  - **Graceful Cancellation:** Catch `KeyboardInterrupt` (`Ctrl+C`) during streaming or tool execution to abort only the current turn, cleanly releasing spinner state without killing the process or corrupting session history.
- **Pitfall:** Blocking the terminal on synchronous `input()` without token streaming leaves the user staring at an unresponsive terminal for 10-30 seconds, while multi-line tool outputs without in-place rewriting clutter the scrollback.

### 12. Web Studio Chat & Reasoning UI Invariants
- **Reasoning / Thought Process Durability:** Never wipe or discard model thinking tokens (`activeThinkingText`) upon the first arrival of output narrative tokens. Capture a snapshot and persist `thinkingText` and `thinkingDuration` into the message data model (`TranscriptItem`) so users can inspect the full reasoning chain post-turn in an expandable accordion (`Thinking (3.2s) ▾`).
- **Thinking Live-Latch & Low-Churn Ticks:** When reasoning streams live, latch the thinking accordion open (`isExpanded = true`, `sawLivePreview = true`) and keep it open post-settle to prevent disorienting layout jumps upon turn completion. Throttle elapsed timers to 1s ticks (`Math.round(elapsed/1000)`) rather than 100ms intervals to eliminate unnecessary CPU re-renders.
- **Stable-Height 4-Action Message Footer:** Each settled assistant turn must feature a stable-height, hover/focus-revealed action bar: elapsed duration (`⏱ X.Xs`), Branch in new chat (`/branch`), Read aloud / browser TTS audio playback, 1-Click retry prompt re-submission, and Copy message with visual confirmation.
- **Transcript Error Boundary & Interrupted State:** Seal interrupted turns with an explicit amber/rose `Interrupted` status pill, and format upstream API failures into a dedicated error card with an actionable 1-click `Retry ↺` button rather than silently swallowing errors or resetting to idle.
- **Smart Scroll Pinning (Anti-Hijacking):** Do NOT unconditionally invoke `scrollIntoView` on every streaming token delta. Compute distance to bottom (`scrollHeight - scrollTop - clientHeight < 120`). Only auto-scroll when the user is already near the bottom; if the user scrolled up to read earlier code or responses, pause auto-scrolling and render a floating "Scroll to bottom" button.
- **Lifecycle-Aware Tool Deduplication:** Do not deduplicate or overwrite tool call items in the message stream based solely on matching tool names (`toolName === toolName`). Differentiate lifecycle events (`agent_action_start` vs `agent_action_complete`); append each new start event so that multiple consecutive read/search operations are preserved and can be grouped cleanly into an exploration summary (`Explored 3 reads, 2 searches ▾`).
- **Pitfall:** Wiping thinking text on the first stream delta permanently destroys visibility into model reasoning for thinking models (Claude 3.7 Sonnet, DeepSeek R1, Gemini Flash Thinking), while un-gated auto-scroll violently hijacks the user's viewport during active reading.

### 13. IDE Code & Diff Viewport State Discipline
- **Explicit Code vs Diff View Modes:** Never permanently lock the editor viewport into a unified diff view mode (`unifiedMergeView`) simply because a file is non-empty. Default to clean editable `Code` view; render an explicit interactive toggle `[Code] ↔ [Diff (+X -Y)]` only when the active code differs from the original content.
- **Multiset Frequency Diff Accounting:** Avoid naive `Set`-based line diff calculations, which collapse duplicate identical lines (such as closing braces `}` or blank lines). Use multiset / frequency maps to count added and deleted lines accurately.
- **Stale Closure Drag Resizing:** When implementing draggable panel dividers, avoid referencing React state variables inside `useEffect` mouse event listeners without ref-backing. Track live coordinates and dimensions in `useRef` and read from refs on `mouseup` before persisting to `localStorage` and cookies, eliminating stale-closure revert bugs and reducing re-render churn during 60 FPS dragging.
- **Pitfall:** Initializing diff view on every non-empty file without a toolbar toggle traps users in read-only diff mode, while closures over state in mouseup listeners cause custom layout panel dimensions to snap back to defaults on reload.

### 14. Explicit Ingress Channel Propagation & Platform Context Guard
- When processing turns across multi-channel runtimes (Web Studio, Desktop GUI, Terminal CLI, Telegram, Discord), the execution runner and ingress pipelines must explicitly pass the originating platform identifier (`channel=runner.platform` or `channel=ctx.channel`) down into prompt assembly.
- Never allow platform channel context to fall back silently to an arbitrary default (such as `'cli'`). If missing, inspect the active session record in the database (`s_obj.get("channel")`) before defaulting.
- The prompt assembler must inject unambiguous platform boundaries (`[ACTIVE PLATFORM INTERFACE: WEB & DESKTOP STUDIO]` vs `[ACTIVE PLATFORM INTERFACE: TERMINAL / CLI SESSION]`).
- **Pitfall:** Omitting the channel parameter during prompt assembly causes web and desktop turns to fall back to CLI instructions, leading the model to hallucinate that it is operating inside a terminal and misdirecting users.

### 15. Omnichannel Clarification & Interactive Question Wizard Bridges
- When an agent calls an interactive questionnaire or clarification tool (`clarify` / `interactive_question`), the omnichannel gateway must immediately wire the event to the active channel's native UI (e.g. Telegram inline keyboard buttons, Slack blocks, Discord action rows) rather than exclusively broadcasting to web sockets.
- Maintain consistent parameter schemas between the wizard button generator and callback query dispatch router (e.g., passing `qans:{q_id}:{idx}:{opt_idx}` matching the callback router's expected arity), and define backward-compatible resolution aliases (`resolve_interactive_question = resolve_question_response`) to avoid unhandled `ImportError` crashes during resolution.
- **Pitfall:** Emitting question events to a generic event bus without an active channel presenter leaves the async `Future` waiting indefinitely on the event loop, freezing the turn runner until forced interrupt (`/stop`) or timeout.

### 16. Channel Session ID Propagation & Anti-Split-Brain State
- When slash commands (e.g. `/workspace`, `/status`, `/model`) and agent conversation loops share access to stateful session engines, the channel gateway must assign the resolved channel `session_id` into the request object (`req.session_id = session_id`) *before* delegating to the unified command hub.
- Command handlers inspecting active workspaces or session parameters must dynamically fall back to the active agent session ID (`effective_sid = ctx.session_id or agent.get_active_session_id()`) if context IDs default to 0 or null.
- **Pitfall:** Dispatching slash commands without bound session IDs causes inspection commands to read from the global default session (session 0) while autonomous tools mutate the channel session (e.g. session 382), producing contradictory split-brain status reports where an updated workspace appears unchanged.

### 17. Posture-Preserved Autonomous Tools vs Slash Command Delegation
- Agents must never instruct users in conversational text to copy-paste or manually type slash commands (e.g. *"kirim slash command ini: `/workspace <dir>`"*) when the agent has tools to perform the operation directly.
- The platform tool filter / pruning matrix must include workspace navigation and configuration tools in the baseline coding posture set (`CODING_TOOLS`), ensuring tools are exposed across all messaging channels rather than silently pruned.
- Implement fuzzy directory path resolution (`resolve_fuzzy_folder_path`) at the tool layer to map colloquial, typo-prone, or relative inputs (`download`, `C: download`, `~/Documents`) directly to canonical OS filesystem paths without initiating redundant exploratory search loops.
- **Pitfall:** Leaving a tool out of the base platform set causes the agent to hallucinate that it lacks capability, entering multi-step codebase grepping loops searching for internal methods before deflecting the task back to the user as a manual slash command.

### 18. CLI Subcommand vs Prompt Routing & Terminal Buffer Resilience
- **Smart Argv Dispatch (Subcommands vs Prompts):** When pairing administrative subcommands (`daemon`, `skills`, `gateway`, `autostart`) with direct prompt execution in an agent CLI runner, do not attach an optional positional prompt argument to a top-level `argparse` parser containing `add_subparsers()`. Subparsers greedily consume the first positional token, causing free-form queries (e.g. `<agent> "hello world"`, `<agent> create a script`) to fail with `invalid choice` errors. Inspect `sys.argv[1:]` prior to parser invocation; if the first non-flag token does not match `KNOWN_SUBCOMMANDS` and is not `--help`/`-h`, route directly to single-prompt execution.
- **Terminal Buffer & Screen Adaptation:** On Windows environments, rich terminal engines (`prompt_toolkit`) default to Win32 console buffer APIs (`Win32Output`). In non-standard or modern terminal emulators (Git Bash, MSYS2, mintty, Windows Terminal, VS Code subshells, or piped subprocesses), this triggers fatal `NoConsoleScreenBufferError: Found xterm-256color, while expecting a Windows console`. Always check `sys.stdin.isatty()` before instantiating interactive terminal sessions, provide safe fallback from `create_output()` to `Vt100_Output.from_pty(sys.stdout)` or thread-delegated `input()`, and bypass interactive session setup entirely in single-prompt mode.
- **Non-Blocking Async Prompts:** Within `asyncio` event loops, avoid synchronous `session.prompt()` calls that generate unawaited coroutine warnings (`RuntimeWarning: coroutine 'Application.run_async' was never awaited`). Always use `await session.prompt_async(...)` or `await asyncio.to_thread(input, ...)` for seamless, non-blocking turn ingestion.
- **Pitfall:** Using standard `argparse` subparsers with positional prompt fallbacks breaks single-command agent execution from the terminal, while unshielded `Win32Output` crashes the CLI instantly when invoked inside Git Bash or automated CI test harnesses.

### 19. Multi-Provider Model Discovery & Dynamic Catalog Resilience
- **Timeout Headroom on Bulk Model Discovery:** Upstream or local proxy model endpoints (e.g. OpenAI-compatible proxies serving hundreds of models, like 700+ models / 300KB+ JSON) take multiple seconds on cold start. Setting aggressive client timeouts (e.g. `<= 6.0s`) triggers premature `TimeoutException` fallbacks to a single default model, which is then cached for the TTL (e.g. 5m), making the catalog appear truncated/incomplete. Enforce generous timeouts (`>= 15.0s`) on bulk discovery endpoints.
- **DB Model Pruning Awareness:** When auditing missing models in agent gateways, always inspect persistent prune tables (`hidden_models`) before assuming discovery failed, as models hidden through admin UIs are filtered out at query time.
- **CLI Presentation Truncation Disclaimers:** When presenting model pickers in CLI or messaging channels, never slice output (e.g. `models[:12]`) without an explicit total counter and search guidance (e.g. `Showing 15 of 781 models. Use /model <filter>`). Silent truncation leads users to believe only a fraction of models were discovered.
- **Safe Coroutine Lock Acquisition:** Never use synchronous `with cls._get_lock():` on an async coroutine `async def _get_lock() -> asyncio.Lock:`. It fails silently leaving the coroutine unawaited, emitting `RuntimeWarning`, and leaving shared capability caches unsynchronized. Use `lock = await cls._get_lock(); async with lock:`.
- **DNS Rebinding & Private Network SSRF Defense:** In agent image proxies and browser navigation tools, validate resolved IP addresses (`socket.getaddrinfo`) against `ip.is_private`, `is_loopback`, `is_link_local`, `is_reserved`, `is_unspecified`, `is_multicast`, CGNAT (`100.64.0.0/10`), and cloud metadata hostnames (`metadata.google.internal`) before issuing network requests.

### 20. Full-Duplex Bidi Audio Streaming & Supervisor Reconnect Isolation
- When implementing full-duplex bidirectional audio streaming (e.g. Gemini Live `bidiGenerateContent`) via WebSockets, never manage send and receive loops with a simple `asyncio.gather(recv_loop, send_loop)`.
- If the receive loop exits cleanly due to a server connection close or network drop, a simple `gather` leaves the send loop permanently hung waiting on its input queue, causing the connection handler to deadlock and never return.
- Manage concurrent streaming loops with `asyncio.wait([recv_task, send_task], return_when=asyncio.FIRST_COMPLETED)`: when either task completes or throws an exception, immediately cancel the pending sibling task and drain it (`await task`) so the supervisor session tears down cleanly.
- Never set a global termination flag (`self._is_running = False`) inside inner send error handlers on recoverable network disconnects (`1011`, `1012`, `ConnectionClosed`, `keepalive timeout`). Prematurely clearing the running flag permanently kills the outer supervisor loop, disabling automated backoff, key rotation, and reconnect cycles.
- **Pitfall:** `asyncio.gather` on dual send/receive WebSockets causes deadlocks on server disconnects, while mutating supervisor flags on recoverable send errors permanently breaks live voice auto-reconnect.

### 21. Non-Blocking Async Gateway Tunnel Supervisors & Lazy Lock Ingestion
- When supervising external gateway tunnels (e.g. Cloudflare Quick Tunnels `cloudflared`) from an async daemon or API server, never execute synchronous network downloads (e.g. `urllib.request.urlopen` downloading binaries) directly on the main event loop thread. Offload binary checks and downloads to `await asyncio.to_thread(...)`.
- Avoid instantiating global `asyncio.Lock()` at module import time (`_START_LOCK = asyncio.Lock()`). On Windows and multi-threaded event loop architectures, module-level locks bind to whichever loop was active at import time, throwing `RuntimeError: Task <Task> got Future <Future> attached to a different loop` when accessed from the server's main lifespan loop. Use lazy lock getters (`_get_start_lock()`).
- Avoid hardcoding static gateway public URLs (e.g. `"https://domain.com"`) for named tunnels; parse tunnel configuration files (e.g. `config.yml` `ingress[].hostname`) dynamically so custom domains route without code changes.
- **Pitfall:** Synchronous binary downloads freeze the entire server event loop for up to 60 seconds, while import-time `asyncio.Lock` causes cross-event-loop crashes on Windows daemons.

### 22. Cross-Platform Slash Command Markup Normalization & HTML Injection Defense
- When slash commands (e.g. `/model`, `/memory`, `/status`) output structured rich text containing dynamic variables (user names, memory facts, search keywords), always escape dynamic inputs with `html.escape()`. Unescaped dynamic characters (`<`, `&`) in Telegram HTML strings trigger fatal HTTP 400 `Bad Request: can't parse entities` errors.
- Never transmit raw Telegram HTML tags (`<b>`, `<code>`, `<blockquote>`, `<i>`) indiscriminately across all channel surfaces. In non-Telegram surfaces (Terminal CLI, Discord, Slack, WhatsApp), raw HTML renders as broken, unrendered markup (e.g. `<b>SELECT MODEL</b>`).
- Implement an outbound channel markup normalizer (`format_command_text_for_channel`) at the command hub layer that preserves HTML for Telegram/Web, but converts HTML tags into standard Markdown (`**bold**`, `` `code` ``, `> quote`) or clean plain text for CLI, Discord, and WhatsApp before delivery.
- **Pitfall:** Unescaped dynamic strings in command responses crash Telegram delivery with 400 Bad Request, while un-normalized HTML tags degrade readability across CLI and non-Telegram chat channels.

### 23. Public Group Admin Fencing for Sensitive Callbacks
- In multi-user group chats (Telegram supergroups, Discord servers, Slack public channels), inline keyboard callbacks that trigger global server mutations (e.g. switching active LLM models `setm:`, altering voice synthesis modes `vmode:`, or approving mutating tool calls `approve:`) MUST verify the sender's user ID against authorized channel administrators (`get_authorized_admins(channel)`).
- If the sender is unauthorized, reject the callback query immediately with an ephemeral warning notification and abort execution.
- **Pitfall:** Failing to fence inline callbacks allows any member or guest in a public group to hijack the global model selection or trigger unauthorized tool executions on the host.

### 24. Question Wizard Callback Double-Tap De-bouncing
- In interactive multi-step questionnaire wizards rendered over messaging platforms, rapid double-taps or duplicate packet deliveries can cause race conditions where redundant answers are appended to state or indexing exceeds array boundaries.
- The callback router must verify `if q_idx != q_state.get("current_index", 0): return` before recording the answer or advancing the index.
- **Pitfall:** Unbounded callback taps record duplicate answers into the questionnaire capsule, resulting in desynchronized questions and runtime `IndexError` crashes.

### 25. Telegram HTML Entity Escaping in Error Notices
- Diagnostic notifications and error notices formatted for Telegram (`parse_mode="HTML"`) that incorporate raw exception strings (`str(e)`) or error details must escape all dynamic text via `html.escape()`.
- Error traces frequently contain Python generic types (e.g. `<class 'Exception'>`), XML snippets, or angle brackets (`<`, `>`).
- **Pitfall:** Unescaped error strings crash Telegram API deliveries with HTTP 400 `Bad Request: can't parse entities`, preventing the user from ever seeing error notifications.

### 26. Sequential Chunk Failure Propagation in Multi-Message Dispatches
- When splitting verbose agent responses into sequential chunks across rate-limited messaging APIs (WhatsApp, Slack, Discord), inspect the return status of every individual chunk.
- If any chunk fails to dispatch, immediately halt subsequent chunk deliveries and return the concrete error dictionary rather than continuing the loop and returning the status of the final chunk.
- **Pitfall:** Overwriting intermediate failure statuses with the final iteration hides earlier delivery drops and falsely signals success to the turn orchestrator.

### 27. Direct Await for Telemetry & Event Bus Dispatches
- In asynchronous platform adapters (e.g. Web Studio, HUD presenters), never dispatch event bus emissions via unawaited fire-and-forget tasks (`asyncio.create_task(telemetry_bus.emit(...))`) without maintaining a strong reference.
- In modern Python runtimes (3.12+), unreferenced background tasks risk premature garbage collection by the event loop before execution, resulting in dropped tokens and lost telemetry.
- Always use direct `await telemetry_bus.emit(...)` inside async platform coroutines.
- **Pitfall:** Fire-and-forget tasks without strong references cause intermittent, silent drops of streaming text chunks and action status events.

### 28. Pre-Flight File Size Ceilings Before Media Uploads
- Always inspect the physical file size on disk (`os.path.getsize(file_path)`) against target platform upload ceilings (Discord 25MB, Slack 50MB, Telegram 50MB) *before* reading binary payloads into RAM or opening multi-part POST streams.
- If a file exceeds the platform ceiling, abort the upload immediately and return an explicit descriptive error citing the file size and platform threshold.
- **Pitfall:** Blindly reading multi-hundred megabyte files into RAM crashes the host process with Out-of-Memory (OOM) errors and burns gateway bandwidth on guaranteed upload rejections.

### 29. WebSocket Session Background Task Tracking & Zombie Cancellation
- In WebSocket connection hubs and gateways, background tasks spawned per connection (e.g. STT transcription, HUD enrichment, speaker biometrics, voice enrollment) must be registered in a session task set (`session_tasks: Set[asyncio.Task]`) with `task.add_done_callback(session_tasks.discard)`.
- When a client disconnects or an unhandled exception occurs, the gateway `finally:` block must iterate through and cancel all remaining tasks (`for t in list(session_tasks): if not t.done(): t.cancel()`).
- Wrap WebSocket dispatch calls inside asynchronous tasks with a disconnect-immune helper (`safe_send_json`) catching `RuntimeError` and `WebSocketDisconnect`.
- **Pitfall:** Spawning un-tracked `asyncio.create_task` inside WebSocket event loops leaves zombie tasks running post-disconnect, which crash with `RuntimeError: Cannot call "send" once a close message has been sent` when attempting to stream trailing audio or subtitles.

### 30. Chat Stream Plan Approval State Machine Resolution
- When interactive plan approval is routed through chat streaming handlers, user confirmations or cancellations must explicitly resolve the pending action in the state machine (`session_state_manager.resolve_action(..., ActionState.EXECUTING)` on approval, `ActionState.REJECTED` on denial).
- Intent classification must be fully asynchronous (`await classify_approval_intent(...)`) rather than blocking the asyncio event loop thread with synchronous `future.result(timeout=...)`.
- **Pitfall:** Failing to transition the action state leaves the action pending until TTL expiration, preventing immediate execution of the approved plan and blocking subsequent turns.

### 31. Windows Atomic File Replacement & Reader Synchronization
- File access for raw prompt assets, persona definitions, or system soul markdown files that are dynamically mutated must be protected by thread locks (`with _LOCK:`) across both read and write paths.
- On Windows filesystems, atomic file replacement using temporary files (`os.replace`) fails with `PermissionError: [WinError 32] The process cannot access the file because it is being used by another process` if a concurrent worker thread reads the file without lock coordination.
- **Pitfall:** Omitting read locks on hot configuration or persona files causes sporadic WinError 32 crashes during background agent updates or settings changes.

### 32. SSRF Guarding on Multimodal Web Image Retrieval
- Image search tools, thumbnail proxies, and media enrichers must validate candidate URLs against private, loopback, link-local, multicast, and cloud metadata IP addresses (`socket.getaddrinfo` / `ipaddress.ip_address`) before issuing network requests.
- Validate that URL schemes are strictly `http` or `https`, and reject internal hostnames (`localhost`, `127.0.0.1`, `::1`, `metadata.google.internal`).
- **Pitfall:** Unchecked media scrapers allow attackers or malicious prompts to trigger internal network reconnaissance or cloud credential exfiltration via SSRF.

### 33. Remote Tunnel Ingress, Dynamic URL Resolution & WebSocket Token Handshake
- **Zero Localhost Hardcoding in Web Clients:** In web workspace and client adapters, never hardcode fallback URLs to `localhost` (`http://localhost:8000`, `ws://localhost:8000/ws`). When accessing the agent over external tunnels (Cloudflare, ngrok) or custom domains, `localhost` points to the client device's empty port, and modern browsers strictly block mixed-content requests (HTTPS pages calling insecure HTTP/WS). Resolve endpoints dynamically via `window.location` (protocol `wss:` / `https:`, host, matching port or tunnel path).
- **Public Domain vs Localhost Port Isolation:** When dynamically resolving API and WebSocket endpoints in frontend clients, never append backend ports (e.g. `:8000` via `NEXT_PUBLIC_BACKEND_PORT`) when `window.location.hostname` is a public domain or tunnel endpoint (`domain.com`, `sub.domain.com`). Reverse proxies and Cloudflare Tunnels strictly terminate standard HTTPS/WSS (port 443) and route via path ingress rules (`/api/.*`, `/ws.*`). Appending `:8000` to public domains creates unreachable endpoints (`https://domain.com:8000`) that cause connection timeouts and silent client hangs. Restrict port appending strictly to `localhost` or local LAN IP addresses (`127.0.0.1`, `192.168.x.x`, `10.x.x.x`).
- **WebSocket Query-Param Token Propagation:** Browsers cannot set custom HTTP headers (`Authorization: Bearer <token>`) in standard `new WebSocket(url)` connections. When remote gateway security is active, the frontend WebSocket builder must append the session token as a query parameter (`?token=${encodeURIComponent(token)}`), and the backend gateway auth dependency (`require_gateway_auth`) must validate query-param tokens on WebSocket handshakes.
- **Root Layout Gateway Auth Modal Mounting:** Any remote authentication barrier (such as a password modal prompting for the gateway session token) must be mounted in the application's root layout (`layout.tsx`). If unmounted, remote visitors receive silent HTTP 401 rejections and WebSocket failures with zero UI prompt to authenticate, leaving the application frozen on loading screens.
- **Tunnel Domain Dev Origin Registration:** In framework development modes (`next dev`), ensure custom tunnel domains (`domain.com`, `*.domain.com`) are explicitly declared in `allowedDevOrigins` to prevent cross-origin dev server and WebSocket handshake blocks (HTTP 502/403).
- **Pitfall:** Hardcoding `localhost:8000` breaks all remote access with browser mixed-content violations, while appending `:8000` to public tunnel domains creates unroutable requests, and omitting query-param tokens on WebSockets causes silent 401 handshake rejections.

### 34. Server Component Dynamic Directive & Async Cookie Boundaries
- In modern App Router frameworks (Next.js 15+), accessing cookies via `await cookies()` inside a Server Component (`page.tsx`) without an explicit `export const dynamic = "force-dynamic"` directive triggers fatal dynamic server usage bailout errors during prerendering and client-side RSC navigation.
- If cookie values only serve as layout hints (such as sidebar widths) that are already synchronized on the client via `localStorage` or inline CSS custom properties, eliminate the async cookie call entirely and export `page.tsx` as a synchronous component with static defaults. This prevents unnecessary SSR suspensions, dynamic server usage errors, and client hydration failures.
- **Pitfall:** Using `await cookies()` in root page wrappers without dynamic directives causes Next.js to crash with runtime errors pointing directly at `app/page.tsx`.

### 35. Headless Browser CDP & Desktop Window Diagnostic Probes
- When diagnosing live frontend errors on running dev servers where built-in browser automation tools fail due to user profile locks (e.g. `User data directory is already in use` because the user has Brave/Chrome open), do not stall or guess.
- Spawn an isolated headless Chrome instance with an ephemeral `--user-data-dir` and `--remote-debugging-port`, connect via Chrome DevTools Protocol (CDP) WebSocket, and capture live `Runtime.exceptionThrown` and `Log.entryAdded` events.
- If inspecting user-side visual state or desktop-specific browser anomalies (e.g. Brave Shields blocking WebGL/canvas), capture the target window's rect and screen buffer via native OS APIs (PowerShell Win32 `GetWindowRect` and `Graphics.CopyFromScreen`) into an ephemeral scratch image, then delegate to vision subagents for exact error text extraction.
- **Pitfall:** Terminating or attempting to force-navigate the user's primary browser profile disrupts their active session, while guessing at client-side error text wastes round trips.

### 36. Omnichannel Accumulating Tool Progress Bubbles (Reference Gateway Standard)
- In messaging platforms (Telegram, WhatsApp, Discord), users must not be left staring at an opaque "typing..." indicator during multi-step tool execution. Provide full transparency into background operations by streaming an accumulating progress bubble (`tool_progress_grouping="accumulate"`).
- **Fenced Code Blocks for Terminal Commands:** Format shell and PowerShell invocations in native markdown code blocks with language headers:
  ```shell
  netstat -ano | grep 3000
  ```
  ```powershell
  powershell -NoProfile -Command "Get-Process ..."
  ```
  Never output terminal invocations as bare un-highlighted `terminal: <cmd>` text.
- **Human-Phrased Action Verbs & Icons:** Format file inspection, reading, searching, and editing concisely:
  - `📖 Reading <filename> L<offset>-<limit>`
  - `🔍 Searching files for <pattern>`
  - `✏️ Editing <filename>`
  - `📂 Listing <folder>` or `📂 Finding files matching <pattern>`
  - `🌐 Searching web for <query>`
- **Zero Completion Noise:** Never emit trailing `status: "done"` lines (such as `✓ [Action Name]: Complete`). Emitting completion lines doubles the bubble's vertical height with redundant filler and degrades readability. The action line itself serves as the verified execution record.
- **Consecutive Repetition Counter (`(×N)`):** When identical tool actions execute back-to-back (e.g. repeated file chunks or terminal checks), do not append duplicate lines. Update the existing line in-place with a repeat count (`📖 Reading file.tsx L1-100 (×3)`).
- **In-Place Debounced Accumulation:** 
  - On the first tool execution, dispatch a message bubble (`sendMessage`) containing the first tool line.
  - On subsequent tool executions, append the new line and update the existing bubble in-place via debounced editing (`editMessageText`, enforcing a minimum 0.8s gap to prevent HTTP 429 rate limits).
  - Maintain a continuous native typing heartbeat (`sendChatAction(action="typing")`) in parallel throughout the turn.
- **Permanent Audit Trail & Separate Narrative Reply:** Never attempt to delete the progress bubble (`deleteMessage`) upon turn completion. Ephemeral deletion fails during network glitches, and stripping the execution log hides what the agent verified. Leave the accumulated progress bubble permanently in the chat history as the verified audit trail, delivering the final narrative reply as a separate message directly beneath it.
- **Pure Conversational Bypass:** Turns that execute zero tools (e.g. conceptual questions, greetings) must never create a progress bubble, delivering only the final text response.
- **Pitfall:** Emitting `✓ Complete` lines clutters the chat with redundant machine noise, while bare typing indicators hide active work and cause users to suspect an agent freeze.

### 37. Native Media Directives & Voice Note Auto-Dispatch
- When an agent produces media references in response text (`MEDIA:/path/to/file` or `[[audio_as_voice]]` directives), the platform gateway must extract the directive, verify physical existence on disk, dispatch via the platform's native media endpoint (`send_photo`, `send_document`, `send_voice` for PTT voice bubbles), and strip the directive tag from the final chat text.
- Do not leak unparsed `MEDIA:` tags or `[[audio_as_voice]]` directives as raw text to users on messaging channels.
- **Pitfall:** Leaving media directive tags unparsed sends raw disk paths as plain text while failing to deliver the actual audio or image artifacts to the chat interface.

### 38. Multi-Platform Session Identity, IDOR Fencing & Unified Sidebar Filtering
- **Two-Tier Session Identity (`session_id` vs `session_key`):**
  - `session_id` (Physical Run/Transcript ID, timestamped e.g. `YYYYMMDD_HHMMSS_<hex>`): Uniquely identifies a single concrete conversation timeline and turn history stored in SQLite `sessions` and `messages`.
  - `session_key` (Deterministic Routing Address, e.g. `<ns>:<platform>:<chat_type>:<chat_id>`): Represents an inbound channel/thread/user lane in `gateway_routing`. The logical channel key points to the currently active `session_id`. When the user runs `/new`, a fresh `session_id` is minted while preserving the persistent channel `session_key`.
- **Unified SQLite Store with IDOR Origin Controls:**
  - All sessions (Desktop, CLI, Telegram, WhatsApp, Discord) reside in a unified profile database (`state.db`) rather than fragmented silos.
  - Inbound messaging users are strictly fenced by Insecure Direct Object Reference (IDOR) guards: ordinary participants can only list and resume sessions matching their own `chat_id` and user identity.
  - Cross-platform or cross-origin session enumeration (`/sessions all`) and resumption (resuming CLI/Web sessions in Telegram via `/resume <id>`) is strictly guarded behind explicit administrator authorization (`allow_admin_from`).
- **Cross-Process Concurrency Leases (`active_sessions.lock`):**
  - To prevent concurrent write collisions when terminal CLIs, desktop windows, and gateway workers access the same session, enforce an exclusive process lease registry. If another process holds an active write lease, subsequent writers are rejected with `SESSION_NOT_OWNED` to prevent split-brain transcript corruption.
- **Unified Sidebar Hierarchy vs Siloed Tabs (Header Filter Menu Architecture):**
  - In desktop and web client sidebars, avoid fragmenting multi-channel sessions into siloed, isolated navigation tabs (e.g. separate tabs for Code, CLI, Omnichannel/Messenger), which forces continuous tab switching and breaks developer flow.
  - Maintain a unified, workspace-grouped session hierarchy with a persistent **`SESSIONS` section header** and a dedicated **`ListFilter` / sliders icon trigger**.
  - Clicking the trigger opens a high-density Liquid Glass popover menu (`SidebarFilterMenu`):
    - **`Grouping`** (Radio): `Project` (hierarchical tree by `workspace_info.root_path` / `git_repo_root` with synthetic `Home` for detached chats), `Updated` (temporal date buckets: Today, Yesterday, Last 7 days), `Status` (WORKING vs DONE), or `None` (unbucketed flat list).
    - **`Ordering`** (Radio): `Updated` (recency), `Created` (started timestamp), `Tokens` (token volume / context weight), `Status` (urgency), `Cost` (spend).
    - **`Show`** (Checkboxes): Toggle visible row metadata chips (`Tokens` size badges like `71.2k`, `Relative time`, `Channel/Origin badges`, `Git branch`).
    - **`Filters`** (Multi-select): Filter by `Channels/Platforms` (All, Web Studio, Telegram, WhatsApp, CLI), `Projects` (`Home`, `Project Anara`), `Status`, and `Archived`.
    - **`Batch Actions`**: `Expand all` / `Collapse all` folders, `Reset to defaults`.
  - Persist all grouping, ordering, and filter settings in client storage (`localStorage`), updating reactive state smoothly without DOM re-mount thrashing.
  - Inline Lead Badges: Render clean, distinctive SVG platform badges (Telegram, WhatsApp, CLI, Code Studio) directly on each session row so origin provenance is immediately legible without fracturing the sidebar into isolated tabs.
- **Pitfall:** Unifying desktop and messenger sessions into a single un-leased active write tab causes cross-device context collisions, token limit thrashing, and race conditions on pending approvals when the user interacts via phone and computer simultaneously. Conversely, splitting the UI sidebar into rigid, isolated channel tabs prevents developers from jumping between related workspace chats.

### 39. Autonomous Background Self-Improvement Review & Truncated JSON Auto-Repair
- Implement post-turn lifelong learning by spawning an asynchronous background review task after conversation turns to evaluate dual-store memory (`USER.md` for profile/style vs `MEMORY.md` for environment facts) and skill evolution (`SKILL.md` in-place patching).
- Execute the background review pass using a zero-tool evaluation posture (`platform="review"`, `tools=[]`).
- **Truncated JSON Auto-Repair:** Fast auxiliary models frequently truncate output when returning arrays (e.g. `trigger_keywords: ["kw1", "kw2"` with unclosed strings and brackets). Naive regexes that only balance `{` and `}` fail with syntax errors because `[` was left open (`[...}`). Implement stack-based delimiter auto-repair: track unescaped quote parity to close open string literals, strip trailing commas/colons, and balance open `[` and `{` delimiters in reverse stack order before invoking `json.loads`.
- Provide robust JSON extraction that auto-rebalances braces and brackets, and emit a clean receipt (`💾 Self-improvement review: <summary>`) via channel callbacks.
- **Pitfall:** Passing workspace tools into the review pass causes the evaluation model to enter exploratory file-searching loops rather than emitting structured JSON verdicts, while unhandled bracket and quote truncation causes silent JSONDecodeError drops and lost mutations.

### 40. Concurrent Multi-Surface Workspace Concurrency & Worktree Isolation
- When users interact concurrently across multiple surfaces (e.g. Desktop IDE and mobile Telegram bot) mapped to the same repository workspace (`cwd`), unisolated sessions share the live physical filesystem and `.git` index.
- If a task on Telegram mutates files on disk, a concurrent desktop session inspecting git status or directory trees immediately observes those modifications as ground-truth facts, creating context bleed-over and confusing the user into thinking sessions were merged.
- Enforce Git Worktree isolation (`git worktree add`) for concurrent multi-channel tasks in the same project root so each client surface operates in an independent working directory.
- **Pitfall:** Operating concurrent multi-channel sessions in the same working tree without worktree isolation leaks file modifications across separate tasks, corrupting cross-session context.

### 41. WebSocket Session Pinning & Cross-Talk Isolation in Multi-Channel Gateways
- **Blind WebSocket Broadcast Danger:** When multiple client surfaces (Web Studio tabs, Desktop IDE windows) connect to a backend that also drives messaging bots (Telegram, Discord, WhatsApp), broadcasting tool lifecycle events (`agent_action_start`, `agent_action_complete`, `tool_progress`) to all active WebSockets indiscriminately leaks tool executions, file reads, and shell commands across sessions.
- **WebSocket-to-Session Registry:** Map every connected WebSocket to the specific `session_id` it is viewing (`websocket_session_map: Dict[WebSocket, Optional[int]]`).
- **Event Stamping & Scoped Delivery:** Stamp all agent events with the originating `session_id` from the active context variable (`_ACTIVE_SESSION_CV`). In the broadcast hub, verify `if event_sid is not None and ws_sid is not None and ws_sid != event_sid: continue`, dropping foreign events before transmission.
- **Channel-Scoped Initial Reconnect:** On WebSocket connection or reconnection, resolve the default session strictly within the client's own platform scope (`channel='web'` or `'code'`), never adopting the globally latest active session across all channels (which frequently belongs to an external messenger like Telegram).
- **Frontend Timeline Validation:** Frontend WebSocket consumers must inspect `payload.sessionId` and ignore events where `payload.sessionId !== activeSessionId`.
- **Pitfall:** Unfiltered WebSocket event broadcasting causes tools executed in a Telegram chat or background task to suddenly inject "Explored N files, ran M commands" cards directly into a desktop user's active session, creating apparent session ghosting.

### 42. Asynchronous Event-Loop Offloading & Boundary Exclusions for Codebase Scanners
- Tools that scan or search codebases (`glob_find_files`, `grep_search_code`) must never run synchronous recursive filesystem traversals (`os.walk`) directly on the asyncio event loop thread without boundary exclusion rules.
- Always prune non-code and system directories (`AppData`, `.cache`, `node_modules`, `.git`, `.venv`, `.cargo`, `.npm`, `dist`, `build`, temporary folders) before scanning.
- Always offload directory walking to a worker thread pool (`await asyncio.wait_for(asyncio.to_thread(_sync_walk), timeout=10.0)`).
- **Pitfall:** Searching a broad user directory (such as `C:\Users\<user>`) without AppData/cache exclusions and thread delegation locks the asyncio event loop for tens of minutes in synchronous disk I/O, completely freezing API endpoints, WebSocket ping-pongs, and Telegram long-polling daemons.

### 43. Clean Multi-Chunk Delivery & Zero Robotic Part Header Pollution
- When splitting verbose agent responses across platform character limits (e.g. 2000 or 4000 chars on Telegram, 1950 on Discord), never prepend artificial header badges like `📄 [Bagian 1/2]` or `📄 [Part 1/2]` to every chunk unless explicitly requested by the platform contract.
- Artificial part badges degrade human conversation quality and make agent replies look like robotic system dumps.
- Use code-fence-aware semantic splitting along paragraph `\n\n` boundaries, balancing fences across chunk borders, and deliver clean, consecutive chat bubbles naturally without header prefixes.
- **Pitfall:** Enforcing `[Part X/Y]` headers on all split chunks pollutes chat threads with robotic metadata and breaks visual parity with native conversational messaging.

### 44. Resilient DoH Discovery & Host-Preserving Literal IPv4 Fallback Transport
- **Windows TCP Keepalive Deficiency:** On Windows systems, `SO_KEEPALIVE` is disabled by default on new sockets. Long-polling loops or connection pools to messaging endpoints (e.g. `api.telegram.org`) that encounter silent packet drops or half-open TCP states (`CLOSE_WAIT`) can hang indefinitely. Always configure explicit `socket_options` on httpx transports (`SO_KEEPALIVE=1`, `TCP_KEEPIDLE=30`, `TCP_KEEPINTVL=10`, `TCP_KEEPCNT=3`).
- **DNS-over-HTTPS (DoH) Discovery:** Upstream ISPs routinely poison, throttle, or blackhole DNS lookups for messaging platform domains (`api.telegram.org`). Implement dynamic DoH resolution querying multiple providers (Cloudflare `https://cloudflare-dns.com/dns-query` with `Accept: application/dns-json` and Google `https://dns.google/resolve` with `type=A`) to discover legitimate IPv4 literals dynamically, with system DNS and seed IPs (`149.154.166.110`, `149.154.167.220`) as fallback.
- **Host-Preserving Literal IP Routing (`curl --resolve` Parity):** Standard HTTP clients cannot connect to an IP literal directly when HTTPS/TLS is required without triggering certificate hostname validation errors. Subclass `httpx.AsyncBaseTransport` (`TelegramFallbackTransport`): rewrite the request URL host to the target IP, while explicitly preserving `Host: api.telegram.org` and setting TLS extensions `sni_hostname: api.telegram.org`.
- **Sticky IP Routing & Socket Pool Recycling:** Once a fallback IP successfully completes a handshake, cache it as the sticky path so subsequent calls avoid DNS re-discovery latency. If a sticky IP fails, re-walk the fallback list. On connection errors, immediately close and discard the failed transport pool (`await transport.aclose()`) before instantiating a fresh one; retaining poisoned pools leaks file descriptors on Windows until process limits are exhausted.
- **Pitfall:** Connecting directly to `api.telegram.org` via standard DNS causes catastrophic gateway hangs when local ISP DNS is poisoned or IPv6 routes are blackholed, while failing to close failed fallback transport pools causes file descriptor exhaustion.

### 45. Durable Delivery Obligations Ledger (Crash-Survivable Outbox)
- Outbox dispatches across messaging adapters (Telegram, WhatsApp, Discord, Slack) must be recorded in an SQLite ledger (`delivery_obligations`) with explicit state transitions (`pending` -> `attempting` -> `delivered` / `failed`).
- When the gateway daemon restarts, the startup lifecycle must execute a sweep (`sweep_recoverable`) for obligations left in `attempting` or `pending` states from the previous run.
- Replay unacknowledged messages to the target channel with a clear recovery prefix (`♻️ [Pesan terpulihkan — server sempat restart saat pengiriman]`), preventing silent drops of replies during host reboots, container updates, or unhandled exceptions.
- **Pitfall:** Fire-and-forget message dispatches without persistent state tracking permanently drop outgoing replies whenever the daemon restarts or crashes while waiting for LLM completion.

### 46. Canonical Indexed Session Keys vs Ephemeral Session Title Renaming
- Map incoming channel senders (e.g. Telegram chat ID, WhatsApp phone number) to persistent database sessions using unique indexed canonical keys (`session_key = "channel_{platform}_{channel_id}"`), NEVER by matching substring patterns inside session `title` columns.
- Automatic session title summarization models rewrite the `title` field into conversational headings (e.g. "Fixing Docker Compose Networking") after the initial turn.
- If channel matching checks `WHERE title LIKE '%Telegram [12345]%'`, the title change immediately breaks matching on subsequent turns, causing split-brain duplicates where each new user message creates a fresh blank session.
- **Pitfall:** Matching channel sessions on mutable title strings creates duplicate fragmented sessions each time the title summarizer renames a conversation.

### 47. Strong Task References in Long-Polling Loops (Asyncio GC Defense)
- In long-running polling daemons (e.g. Telegram `getUpdates`), background tasks spawned via `asyncio.create_task` must be stored in a module-level strong reference set (`_active_polling_tasks.add(task)`).
- Attach completion callbacks to cleanly discard finished tasks: `task.add_done_callback(_active_polling_tasks.discard)`.
- In modern Python runtimes (3.12+), unreferenced background tasks that yield control during slow I/O or LLM turns risk non-deterministic garbage collection by the event loop, causing silent dropped updates and lost turns mid-flight.
- **Pitfall:** Creating fire-and-forget `asyncio.create_task` inside polling loops without strong references causes intermittent silent drops of user turns under memory pressure.

### 48. Upstream Model API Fault Taxonomy & Jittered Retry Ladder
- Centralize upstream LLM exception handling into a dedicated classifier mapping provider errors to a normalized taxonomy (`rate_limit`, `overloaded`, `server_error`, `timeout`, `context_overflow`, `auth`, `billing`, `format_error`).
- For transient errors (HTTP 429 rate limits, 503 gateway overloads, 504 timeouts), apply quick exponential backoff with jitter (e.g. 1.5s, 3.0s, 6.0s) before falling back to alternative models.
- When encountering HTTP 413 context length errors, trigger automated context compaction rather than blindly retrying the same oversized payload.
- **Pitfall:** Treating all API exceptions as generic errors causes unnecessary downgrades to fallback models on momentary rate-limit blips, or spins in infinite retries on unrecoverable 413 context overflows.

### 49. In-Memory Text-to-File Attachment for Large Pastes
- In web composer interfaces, direct pasting of massive text payloads (> 3,000 characters) into the textarea causes severe DOM layout thrashing, frame drops, and browser UI freezes.
- Intercept the composer `onPaste` event: if the plain text payload exceeds the threshold, prevent default insertion, wrap the text into an in-memory `Blob`/`File` (e.g. `pasted_text_<timestamp>.txt`), and attach it to the composer's file attachment tray with a visual chip.
- Display a toast notice informing the user that large text was converted into an attachment, keeping the input area lightweight and responsive.
- **Pitfall:** Pasting tens of thousands of lines directly into a React textarea locks the main UI thread during layout calculation, often freezing the browser tab completely.

### 51. Post-Split Code Fence Evaluation in Omnichannel Chunkers
- When splitting long agent responses into chunks across platform character limits (e.g. 2000 on Discord, 3500 on WhatsApp, 4000 on Telegram), NEVER compute `ends_inside_code = (code_fence_count % 2 == 1)` on the pre-split window (`candidate = text[:limit]`).
- If `ends_inside_code` is evaluated on `candidate`, but `split_idx` finds a clean paragraph break (`\n\n`) *before* an upcoming code block, the code fence flag is evaluated as `True` even though `chunk_part = text[:split_idx]` does NOT end inside code.
- This defect causes the chunker to inject a spurious closing `\n``` ` into Chunk 1 and a duplicated opening ````{lang}\n``` into Chunk 2, breaking code block formatting on all messaging platforms.
- Evaluate `ends_inside_code = (chunk_part.count("```") % 2 == 1)` strictly on `chunk_part` *after* `split_idx` has sliced the text.
- **Pitfall:** Evaluating code fences on pre-split candidate slices corrupts markdown code blocks whenever paragraph breaks precede code fences near the chunk limit.

### 52. Voice Note Duration Probing & Native OGG Opus Transcoding
- When dispatching voice notes to messaging platforms (such as Telegram `sendVoice`), the client displays `0:00` or fails to render a waveform if duration metadata is omitted.
- Probe whole-second audio duration via standard library `wave` (for `.wav`) or subprocess `ffprobe` (`-show_entries format=duration -of default=noprint_wrappers=1:nokey=1`) and include `"duration": int(duration_secs)` in the multipart payload.
- Telegram strictly requires an OGG container with Opus audio encoding (`audio/ogg; codecs=opus`) for native playable voice bubbles with waveforms. If the source file is `.mp3` or `.wav`, transcode on the fly via `ffmpeg -i input -c:a libopus -b:a 32k output.ogg` into an ephemeral temporary file before dispatch.
- **Pitfall:** Sending raw `.mp3` files without probed duration to `sendVoice` endpoints causes audio clips to render as generic files or display broken `0:00` durations without playable waveforms.

### 53. Thought Part Isolation in Multi-Modal Provider Streaming (Anti-Monologue Leakage)
- In modern LLM SDKs with thinking/reasoning enabled (e.g. Google GenAI / Gemini `thinking_config`), the candidate response stream yields distinct content parts where internal reasoning carries `getattr(part, "thought", False) is True`.
- Never treat all parts possessing a `.text` attribute uniformly as conversational text. If thought parts are concatenated directly into conversational text accumulators, raw internal monologue tokens (e.g. *"Okay, need to figure out how to do this. User wants a repo check..."*) leak into client chat bubbles as unformatted text.
- Inspect `is_thought = getattr(part, "thought", False)` during streaming iteration: wrap thought tokens in explicit `<thought>...</thought>` delimiters or route them directly to dedicated `agent_thinking` event channels. This allows stateful thinking scrubbers (`StreamingThinkScrubber`) to extract reasoning into expandable thinking accordions while guaranteeing that only clean conversational narrative reaches the final chat bubble.
- **Pitfall:** Blindly appending `part.text` to narrative chunks when `part.thought` is True pollutes the user transcript with raw stream-of-consciousness model thoughts, breaking visual polish and conversational immersion.

### 54. Curated Omnichannel Tool Verb Extraction & Browser Step Parsing
- When generating live progress lines for messaging channels (`format_omnichannel_tool_progress`), do not fall back to generic `⚙️ <tool_name>: {json}` strings for high-level agent tools.
- Curate human-phrased action verbs with clean parameter extraction:
  - `browser_exec` / `browser_code`: Parse the leading `# Comment` line of the Python script (e.g. `# Searching Amazon for paper towels` -> `🌐 Searching Amazon for paper towels`) rather than outputting raw Python execution code.
  - `browser_navigate`: Format concisely as `🌐 Browsing <url>`.
  - `delegate_task`: Extract the subtask count and first goal snippet (`👥 Delegating N subtask(s): <goal>`).
  - `todo_list` / `task_scratchpad`: Format as `📋 Updating task checklist`.
  - `vision_analyze`: Format as `👁️ Inspecting visual media`.
  - `text_to_speech`: Format as `🎙️ Generating voice audio`.
  - `computer_use`: Format as `🖥️ Desktop <action>`.
- **Pitfall:** Emitting raw JSON dictionaries or multi-line automation scripts into mobile chat notifications overwhelms users with unreadable machine syntax, whereas curated single-line action verbs provide immediate, legible progress.

### 55. Omnichannel Reasoning Block Presentation & Per-Platform Formatting
- When models produce thinking or reasoning chains (via `<think>`/`<thought>` tags or provider thought parts), do not suppress reasoning entirely or dump it as raw text into the conversation bubble. Format it as an explicit, platform-adapted reasoning block prepended to the final response.
- **Telegram Code Block Standard:** Prepend `💭 **Reasoning:**\n```\n{display_reasoning}\n```\n\n{response}`. When translated to Telegram HTML (`💭 <b>Reasoning:</b>\n<pre><code>...</code></pre>`), the Telegram client renders a distinct muted monospace card with an interactive "Copy Code" button, clearly separating internal contemplation from the final narrative.
- **WhatsApp Blockquote Styling:** Convert to `💭 *Reasoning:*\n> {line}` across each non-blank line of reasoning.
- **Discord Subtext Styling:** Convert to `-# 💭 **Reasoning:**\n-# {line}` so reasoning renders as unobtrusive metadata above the answer.
- **Inner Fence Escaping & Line Capping:** Replace inner triple backticks (```` ``` ````) with triple single quotes (```` ''' ````) inside the reasoning body to prevent premature closure of the outer code block. Cap long reasoning to 15–20 lines with an explicit `\n... (N more lines)` indicator to prevent single-turn messages from consuming the entire mobile screen.
- **Pitfall:** Omitting reasoning blocks hides the agent's analytical rationale and leaves users questioning why certain conclusions were reached, while unescaped inner code fences break message parsing across all chat platforms.

### 56. Headless Chrome CDP Probing for 3D WebGL & Interactive Workbenches
- When diagnosing live frontend rendering, WebGL context, or skeletal 3D animations where standard browser automation tools time out or freeze on canvas render loops, do not guess or stall.
- Launch an isolated headless Chrome instance with an ephemeral `--user-data-dir`, `--enable-webgl`, and `--remote-debugging-port=924x`.
- Connect directly via WebSocket to the page's `webSocketDebuggerUrl` using Chrome DevTools Protocol (CDP):
  1. Enable `Runtime`, `Page`, and `Console` domains.
  2. Evaluate DOM and canvas drawing buffer metrics (`gl.drawingBufferWidth`, `gl.isContextLost()`, non-zero pixel sampling via `gl.readPixels`) to verify active 3D scenes without triggering external screenshot loops.
  3. Probe skeletal bone rotation and position deltas over temporal intervals (e.g. $\Delta t = 1.5\text{s}$) to programmatically verify procedural breathing, natural idle sway, and head tracking.
  4. Capture full viewport base64 screenshots (`Page.captureScreenshot`) and evaluate visual fidelity with vision subagents.
- **Pitfall:** Relying on basic HTTP health checks confirms only that the web server returns 200 OK, failing to detect silent client-side WebGL context loss, frozen Three.js render loops, or invisible avatar meshes.

### 57. Ingress Slash Command Interception (Anti-Tool Hunt Loop)
- Administrative slash commands (`/sessions`, `/resume`, `/help`, `/status`, `/model`, `/approvals`) must be intercepted and resolved at the command hub router *before* forwarding inbound messages to the agent ReAct loop.
- If an unhandled slash command slips past into an LLM agent loop, the model treats the slash token as a technical task or codebase instruction, initiating a destructive "tool hunt loop" (e.g. running shell commands, executing Python scripts to inspect SQLite tables, reading `SKILL.md` files, or attempting `--help` CLI flags).
- For session management commands (`/sessions` and `/resume [id]`), return clean formatted channel responses and attach platform-native interactive widgets (e.g. Telegram inline keyboard buttons `🔄 #ID Title` with callback data `resume:<id>`) to enable 1-tap session switches without manual typing.
- **Pitfall:** Failing to intercept slash commands at the ingress gateway causes the model to hallucinate that the command is a technical assignment, executing arbitrary read/write tools against local databases and file structures.

### 58. Intercepted Tool Payload Sanitization & Thought Tag HTML Entity Defense
- When a mutating tool call is intercepted by a safety gate (`intercepted: True`), the gateway channel adapter must NEVER serialize the raw Python dictionary (`{'intercepted': True, 'tool_name': ...}`) to a string or leak it to user chat.
- Thought tags (`<thought>...</thought>`) inside `lead_text` must be scrubbed using `_clean_model_chat_text()` before passing to approval renderers. Raw thought tags expose internal monologues, and in HTML parse mode (e.g. Telegram `parse_mode="HTML"`), the Telegram Bot API rejects unsupported `<thought>` tags with HTTP 400 (`Bad Request: can't parse entities: Unsupported start tag "thought"`), triggering plain-text fallback or failed deliveries.
- Approval payload renderers must format tool parameters safely: shell commands as ````shell\n<cmd>\n````, code snippets (`execute_code`) as ````python\n<code>\n````, file paths as `Target: <path>`, and synthesize clean fallback narration if model rationale is absent or malformed.
- **Pitfall:** Leaking raw interception dictionaries outputs internal runtime plumbing to the user, while unscrubbed `<thought>` tags crash Telegram HTML entity parsers with HTTP 400.

### 59. ASGI Gateway Hot-Reloading Discipline in Local Development Launchers
- When launching long-lived backend and omnichannel gateway servers in local development environments, always launch the ASGI server with explicit reload directories (e.g. `uvicorn <module>:app --reload --reload-dir backend`).
- Running without auto-reload leaves the gateway executing stale in-memory bytecode in RAM from hours or days prior. Newly added slash command handlers, tool patches, and router updates are completely ignored on live messaging channels while source files on disk appear correct, misleading developers into duplicate debugging cycles.
- **Pitfall:** Omitting `--reload` on development launchers causes running daemon processes to silently execute obsolete bytecode, masking newly implemented features and bug fixes.

### 60. Canonical Session Listing, 1-Based Index Resolution & Native Command Quote Replies
- When implementing administrative `/sessions` and `/resume` commands on messaging gateways, format the list cleanly:
  - Header: `📋 Named Sessions` for default, `📋 Sessions` for `all` or `full`.
  - Item structure: `{index}. {title}{current_marker} — {session_key} — _{snippet}_`.
  - In cross-chat listings (`/sessions all`), non-admin users must be scoped to the originating chat with a clear security notice (`Note: all (cross-chat listing) requires a configured admin; showing this chat's sessions only.`).
- **1-Based Index Resolution in Resuming:**
  - In `/resume [arg]`, if `arg` is a small integer (e.g. `1`, `2`, `3`), resolve it to the 1-based index from the active session listing before attempting fallback to raw numeric database IDs or canonical string keys.
  - This allows mobile users to resume threads by typing single digits (`/resume 2`) without copying 24-character timestamp hashes.
- **Native Command Quote Replies:**
  - Administrative slash command responses delivered to messaging platforms (such as Telegram) should pass `reply_parameters={"message_id": incoming_message_id}` so the output quotes the user's command prompt.
  - This provides clear visual pairing between the user's command and the bot's system output in busy chat timelines.
- **Single-Pass Entity Escaping vs Double-Escape Bugs:**
  - Never pre-escape angle brackets (`&lt;...&gt;`) in command template strings when passing through an outbound platform formatter that applies entity escaping (`&` -> `&amp;`, `<` -> `&lt;`). Pre-escaping causes `&lt;` to transform into `&amp;lt;`, displaying literal `&lt;session id&gt;` on client screens.
- **Pure Italic Formatting Without Literal Underscores:**
  - Do not combine HTML italic tags with Markdown underscores (`<i>_{text}_</i>`), which renders visible literal underscores around italic words. Use pure `<i>{text}</i>` or pure `_{text}_`.
- **Session Scope Semantics (`/sessions` vs `/sessions full` vs `/sessions all`):**
  - `/sessions`: Named sessions only, filtering out untitled threads (`title is not None and title != '—'`).
  - `/sessions full`: Unfiltered listing including unnamed threads (`title is None or title == '—'`). When all sessions are named, `/sessions` and `/sessions full` produce identical outputs by design.
  - `/sessions all`: Cross-chat scope, guarded by admin authentication.
- **Pitfall:** Omitting 1-based index mapping forces mobile users to manually copy/paste long session hashes, while failing to quote command messages leaves system outputs visually dislocated from the command trigger. Pre-escaping template brackets causes double-escaping artifacts (`&lt;session id&gt;`), and combining HTML tags with Markdown underscores leaves raw underscores visible in client message bubbles.

### 61. Two-Tier Gateway Slash Authorization & Channel Session Auto-Titling Gates
- **Two-Tier Access (`allow_from` vs `allow_admin_from`):**
  - Distinguish explicitly between general bot chat allowlists (`allow_from`) and privileged administrative rights (`allow_admin_from`).
  - Being allowed to chat with a bot does not confer rights to view or resume sessions originating from other chats or platforms.
  - Cross-origin session enumeration (`/sessions all`) and cross-chat session resuming (`/resume --all`) must require membership in `allow_admin_from` (or fail closed with an informative notice: `Note: all (cross-chat listing) requires a configured admin; showing this chat's sessions only.`).
  - Failing to separate these tiers creates an Insecure Direct Object Reference (IDOR) vulnerability where any permitted chat participant can enumerate conversation histories and token previews across the entire agent gateway.
- **Channel Session Auto-Titling Gate on Generated Prefixes:**
  - Dynamic session summarizers that name conversations based on the initial dialog turns must treat default channel placeholders (e.g. `Telegram Chat (Name) [telegram:12345]`, `channel_telegram_...`, or names ending with `]`) as replaceable placeholders.
  - Restricting the placeholder check solely to `"New Chat"` or `"Session"` causes sessions originating from messaging channels to remain permanently locked to their initial channel metadata tag, preventing the LLM summarizer from assigning meaningful conversation topics.
- **Pitfall:** Conflating `allow_from` with `allow_admin_from` exposes private conversations across all chat lanes, while failing to treat channel-stamped titles as placeholders leaves session lists cluttered with generic channel tags instead of conversational topics.

### 62. Omnichannel Settings UI & Admin Tier Gating Parity in Agent Consoles
- In agent settings consoles and messaging integration dashboards (e.g. Brain Console, Integration tabs), never provide only a single generic "Allowed User IDs" input field.
- Always provide two explicitly distinguished configuration fields:
  1. **Allowed User IDs (`allow_from`):** Whitelists identities permitted to send direct messages to the bot to prevent spam and stranger access.
  2. **Admin User IDs (`allow_admin_from` / `admin_ids`):** Whitelists privileged operators with authority to inspect cross-platform sessions (`/sessions all`), switch remote sessions (`/resume <id>`), alter active LLM providers (`/model`), adjust approval gates (`/approvals`), and execute administrative diagnostics.
- Provide clear explanatory hints directly in the UI making it obvious that being an allowed user does not grant cross-platform session visibility or administrative execution rights.
- **Pitfall:** Omitting an explicit Admin IDs input in the integration UI leads operators to assume configuring Allowed User IDs confers full bot ownership, resulting in unexpected permission denials when running cross-platform management commands.

## Diagnostic Audit Checklist

1. **Secret Redaction:** Are all exception messages wrapped in `redact_sensitive_text()` before logging or outputting to channels?
2. **Callback Ceilings:** Are inline keyboard callback payloads bounded to <= 64 bytes?
3. **Flood Protection:** Does message chunking enforce a maximum split limit and back off on HTTP 429?
4. **Syntax Adaptation:** Are markdown tokens translated to target platform formatting conventions (WhatsApp asterisks, Telegram HTML tags)?
5. **Webhook Cleanup:** Does the polling worker delete lingering webhooks before starting?
6. **Async File I/O:** Are media files read via non-blocking thread workers before upload?
7. **Lifespan Reaping:** Does server shutdown terminate external tunnels, clean up process registry jobs, and checkpoint SQLite WAL pages?
8. **Audio Stream Alignment:** Are PCM buffers even-aligned and silent acoustic frames guarded from false affect classifications?
9. **Intent Classification:** Are approvals and conversational intent evaluated via auxiliary model reasoning rather than static keyword token sets?
10. **Windows Autostart & Global Shims:** Does desktop Windows deployment support dual-path background auto-start (schtasks + startup folder fallback) and cross-shell CLI shims (.cmd + POSIX)?
11. **Terminal TUI Parity:** Does the CLI provide live token streaming, in-place tool spinners with stopwatch, tab-completion, and graceful Ctrl+C cancellation?
12. **Chat & Reasoning UX:** Is model reasoning persisted post-turn in expandable accordions, is auto-scrolling gated against hijacking, and are tool starts appended without overwriting?
13. **IDE Viewport & Resizing:** Does the editor offer an explicit Code-to-Diff toggle, multiset diff counting, and ref-backed persistent panel resizers?
14. **Platform Channel Propagation:** Does every ingress runner explicitly pass `channel` down to system prompt assembly to prevent terminal/web identity hallucination?
15. **Omnichannel Clarification:** Are interactive questionnaires hooked directly to platform-native keyboards/buttons with matching callback parameter arity?
16. **Session ID Binding:** Does the channel gateway propagate the resolved `session_id` into slash command requests to prevent split-brain inspection?
17. **Tool Posture Completeness:** Are workspace switching and configuration tools retained in `CODING_TOOLS` with fuzzy path resolution to prevent deflection loops?
18. **CLI Argument & Terminal Resilience:** Does the CLI runner decouple direct prompts from subcommands to prevent `invalid choice` crashes, adapt terminal outputs safely against `NoConsoleScreenBufferError` in mintty/Git Bash, and use native async prompts in event loops?
19. **Model Catalog & Discovery Resilience:** Does model discovery provide sufficient timeout headroom (>=15s) for bulk catalogs, account for DB hidden model pruning, avoid silent CLI presentation slicing, acquire async locks properly, and enforce SSRF/DNS rebinding defense on remote resource fetching?
20. **Streaming Send/Recv Supervisor:** Are full-duplex WebSocket streaming tasks managed via `asyncio.wait(FIRST_COMPLETED)` with sibling cancellation, and are supervisor running flags preserved on recoverable disconnects?
21. **Non-Blocking Tunnel Download:** Are binary downloads offloaded to worker threads with lazy-initialized async locks to prevent event loop freezes and cross-loop errors?
22. **Cross-Platform Slash Markup:** Are dynamic inputs in slash commands escaped against HTML injection, and are HTML tags automatically normalized to Markdown/plain text on CLI, Discord, Slack, and WhatsApp?
23. **Group Admin Fencing:** Are sensitive callbacks (model selection, voice mode, destructive tools) restricted to authorized administrators in group chats?
24. **Wizard De-bouncing:** Are interactive questionnaire callbacks guarded against double-tap state desynchronization and array out-of-bounds errors?
25. **HTML Error Escaping:** Are exception traces and error notices escaped via `html.escape()` before dispatching in Telegram HTML parse mode?
26. **Chunk Failure Propagation:** Do multi-chunk messaging loops halt immediately upon intermediate chunk errors to avoid false success reporting?
27. **Awaited Telemetry:** Are event bus dispatches awaited directly rather than spawned as untracked, GC-vulnerable background tasks?
28. **Pre-Flight Upload Ceilings:** Are physical file sizes inspected on disk before allocating RAM buffers or dispatching media attachments?
29. **WebSocket Task Lifecycle:** Are background tasks tracked in a session set and cancelled on disconnect with disconnect-immune send wrappers?
30. **Chat Stream Action Resolution:** Are pending plan approvals explicitly transitioned in the state manager and evaluated asynchronously?
31. **Atomic File Read Locks:** Are dynamically updated markdown and config files protected by read/write locks against Windows WinError 32 sharing violations?
32. **Multimodal SSRF Defense:** Are external media URLs validated against private and cloud metadata IPs before fetching?
33. **Remote Tunnel & WebSocket Token Handshake:** Are API and WebSocket endpoints resolved dynamically via `window.location` without `localhost` hardcoding, and are gateway tokens appended as query parameters on WebSockets and validated by backend auth?
34. **Gateway Auth Modal Mounting & Allowed Dev Origins:** Is the remote gateway login modal mounted in the root layout to prevent silent 401 locks, and are tunnel hostnames registered in `allowedDevOrigins`?
35. **Public Domain vs Localhost Port Isolation:** Are port numbers excluded when constructing URLs on public domains/tunnels so requests route through standard reverse proxy ports (443)?
36. **Server Component Dynamic Directives:** Are `await cookies()` calls in App Router root pages either accompanied by `export const dynamic = "force-dynamic"` or converted to synchronous components with static defaults to prevent dynamic server usage crashes?
37. **Headless CDP & Window Probes:** Are locked user profiles diagnosed using isolated ephemeral headless Chrome instances or native window capture rather than guessing at client errors?
38. **Accumulating Progress Bubbles:** Does the messaging gateway stream tool executions into an in-place debounced progress bubble using fenced code blocks for terminal commands, human-phrased action verbs, zero completion noise, and consecutive repeat counters `(×N)`?
39. **Native Media Auto-Dispatch:** Are `MEDIA:` and `[[audio_as_voice]]` tags parsed and dispatched natively via platform media endpoints with clean tag stripping from outbound text?
40. **Source-Scoped Session Slicing:** Are external messaging sessions partitioned with dedicated source-scoped session keys and sidebar slices separate from local desktop sessions to prevent multi-device split-brain collisions?
41. **WebSocket Session Isolation:** Are WebSocket connections bound to specific session IDs and are broadcasted tool events filtered to prevent cross-session event leakage?
42. **Non-Blocking Codebase Searches:** Are filesystem search tools offloaded to worker threads with timeout bounds and system directory exclusions (`AppData`, `.cache`, `node_modules`) to prevent event loop freezes?
43. **Truncated Review JSON Auto-Repair:** Does the background review parser track quote parity and stack-balance unclosed brackets `[` and braces `{` to prevent silent JSON decode drops?
44. **Zero Part Header Pollution:** Does message chunking deliver long responses across natural paragraph/fence boundaries without injecting artificial `[Part X/Y]` or `[Bagian X/Y]` badges into conversational bubbles?
45. **Resilient DoH Transport:** Does the messaging gateway enforce TCP keepalive on Windows sockets, resolve platform APIs via DNS-over-HTTPS, route through IPv4 literals with preserved Host/SNI headers, and recycle failed transport pools?
46. **Durable Delivery Ledger Outbox:** Are outgoing messages recorded in persistent SQLite ledger tables and auto-swept upon gateway reboot to prevent message drops during crashes?
47. **Canonical Session Keys:** Are multi-platform inbound sessions mapped through unique indexed `session_key` strings rather than matching mutable session titles that change during auto-titling?
48. **Strong Polling References:** Are background coroutines in polling workers retained in module sets to prevent non-deterministic garbage collection during long-running tasks?
49. **Upstream Error Taxonomy & Backoff:** Are upstream LLM exceptions classified with retry ladders for transient 429/503 errors and auto-compaction for 413 context overflows?
50. **Large Paste In-Memory Attachment:** Does the web composer intercept pastes exceeding 3,000 chars and convert them into in-memory file attachments to eliminate DOM layout thrashing?
51. **Post-Split Code Fence Evaluation:** Is `ends_inside_code` evaluated strictly on the sliced `chunk_part` rather than the pre-split candidate slice to prevent spurious fence injections at paragraph splits?
52. **Voice Duration & Opus Transcoding:** Does voice note dispatch probe duration with `wave`/`ffprobe` and transcode `.mp3`/`.wav` to OGG Opus via `ffmpeg` to prevent `0:00` display and non-rendering waveforms?
53. **Thought Part Isolation:** Are model reasoning parts (`part.thought == True`) segregated from conversational narrative chunks and routed to dedicated thinking event channels to prevent internal monologue leakage?
54. **Curated Tool Verb Extraction:** Does omnichannel progress formatting extract human-readable action labels (such as `# Comment` headers in browser automation and goal snippets in delegation) rather than outputting raw JSON argument dumps?
55. **Slash Command Ingress Interception:** Are administrative slash commands (`/sessions`, `/resume`, `/help`) intercepted and resolved before passing to the LLM loop to prevent destructive tool hunt loops?
56. **Approval Interception Sanitization:** Are intercepted tool payloads sanitized against raw dictionary leaks, thought tags stripped before Telegram HTML parsing, and arguments formatted in clean code blocks?
57. **ASGI Hot-Reloading:** Do development launch scripts run the gateway server with `--reload --reload-dir` to prevent stale bytecode execution in RAM across code edits?
58. **Canonical Sessions & Index Resolution:** Does `/sessions` format items with canonical keys and snippets, support 1-based index resolution on `/resume`, and deliver command responses via native quote replies?
59. **Command Escaping & Sessions Semantics:** Are command usage examples written with raw brackets (`<id>`) rather than pre-escaped entities (`&lt;id&gt;`) to prevent double-escaping, are italics free of literal underscores, and does `/sessions` cleanly distinguish named vs full/unnamed listings?
60. **Two-Tier Slash Authorization & Channel Title Gates:** Are cross-chat session listings restricted strictly to explicit admin lists (`allow_admin_from`) rather than general user whitelists (`allow_from`), and do session auto-titlers treat channel-prefixed session titles as replaceable placeholders?
61. **Omnichannel Settings UI Admin Parity:** Does the integration settings console provide separate, clearly documented input fields for both Allowed User IDs (`allow_from`) and Admin User IDs (`allow_admin_from`), preventing confusion between chat access and cross-platform administrative privileges?
