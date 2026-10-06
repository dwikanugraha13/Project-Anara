---
category: autonomous-ai-agents
name: agent-guardrails-and-sandboxing
description: Use when designing agent safety, sandboxing, or guards.
---

# Agent Guardrails and Sandboxing

Use this skill when implementing, auditing, or hardening execution guardrails, shell command sandboxes, filesystem sentinels, and loop breakers in autonomous AI agents.

## Core Security & Reliability Principles

### 1. Shell AST Classification & Isolated Security Guardians
- Analyze shell pipelines by tokenizing commands and unwrapping nested execution wrappers (`sudo`, `sh -c`, `bash -c`, `cmd /c`, `powershell -Command`).
- Exclude file descriptor stream duplications (`2>&1`, `>&-`) from write redirection detection so stderr capture does not escalate read-only commands to mutating.
- When pre-sanitizing shell commands to prevent false positives in commit messages (`git commit -m "..."`), strip ONLY commit message flags (`-m`, `--message`) and `echo` string literals. Never strip all quoted strings globally (`_strip_quoted_strings`); doing so strips quoted target paths (e.g. `rm -rf ".git"`, `del "db.sqlite"`), blinding regex pattern matchers and allowing destructive commands to bypass execution barriers.
- After stripping commit messages, match takeover patterns strictly against the cleaned/normalized command. Never fall back to testing the raw unstripped command string (`cmd_raw.lower()`); doing so completely negates commit message stripping, causing benign commits with words like 'drop database' or 'rm -rf' in the message to be falsely blocked.
- When invoking an auxiliary LLM classifier to evaluate command safety (Anara `approval_smart.py` parity):
  - Keep the system prompt strictly static and immutable (security policy).
  - Strip shell comments (`# ...`) before tokenization to block hidden instruction hijacking.
  - Enclose the untrusted command inside structured user prompt tags: `<command>\n{clean_command}\n</command>`.
  - Use exact word boundary matching for verdict tokens (`r"\b(APPROVE|DENY|ESCALATE)\b"`).
- **Pitfall:** Formatting raw shell strings into system prompt templates causes prompt injection, and naive substring matching (`"APPROVE" in res`) misinterprets "I CANNOT APPROVE THIS" as an approval verdict. Global quote stripping transforms `rm -rf ".git"` into `rm -rf ""` which bypasses file targeting regexes.

### 2. Argument-Aware Cycle & Stagnation Detection
- Track agent action history with canonical argument hashes (`(tool_name, target, sha256(canonical_args)[:8])`) rather than bare tool/target pairs.
- Exclude non-test inspection commands (`git checkout`, `cat test.py`, `grep`, `echo`, `ls`, `dir`, `head`, `tail`, `less`, `find`, `rg`) from test execution verification counters, even if arguments contain words like `test` or `check` (e.g. `ls tests`).
- **Pitfall:** Matching only `(tool_name, target)` falsely flags legitimate test-driven bug fixing as an infinite stall loop, while classifying `ls tests` as a test execution command allows any command returning exit code 0 to falsely satisfy the Negative Verification Stop-Gate without executing real automated tests.

### 3. Windows NT & UNC Namespace Pre-Resolution Shielding
- Inspect path strings for Windows NT object manager prefixes (`\??\`, `\\.\`, `\\?\UNC\`, `\\<host>\`) on the raw string *before* calling `Path.resolve()` or `os.path.realpath()`.
- Reject any NT or remote UNC path immediately before resolution.
- **Pitfall:** Calling `Path.resolve()` on an unvalidated UNC path on Windows causes the OS kernel to initiate outbound SMB network negotiation, leaking NTLM authentication hashes to remote rogue servers.

### 4. Bidirectional Filesystem Confinement & Credential Shielding
- Restrict file modifications (`write`, `edit`, `delete`) to the authorized workspace root and runtime temporary scratchpads.
- Block read access to sensitive credential stores (`.env*`, `.git-credentials`, `id_rsa`, `id_ed25519`, `id_ecdsa`, `id_dsa`, `.netrc`, `.aws/`, `.ssh/`, `.docker/`, `.kube/`) to prevent secret exfiltration through conversational prompt injection.
- For post-write ground-truth verification, read back raw physical bytes from disk to confirm changes landed, but avoid failing valid 0-byte initializations (e.g. empty `__init__.py`). Normalize CRLF (`\r\n`) and LF (`\n`) across both physical disk contents and expected code snippets when comparing on Windows hosts.
- **Pitfall:** Protecting only write actions allows prompt-injected LLM turns to read `.env` or SSH keys and dump their contents into conversational responses. Comparing unnormalized Windows CRLF disk bytes against LF model-generated snippets causes false-negative write verification failures. Omitting modern SSH keys (`id_ed25519`, `id_ecdsa`) leaves credential stores vulnerable.

### 5. Negative Verification Stop-Gate & Ground-Truth Test Evaluation
- Intercept agent completion when code or configuration files were modified during the turn.
- If no passing test or build verification was executed during the turn, withhold final completion and inject a synthetic verification prompt directing the agent to verify its changes.
- When evaluating physical test output, do not treat logged error substrings (e.g. `ERROR:` or `TRACEBACK`) as test failures when the test runner exited with code 0 (`exit_code == 0`) and the summary confirms all tests passed. Unit tests frequently test error handling, expected exceptions, or logged error messages; treating any appearance of `ERROR:` as an unconditional failure causes 100% passing test suites to be rejected. Only explicit test runner failure summaries (e.g. `=== FAILURES ===`, `FAILED (failures=...)`) or non-zero exit codes should fail ground-truth verification.
- **Pitfall:** Permitting unverified completion leads to confident hallucinations of task completion without real ground-truth validation. Conversely, naive keyword scanning of stdout causes passing test suites that test error handling to be falsely marked as failing.

### 6. Trojan Source Pre-Cleaning & False-Positive Prevention
- When scanning inbound prompts for invisible Unicode or bidirectional Trojan Source characters, strip standard Windows UTF-8 Byte Order Marks (`\ufeff`) prior to checking invisible character sets.
- Notepad and standard Windows editors prepend BOM bytes on save. Testing text containing BOM against raw `INVISIBLE_CHARS` sets causes false-positive prompt injection rejections on benign user code or file pastes.
- **Pitfall:** Flagging `\ufeff` as an adversarial Trojan Source attack blocks legitimate users from pasting code saved from Windows Notepad.

### 7. Reverse Proxy Authorization Bypass Guard
- Local request detection (`is_request_local`) for local developer bypass must inspect `X-Forwarded-For` in addition to direct peer IP and Cloudflare headers (`cf-connecting-ip`).
- Without checking `X-Forwarded-For`, external requests reverse-proxied through a local gateway (e.g. Nginx, Caddy, or dev tunnels) appear as loopback (`127.0.0.1`), completely bypassing gateway authentication.
- **Pitfall:** Checking only `client_host == "127.0.0.1"` allows external internet users behind local reverse proxies to bypass gateway authentication.

### 8. Approval Mode Three-Tier Architecture (Manual / Smart / Off)
- **Canonical Mode Names:** Use `manual`, `smart`, `off` as the three approval modes — never `plan`, `auto`, or `yolo` as canonical mode identifiers. Legacy aliases (`plan` → `manual`, `auto` → `smart`, `yolo` → `off`) may be accepted on input but must be normalized immediately.
- **Hardline Safety Floor (Unconditional, even in Off mode):** Maintain a compiled regex library of catastrophic command patterns (recursive root delete, `mkfs`, `dd` to raw block devices, fork bombs, system shutdown/reboot, `init 0/6`, `systemctl poweroff`) that are ALWAYS blocked regardless of approval mode. The hardline floor runs before any mode-specific logic. Off mode removes approval prompts but never removes the hardline floor.
- **Dangerous Pattern Detection (40+ patterns):** A second tier of compiled regex patterns for risky-but-not-catastrophic commands (recursive delete in non-root paths, `git push --force`, `git reset --hard`, SQL `DROP`/`TRUNCATE`/`DELETE` without `WHERE`, `chmod 777`, pipe-to-shell patterns, cloud metadata endpoint access, Windows `taskkill /F`, `Remove-Item -Recurse -Force`, registry delete). These promote the tool's risk tier to `ask` and trigger approval prompts in Manual and Smart modes.
- **Command Normalization Before Matching:** Strip ANSI escape sequences, collapse backslash-newline continuations, and remove backslash-escapes and empty string literals before running regex patterns. Wrap `sudo`, `env`, `exec`, `nohup`, `setsid`, `time` prefixes into command-position anchors so wrapped invocations are still detected.
- **Smart Mode Guardian LLM Assessment:** In Smart mode, flagged commands are sent to an auxiliary LLM (temperature=0, max_tokens=16) for APPROVE/DENY/ESCALATE classification. The guardian system prompt is static and immutable. Shell comments are stripped before assessment. The command is wrapped in `<command>` XML delimiters with an explicit instruction to ignore embedded directives. Extract verdict via exact word matching, defaulting to `escalate` on empty or ambiguous responses.
- **Mode Behavior Matrix:**
  - *Manual:* All `mutating` and `ask` risk tools are intercepted for explicit user approval.
  - *Smart:* Guardian LLM auto-approves safe commands; risky/uncertain commands escalate to user approval prompt.
  - *Off:* No approval prompts. Only the hardline floor blocks catastrophic commands.

### 9. Approval State Machine Status Integrity
- When clearing approved or executed proposals (`clear_pending`), never unconditionally write `ActionState.REJECTED` to the database ledger.
- Retain the verified state (`APPROVED` or `EXECUTED`) or pass the target transition explicitly (`final_state: Optional[ActionState] = None`) to preserve audit accuracy in SQLite.
- **Pitfall:** Unconditionally updating cleared actions to `REJECTED` marks successfully approved and executed operations as rejected in audit logs and metrics.

### 9. Bounded Reverse Log Tailing & Process Registry Cleanup
- Read daemon process logs from disk using reverse block-seeking (`seek(bytes_to_read, SEEK_SET)`) with consistent `block_size` buffer chunking. Decode UTF-8 incrementally to avoid splitting multibyte sequences across block boundaries.
- Always wrap registry removal and process exit recording in a `finally:` block during process termination (`stop_process`). If the OS process termination (`taskkill` on Windows or `killpg` on POSIX) times out or throws an error, dead PID metadata must still be cleared from the active registry to prevent zombie process entries and leaks.
- **Pitfall:** Using mismatched buffer variable names in block seeking or reading whole log files into memory causes runtime NameErrors and out-of-memory crashes on multi-megabyte daemon logs. Leaving process registry removal outside a `finally:` block strands dead process metadata in memory when termination commands encounter errors.

### 10. Safe Argument Vectors Over Shell String Interpolation
- When invoking host operating system commands or opening application targets, avoid formatting target arguments directly into shell commands executed with `shell=True` (e.g. `cmd.exe /c start "" "{tgt}"`).
- Passing unvalidated strings with `shell=True` permits command injection if the target contains shell metacharacters (`&`, `|`, `;`, `` ` ``, `$`, `>`, `<`, newlines).
- Disallow dangerous shell metacharacters before dispatch and execute via explicit argument vectors with `shell=False`: `subprocess.Popen(["cmd.exe", "/c", "start", "", tgt], shell=False)`.
- **Pitfall:** Formatting target arguments into `shell=True` commands allows prompt-injected targets like `notepad" & calc.exe & "` to break out and execute arbitrary commands in the host shell.

### 11. Canonical Path Pre-Resolution in Destructive Filesystem Tools
- In destructive or modifying filesystem tools (`delete_local_file`, `edit_file`, `write_local_file`), always resolve relative, user-aliased, or fuzzy paths to their canonical absolute target on disk (`resolved = _resolve_path(raw_path)`) *before* validating permissions via `WorkspaceSentinel.validate_file_access(resolved)`.
- Validating the raw unverified path before resolution creates a security bypass: a seemingly safe relative path (e.g. `"file.txt"`) passes inspection, but subsequently resolves to a file outside the workspace root (e.g. on the host Desktop or Documents) where destructive operations land unvetted.
- **Pitfall:** Calling sentinel validation on `raw_path` instead of `resolved` allows files in sensitive user home directories to be deleted or overwritten without sentinel inspection.

### 12. Active Browser Network Route Interception for Anti-SSRF & DNS Rebinding Defense
- Pre-flight DNS resolution of initial URLs (`socket.getaddrinfo`) is insufficient on its own to defend against SSRF in browser automation engines.
- Pre-flight checks suffer from Time-of-Check to Time-of-Use (TOCTOU) DNS rebinding attacks and do not inspect HTTP 301/302 redirects or dynamic subresources fetched by the browser page.
- Attach an active network route interceptor to the browser context or page (`page.route("**/*", handler)`). Re-evaluate the target URL of every outbound request and abort (`route.abort("blockedbyclient")`) requests directed toward loopback, RFC 1918 private subnets, link-local addresses, and cloud metadata endpoints (`169.254.169.254`).
- Allow benign internal browser schemes (`data:`, `blob:`, `about:`) required for rendering while blocking network calls to internal infrastructure.
- **Pitfall:** Relying solely on URL pre-flight validation permits malicious external servers to return 302 redirects to `http://169.254.169.254/computeMetadata/v1/`, leaking cloud IAM credentials and instance tokens.

### 13. Windows Subprocess Tree Reaping & Pipe Transport Teardown
- Terminating timed-out subprocesses on Windows with standard `proc.kill()` terminates only the parent wrapper process; any subprocesses spawned by the script remain orphaned in the background as zombie processes.
- Plain `proc.kill()` does not cleanly close underlying asyncio pipe transports, triggering `ResourceWarning: unclosed transport <_ProactorReadPipeTransport>` on the Windows Proactor event loop.
- On Windows timeout, terminate the entire process tree using `subprocess.run(["taskkill", "/PID", str(proc.pid), "/F", "/T"])`, and always await `proc.wait()` in an enclosing `try...except` block to ensure all pipe transports drain and close cleanly.
- **Pitfall:** Calling `proc.kill()` without process tree termination and `proc.wait()` leaks orphan background processes and exhausts asyncio pipe handles on Windows.

### 14. ZIP Archive Decompression Bomb & Traversal Defense
- In zip extraction or re-archiving tools, enforce a ceiling on total uncompressed byte size (e.g. 200MB) and maximum entry count (e.g. 2,000 files) before unpacking.
- For every entry, check `target_path = os.path.abspath(os.path.join(dest_dir, member.filename))` to ensure `target_path == dest_dir or target_path.startswith(dest_dir + os.sep)` to eliminate Zip Slip path traversal attacks.
- Always wrap temporary zip files in `try...finally:` cleanup blocks so disk storage is not leaked on errors.
- **Pitfall:** Extracting unvalidated ZIP archives exposes the host to Zip Slip arbitrary file overwrite and decompression bomb disk exhaustion.

### 15. Artifact Generation Path Confinement & Atomic Replacement
- When generating file artifacts or documents, sanitize raw filenames via `os.path.basename` and bound output destination folders strictly to authorized roots (session directory, artifacts folder, scratch directory, user home).
- Reject destination paths resolving outside permitted boundaries with structured denial notices.
- Write artifact contents atomically via temporary files (`tempfile.mkstemp` in the target directory) followed by `os.replace` to prevent corrupted 0-byte or partial files on process interruption.
- **Pitfall:** Allowing arbitrary destination folders in artifact generators enables arbitrary file overwrite attacks across the host filesystem.

### 16. Timing-Safe Gateway Route Authentication & Rate Limiting
- Public gateway API endpoints controlling services (e.g. tunnel stop/start, daemon shutdown, session logout) must enforce authentication checks; unauthenticated callers must not be able to trigger service termination.
- For password/secret comparisons, use constant-time comparison (`hmac.compare_digest(a.encode(), b.encode())`) ensuring byte encoding to avoid timing attacks and Python TypeError on non-ASCII characters.
- Implement sliding-window IP rate limiting on login/auth routes to prevent automated brute-force attacks.
- **Pitfall:** Exposing tunnel control routes without auth allows external callers to terminate gateways, while plain string comparison (`==`) leaks credential length and prefixes via timing attacks.
