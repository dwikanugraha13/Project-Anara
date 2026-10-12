"""Anara Approval Guard: hardline floor + dangerous pattern detection.

Pure command classification — no approval state, config reads, or prompting.
Hardline patterns NEVER bypass, even in Off/YOLO mode.
Dangerous patterns trigger approval prompts in Plan and Auto mode.
"""

import re
import logging

logger = logging.getLogger("core.approval_guard")

_RE_FLAGS = re.IGNORECASE | re.DOTALL

# ── Command-position anchor ────────────────────────────────────────────────
# Start-of-command position: start of string, newline, subshell opener,
# optionally consuming sudo/env/exec/nohup wrappers.
_CMDPOS = (
    r'(?:^|[\n`]|\$\()'
    r'\s*'
    r'(?:sudo\s+(?:-[^\s]+\s+)*)?'
    r'(?:env\s+(?:\w+=\S*\s+)*)?'
    r'(?:(?:exec|nohup|setsid|time)\s+)*'
    r'\s*'
)

# Shell names for pipe-to-shell detection
_SHELL_NAMES_RE = r"bash|sh|zsh|ksh|dash"

# ── HARDLINE PATTERNS (unconditional floor — blocked even in Off mode) ──────
HARDLINE_PATTERNS = [
    # Recursive delete of root filesystem
    (_CMDPOS + r'rm\s+(-[^\s]*\s+)*/\s', "recursive delete of root filesystem"),
    (_CMDPOS + r'rm\s+(-[^\s]*\s+)*/', "recursive delete from root path"),
    # Recursive delete of home directory
    (_CMDPOS + r'rm\s+(-[^\s]*\s+)*(?:~|\$\{?HOME\}?)(?:/?|\s)', "recursive delete of home directory"),
    # Format filesystem
    (_CMDPOS + r'mkfs(\.[a-z0-9]+)?\b', "format filesystem (mkfs)"),
    # dd to raw block device
    (_CMDPOS + r'dd\b[^\n]*\bof=/dev/(sd|nvme|hd|mmcblk|vd|xvd)[a-z0-9]*', "dd to raw block device"),
    # Redirect to raw block device
    (r'>\s*/dev/(sd|nvme|hd|mmcblk|vd|xvd)[a-z0-9]*\b', "redirect to raw block device"),
    # Fork bomb
    (r':\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:', "fork bomb"),
    # Kill all processes
    (_CMDPOS + r'kill\s+(-[^\s]+\s+)*-1\b', "kill all processes"),
    # System shutdown/reboot/halt
    (_CMDPOS + r'(shutdown|reboot|halt|poweroff)\b', "system shutdown/reboot"),
    (_CMDPOS + r'init\s+[06]\b', "init 0/6 (shutdown/reboot)"),
    (_CMDPOS + r'systemctl\s+(poweroff|reboot|halt|kexec)\b', "systemctl poweroff/reboot"),
    # Windows destructive built-ins
    (_CMDPOS + r'format-volume\b', "format filesystem (Format-Volume)"),
    (_CMDPOS + r'clear-disk\b', "wipe disk (Clear-Disk)"),
]

HARDLINE_COMPILED = [(re.compile(p, _RE_FLAGS), d) for p, d in HARDLINE_PATTERNS]


# ── DANGEROUS PATTERNS (trigger approval prompts) ───────────────────────────
DANGEROUS_PATTERNS = [
    # Recursive delete
    (r'\brm\s+(-[^\s]*\s+)*/', "delete in root path"),
    (r'\brm\s+-[^\s]*r', "recursive delete"),
    (r'\brm\s+--recursive\b', "recursive delete (long flag)"),
    # Windows destructive commands
    (r'\bcmd(?:\.exe)?\s+/(?:c|k)\s+.*\b(?:del|erase|rd|rmdir)\b', "Windows cmd destructive delete"),
    (r'\b(?:powershell|pwsh)(?:\.exe)?\b.*\s-(?:encodedcommand|enc|e)\b', "PowerShell encoded command execution"),
    (r'\bremove-item\b[^\n;|&]*\s-(?:recurse|force)\b', "PowerShell destructive delete (Remove-Item)"),
    (r'\btaskkill\b[^\n]*\s/f\b', "force kill processes (taskkill /F)"),
    (r'\bstop-process\b[^\n]*\s-force\b', "force kill processes (Stop-Process -Force)"),
    # File permission changes
    (r'\bchmod\s+(-[^\s]*\s+)*(777|666|o\+[rwx]*w|a\+[rwx]*w)\b', "world/other-writable permissions"),
    (r'\bchown\s+(-[^\s]*)?R\s+root', "recursive chown to root"),
    # SQL destructive
    (r'\bDROP\s+(TABLE|DATABASE)\b', "SQL DROP"),
    (r'\bDELETE\s+FROM\b(?![^\n]*\bWHERE\b)', "SQL DELETE without WHERE"),
    (r'\bTRUNCATE\s+(TABLE)?\s*\w', "SQL TRUNCATE"),
    # System service control
    (r'\bsystemctl\s+(-[^\s]+\s+)*(stop|restart|disable|mask)\b', "stop/restart system service"),
    # Force kill
    (r'\bkill\s+-9\s+-1\b', "kill all processes"),
    (r'\bpkill\s+-9\b', "force kill processes"),
    # Pipe remote content to shell
    (rf'\b(curl|wget)\b.*\|\s*(?:[/\w]*/)?(?:{_SHELL_NAMES_RE})(?:\s|$|-c)', "pipe remote content to shell"),
    # Decode and execute
    (rf'\b(base64|base32)\s+(?:-[dD]|--decode)\b.*\|\s*\b(?:{_SHELL_NAMES_RE})\b', "pipe decoded content to shell"),
    # xargs with rm
    (r'\bxargs\s+.*\brm\b', "xargs with rm"),
    # find -exec rm / find -delete
    (r'\bfind\b.*-exec(?:dir)?\s+(/\S*/)?rm\b', "find -exec rm"),
    (r'\bfind\b.*-delete\b', "find -delete"),
    # Git destructive operations
    (r'\bgit\s+reset\s+--hard\b', "git reset --hard (destroys uncommitted changes)"),
    (r'\bgit\s+push\b.*--force\b', "git force push (rewrites remote history)"),
    (r'\bgit\s+push\b.*-f\b', "git force push short flag"),
    (r'\bgit\s+clean\s+-[^\s]*f', "git clean with force (deletes untracked files)"),
    # Sudo with privilege escalation
    (r'\bsudo\b[^;|&\n]*?\s+(?:-s\b|--stdin\b|-a\b)', "sudo with privilege flag"),
    # Package manager uninstalls
    (_CMDPOS + r'npm\s+(?:uninstall|unlink|remove|rm)\b', "package manager uninstall"),
    (_CMDPOS + r'pip(?:3)?\s+uninstall\b', "package manager uninstall"),
    # Windows backup/recovery destruction
    (r'\bvssadmin\b[^\n]*\bdelete\s+shadows\b', "delete volume shadow copies"),
    (r'\bbcdedit\b[^\n]*\s/set\b', "modify boot configuration"),
    (r'\breg(?:\.exe)?\s+delete\b', "registry delete"),
    # Sensitive file overwrites
    (r'>\s*(?:~|/home/|/etc/)', "overwrite sensitive system path"),
    (r'\btee\b.*(?:~|/home/|/etc/)', "tee to sensitive path"),
    # chmod +x followed by immediate execution
    (r'\bchmod\s+\+x\b.*[;&|]+\s*\./', "chmod +x followed by immediate execution"),
    # Cloud metadata endpoint
    (r'(?<![.\d])(?:169\.254\.169\.254|100\.100\.100\.200)(?![.\d])', "cloud metadata endpoint access"),
    # Docker/container lifecycle
    (r'\bdocker\s+(?:restart|stop|kill)\b', "docker container lifecycle"),
    (r'\bdocker(?:-compose|\s+compose)\s+(?:restart|stop|kill|down)\b', "docker compose lifecycle"),
]

DANGEROUS_COMPILED = [(re.compile(p, _RE_FLAGS), d) for p, d in DANGEROUS_PATTERNS]


def _normalize_command(command: str) -> str:
    """Normalize command for detection: collapse escapes, strip ANSI."""
    import re as _re
    # Strip ANSI escape sequences
    command = _re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', command)
    # Collapse backslash-newline continuations
    command = _re.sub(r'\\\r?\n', '', command)
    # Strip backslash-escapes
    command = _re.sub(r'\\([^\n])', r'\1', command)
    # Strip empty-string literals
    command = _re.sub(r"''|\"\"", '', command)
    return command


def detect_hardline_command(command: str) -> tuple[bool, str | None]:
    """Check hardline patterns (NEVER bypassable, even in Off/YOLO mode).
    Returns (is_hardline, description)."""
    normalized = _normalize_command(command).lower()
    for pattern_re, description in HARDLINE_COMPILED:
        if pattern_re.search(normalized):
            return (True, description)
    return (False, None)


def detect_dangerous_command(command: str) -> tuple[bool, str | None, str | None]:
    """Check dangerous patterns. Returns (is_dangerous, pattern_key, description)."""
    normalized = _normalize_command(command).lower()
    for pattern_re, description in DANGEROUS_COMPILED:
        if pattern_re.search(normalized):
            return (True, description, description)
    return (False, None, None)


def normalize_approval_mode(mode: str | None) -> str:
    """Normalizes any approval mode or legacy alias to canonical 'plan', 'auto', or 'off'."""
    clean = str(mode or "").strip().lower()
    if clean in ("plan", "manual"):
        return "plan"
    if clean in ("off", "yolo"):
        return "off"
    return "auto"


def check_command_safety(command: str, approval_mode: str) -> dict | None:
    """Run the safety floor. Returns a block dict if the command must be blocked,
    or None if it can proceed.

    The hardline floor runs regardless of approval_mode (even in 'off').
    """
    # 1. Hardline floor — always blocks
    is_hardline, hardline_desc = detect_hardline_command(command)
    if is_hardline:
        return {
            "blocked": True,
            "hardline": True,
            "reason": f"[SAFETY FLOOR] {hardline_desc}",
            "description": hardline_desc,
        }

    # 2. In 'off' mode, dangerous patterns do NOT block (only hardline does)
    norm_mode = normalize_approval_mode(approval_mode)
    if norm_mode == "off":
        return None

    # 3. Dangerous pattern detection (for plan and auto modes)
    is_dangerous, pattern_key, danger_desc = detect_dangerous_command(command)
    if is_dangerous:
        return {
            "blocked": False,
            "dangerous": True,
            "pattern_key": pattern_key,
            "reason": f"[DANGEROUS] {danger_desc}",
            "description": danger_desc,
            "needs_approval": True,
        }

    return None


# ── Quote-Aware Shell Metacharacter Analyzer (port of can1357/oh-my-pi#7553) ──
_SHELL_CONTROL_CHARS = frozenset("\n\r;&|<>`$()")
_REINTERPRETED_ARGUMENT_RE = re.compile(
    r"(?:^|[ \t])(?:-[^-\s]*[ce]|--(?:command|eval))(?:[= \t]|$)",
    re.IGNORECASE,
)


def has_compound_shell_operator(command: str) -> bool:
    """Return True when a command is compound or contains unquoted shell control operators.

    Quote-aware (port of can1357/oh-my-pi#7553):
    Metacharacters inside single quotes or behind a backslash are literal arguments
    (e.g. `cargo bench -- '^layer3/write/(a|b)$'` or `grep "a|b;c"`), not shell syntax.
    Still compound: `$` or backtick inside DOUBLE quotes (active expansion),
    and any quoted/escaped control character when the command also carries a
    `-c`/`-e`/`--command`/`--eval`-style option that hands quoted text to another interpreter.
    """
    command = command or ""
    quote = None  # None | "'" | '"'
    has_reinterpretable = False
    i = 0
    n = len(command)
    while i < n:
        ch = command[i]
        if ch == "\\" and quote != "'":
            nxt = command[i + 1] if i + 1 < n else ""
            if nxt in _SHELL_CONTROL_CHARS:
                has_reinterpretable = True
            i += 2
            continue
        if quote is not None:
            if ch == quote:
                quote = None
            elif quote == '"' and ch in ("`", "$"):
                return True  # expansion is active inside double quotes
            elif ch in _SHELL_CONTROL_CHARS:
                has_reinterpretable = True
        elif ch in ("'", '"'):
            quote = ch
        elif ch == "$":
            # Unquoted $ is compound when it opens a substitution $(...)
            if i + 1 < n and command[i + 1] == "(":
                return True
        elif ch in _SHELL_CONTROL_CHARS and ch not in "()":
            return True
        i += 1

    # An unterminated quote means we cannot reason about the command shape safely
    if quote is not None:
        return True
    if has_reinterpretable and _REINTERPRETED_ARGUMENT_RE.search(command):
        return True
    return False


def command_matches_allowlist(command: str, allowlist: list[str] | set[str]) -> bool:
    """True when allowlist holds this exact command text or a matching glob.

    Quote-aware (port of can1357/oh-my-pi#7553): refuses compound commands or
    quoted interpreter payloads before matching against allowlist globs.
    """
    import fnmatch
    cmd = (command or "").strip()
    if not cmd or not allowlist:
        return False
    if has_compound_shell_operator(cmd):
        return False
    # If the command has an interpreter option (-c, -e, --eval, --command), reject glob allowlist matching
    # unless the exact pattern explicitly specifies the interpreter option
    has_reinterpretable = bool(_REINTERPRETED_ARGUMENT_RE.search(cmd))
    for pat in allowlist:
        pat = (pat or "").strip()
        if not pat:
            continue
        if pat == cmd:
            return True
        if fnmatch.fnmatchcase(cmd, pat):
            if has_reinterpretable and not _REINTERPRETED_ARGUMENT_RE.search(pat):
                continue
            return True
    return False
