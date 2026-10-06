---
category: autonomous-ai-agents
name: agent-lifecycle-engineering
description: Use when auditing agent skills and process supervision.
---

# Agent Lifecycle Engineering

Use this skill when auditing, designing, implementing, or hardening agent skill lifecycles, autonomous skill distillation, and background process supervisors.

## 1. Skill Lifecycle & Storage Invariants (Anara Parity)

### Root Directory Traversal & Wipe Prevention
- In skill deletion (`uninstall_skill`, `reject_skill`), sanitize the slug string and reject empty strings, whitespace, `.`, `/`, or `\\`.
- Verify that `(root_dir / slug).resolve() != root_dir.resolve()` and `target_dir.is_relative_to(root_dir)`.
- Enforce that the target directory is a leaf skill folder containing its own `SKILL.md` (`(target_dir / "SKILL.md").is_file()`). Never delete a category bucket directory (e.g. `skills/productivity/`) that groups multiple child skills.

### Multi-Vector Threat Scanning (Anara `skills_guard` Parity)
Scan all candidate skill markdown and script payloads against:
1. **Prompt Injections:** Instruction overrides (`ignore previous instructions`), role hijacking, system prompt overrides, and HTML comments (`<!-- ... -->`).
2. **Secret Exfiltration:** Environment token theft (`curl $KEY`, `wget $TOKEN`), attempts to read `.env`, `.ssh/id_rsa`, `.aws/credentials`, or DNS exfiltration.
3. **Host Destruction & Reverse Shells:** `rm -rf /`, drive formatting, `nc -e`, `/dev/tcp`, `powershell -enc`, `certutil -urlcache`.
4. **Persistence Tampering:** Modifications targeting `AGENTS.md`, `CLAUDE.md`, or runtime agent configuration files.

### Category Subfolder Resolution in Skill Lifecycle
- When approving, rejecting, toggling, or reading skills, resolve actual directory paths dynamically via registry lookup (`get_skill(slug)`) rather than assuming flat placement under `root_dir / slug`.
- Skills organized under category buckets (`skills/software-development/test-driven-development/`) fail to resolve when looked up as top-level paths under `root_dir`.
- **Pitfall:** Constructing paths via `os.path.join(self.root_dir, slug)` causes `approve_skill` and `reject_skill` to return `False` or fail deletion for all categorized skills.

### Safe Procedure Step Formatting
- Never use greedy numeric stripping (`s.lstrip("0123456789. ")`) when compiling Markdown step procedures.
- Greedy stripping deletes legitimate numeric content from the beginning of step instructions (e.g. `"1. 10 unit tests..."` becomes `"unit tests..."`). Use targeted line-prefix regex (`re.sub(r'^\d+\.\s*', '', s.strip())`) to strip only the list enumeration marker.
- **Pitfall:** `lstrip` with digit characters corrupts technical thresholds, port numbers, and quantitative guidance in generated skill markdown.

### Threat Scanner Case-Insensitivity & Windows Reserved Names
- Threat scanning pipelines that lowercase target content (`content.lower()`) must match against lowercase patterns (e.g. `agents\.md|claude\.md|\.anara[/\\]config\.yaml`). Using uppercase patterns like `AGENTS\.md` against lowercased text causes regexes to never match, allowing hostile configuration overrides.
- Slug generators must guard against Windows device reserved names (`con`, `prn`, `aux`, `nul`, `com1..9`, `lpt1..9`) by suffixing `_skill` to prevent WinError 87 filesystem crashes on Windows hosts.

### Split-Brain Memory Deduplication
Autonomous skill extractors running on task completion traces must query BOTH:
- The filesystem runtime skill catalog (`skill_library.list_skills(status_filter="all")`).
- The persistent database table (`memory_engine.get_all_agent_skills()`).
Checking only the database leads to overwriting pristine bundled skills on disk. Avoid calling `list_skills` twice back-to-back; cache the listing locally during deduplication.

### Zombie Skill Resurrection Prevention
In template synchronization engines (`skills_sync`):
- If a bundled skill is recorded in `.bundled_manifest` but missing on disk, it was intentionally deleted by the user. Do NOT re-seed it automatically.
- Only seed skills that are completely unknown to the manifest.

### Full-Scope Skills Sync Concurrency Serialization
- Synchronization between in-tree repository templates and runtime skills storage must be protected by a process/thread lock (`threading.Lock`).
- Verify lock scope bounds the entire manifest reading, directory discovery, file copying/staging, and manifest writing loop.
- **Pitfall:** Placing `with _SYNC_LOCK:` only around directory path resolution and exiting before the manifest read and file copy loop leaves filesystem mutations and `.bundled_manifest` updates unprotected against concurrent worker threads, leading to `FileExistsError` crashes and corrupted manifest states.

### Atomic File Mutation & Resource Limits
- Write all skill modifications atomically using temporary file replacement (`os.replace`) to prevent zero-byte truncation.
- On Windows, read-only git checkout files crash `shutil.rmtree`. Implement an `onerror` handler that grants `stat.S_IRWXU` before retrying deletion.
- Enforce a maximum file byte ceiling (`f.read(MAX_SKILL_FILE_BYTES)`) when parsing `SKILL.md` frontmatter and bodies rather than unbounded `f.read()`, preventing memory exhaustion when indexing hostile markdown files.

### Targeted In-Place Skill Patching vs Duplicate Accumulation (Anara Parity)
- When lifelong learning engines or post-turn reviewers identify updated techniques, command flags, or new pitfalls for existing skills, NEVER discard them as duplicate entries and NEVER accumulate redundant unreviewed copies (`skill-copy`, `skill-2`).
- Implement targeted in-place patching (`patch_skill(slug, old_string, new_string)`) enforcing occurrence verification (rejecting ambiguous multiple matches without `replace_all=True`), atomic temporary file replacement, content safety scanning (`validate_skill_content_safety`), and automatic `updated_at` frontmatter synchronization.

### Autonomous Background Self-Improvement & Continuous Learning Engine
- Post-turn reflection loops evaluating conversation history must execute asynchronously in isolated daemon tasks/threads to avoid delaying user responses.
- The evaluation pass must operate under a zero-tool posture (`platform="review"` / empty tool definitions) to prevent auxiliary evaluator models from initiating runaway workspace inspection or recursive tool-use loops.
- Enforce strict Dual-Store Memory Routing:
  - `USER.md` (target `user`): Persona expectations, user communication style (e.g. casual informal tone), and behavioral preferences.
  - `MEMORY.md` (target `memory`): Durable environment facts, paths, tool quirks, and project conventions.
  - `SKILL.md`: Procedural workflows, concrete execution sequences, and generalizable pitfalls.
- Chat cleaning filters stripping leading/trailing markdown fences or structural brackets from LLM responses must be counteracted by resilient JSON bracket balancing and object reconstruction (`_extract_review_json`) prior to deserialization.
- Emit clean single-line audit receipts (`💾 Self-improvement review: <summary>`) upon successful mutation across all messaging channels (Telegram, WhatsApp, Discord, CLI) to maintain transparent lifelong learning telemetry.

## 2. Background Process Supervisor Invariants (Anara Coding Agent & Anara Parity)

### POSIX Process Group Isolation
- Always pass `start_new_session=True` to `subprocess.Popen` on POSIX.
- When terminating process trees, verify `pgid != os.getpgrp()`. Never issue `os.killpg()` against the parent server's process group.

### PID Recycling Collision Protection
- Capture kernel process start ticks (`GetProcessTimes` on Win32, `/proc/<pid>/stat` field 22 on Linux) at spawn.
- Verify PID liveness AND compare start ticks before issuing termination commands (`taskkill` / `killpg`) to avoid killing innocent host processes that inherited the recycled PID.

### Win32 STILL_ACTIVE (259) False Liveness Trap & 64-Bit Ctypes Argtypes
- On Windows, `GetExitCodeProcess` returning `259 (STILL_ACTIVE)` does NOT guarantee the process is alive; an application that explicitly exits with code `259` will permanently appear alive.
- Check liveness using `WaitForSingleObject(h_proc, 0) == WAIT_TIMEOUT (0x102)` instead of relying on exit code alone.
- Set explicit ctypes calling signatures (`argtypes` and `restype`) on 64-bit Windows kernel calls:
  ```python
  k32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
  k32.OpenProcess.restype = ctypes.c_void_p
  k32.CloseHandle.argtypes = [ctypes.c_void_p]
  k32.CloseHandle.restype = ctypes.c_int
  k32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
  k32.WaitForSingleObject.restype = ctypes.c_uint32
  ```
  Omitting `argtypes` on 64-bit Python causes handles with high-order bits set to be truncated as 32-bit `c_int`, triggering access violation crashes.
- Wrap all Win32 handle operations in `try ... finally: k32.CloseHandle(h_proc)` to prevent kernel handle exhaustion across continuous monitoring cycles.

### POSIX `/proc/[pid]/stat` Space-in-Command Parsing
- Under Linux `/proc/[pid]/stat`, the process executable name (`comm`, field 2) is enclosed in parentheses and can contain whitespace (e.g. `(python worker)`). Never parse with a bare `.split()`. Slice after the last closing parenthesis: `raw[raw.rfind(")") + 2:].split()`. `fields[0]` is state, `fields[19]` is starttime.

### Windows Process Tree Reaping
- On Windows, child processes detach or reparent to `null` if their launcher crashes. Terminate child processes and their entire tree using `taskkill /F /T /PID <pid>` to prevent lingering handle locks.

### Zero-OOM Reverse Chunk Log Tailing
- Never load entire log files via `f.readlines()`.
- Use reverse block-seeking (`os.SEEK_END`, reading backwards in 8KB chunks) to retrieve the last N lines in constant memory. Ensure loop chunk parameters match function signature names (`block_size` vs undefined `buffer_size`) and log errors rather than swallowing silently with `pass`.

### Parent Descriptor Hygiene
- Immediately close the opened log file handle in the parent process after passing it to `Popen`, avoiding file descriptor exhaustion.

## 3. Telemetry & Redaction Sentinels

### Windows Rotating File Handler Rollover Backoff
- On Windows, open file handles from concurrent threads or scanners trigger `PermissionError` (WinError 32) when `doRollover()` renames the active log file. Enforce a cooldown timer (e.g. 30s) before attempting rollover again (`self._next_rollover_retry = now + 30.0`) to prevent disk thrashing.

### Secret Redaction Boundary Protection
- Never use unanchored, broad regex patterns like `key=[^&\s]+` in telemetry scrubbers. This aggressively corrupts legitimate Python keyword arguments (`key=item_name`) into `key=[REDACTED]`.
- Anchor query parameters to query string delimiters: `(?<=[?&])(token=|api_key=|key=|password=)[^&\s]+`.
- Variable-width look-behinds like `(?<=[?&]|\b--|\b-)` raise `re.PatternError: look-behind requires fixed-width pattern` in standard Python. Split into separate fixed-width patterns or non-capturing groups.
- When logging exception objects (`{e}`) during API retries or failover events, always pass error strings through a credential sanitizer (`re.sub(r'(?:key|token|api_key)=[^\s&"\']+', r'key=[REDACTED]', str(e))`). HTTP client exceptions often embed full request URLs with sensitive query strings, leaking raw API keys into log files.

### Fail-Safe Directory Confinement Exception Handling
- When verifying path confinement (e.g. `file_path.resolve().is_relative_to(root.resolve())`), never catch exceptions and `pass` silently.
- On Windows cross-drive operations or invalid paths, path resolution can raise `ValueError` or `RuntimeError`. Swallowing the exception permits out-of-boundary access to proceed to reading the target file.
- Always implement fail-safe handling: if path resolution or confinement verification raises an exception, immediately reject the access and return the default fallback.
