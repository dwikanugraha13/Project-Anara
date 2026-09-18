"""
plan_detector.py ? Unified Plan Detector for Project Anara General Agent.
Implements the 4-tier risk gate specified in prd-general-agent.md & rancangan-general-agent.md.

Principle: Security follows the tool invoked, not the channel or interface.
Zero-hardcoding: Tools are exclusively selected dynamically by the LLM, not by regex heuristics.
"""
import re
import shlex
import logging
from typing import List, Optional, Dict, Any, Set
from tools import get_tool_risk, TOOL_RISK_CLASSIFICATION

logger = logging.getLogger(__name__)

# Severity hierarchy for tool risk
RISK_ORDER: Dict[str, int] = {
    "read_only": 0,
    "action": 1,
    "mutating": 2,
    "ask": 3,
}

# Explicit approval keywords (Case-insensitive)
EXPLICIT_APPROVAL_PATTERNS = [
    r"\b(?:setujui|setuju|approve|approved)\s+(?:rencana|plan)?\b",
    r"\b(?:eksekusi|jalankan|laksanakan)\s+(?:rencana|plan|sekarang)?\b",
    r"\b(?:sikat|gas|gaspol|gasss|hajar|hajar\s*bleh)\b",
    r"\b(?:lanjutkan|lanjut|proceed|lanjoott)\b",
    r"\b(?:boleh|yoi|yup|yap|ok|oke|oke\s*gas)\b",
    r"\b(?:siap\s*(?:laksanakan|jalankan|eksekusi)?)\b",
    r"\bbuild\s+mode\s*(?:sekarang)?\b",
    r"\bok(?:e)?\s*,?\s*(?:jalankan|eksekusi|sikat|lakukan)\b",
    r"\bya\s*,?\s*(?:jalankan|eksekusi|sikat|lakukan)\b",
]


def split_shell_pipeline(cmd: str) -> List[str]:
    """
    Splits a compound shell command by chain operators (;, &&, ||, |)
    while strictly preserving strings inside quotes and backticks.
    """
    segments: List[str] = []
    curr: List[str] = []
    in_single = False
    in_double = False
    escape = False
    i = 0
    n = len(cmd)

    while i < n:
        char = cmd[i]

        if escape:
            curr.append(char)
            escape = False
            i += 1
            continue

        if char == '\\':
            curr.append(char)
            escape = True
            i += 1
            continue

        if char == "'" and not in_double:
            in_single = not in_single
            curr.append(char)
            i += 1
            continue

        if char == '"' and not in_single:
            in_double = not in_double
            curr.append(char)
            i += 1
            continue

        if not in_single and not in_double:
            if i + 1 < n and cmd[i:i+2] in ("&&", "||"):
                seg = "".join(curr).strip()
                if seg:
                    segments.append(seg)
                curr = []
                i += 2
                continue
            elif char in (";", "|"):
                seg = "".join(curr).strip()
                if seg:
                    segments.append(seg)
                curr = []
                i += 1
                continue

        curr.append(char)
        i += 1

    final_seg = "".join(curr).strip()
    if final_seg:
        segments.append(final_seg)

    return segments


def classify_single_command_ast(segment: str) -> str:
    """
    Classifies a single atomic command segment into 'read_only', 'mutating', or 'ask'
    using AST argument tokenization and deterministic subcommand risk evaluation.
    """
    seg = segment.strip()
    if not seg:
        return "read_only"

    # Fatal destructive host takeover / disk wipe patterns -> 'ask'
    seg_lower = seg.lower()
    fatal_patterns = [
        r"\brm\s+-[rf]{1,2}\s+[/~]",
        r"\brmdir\s+/[sq]{1,2}\s+[a-z]:\\?",
        r"\bformat\s+[a-z]:",
        r"\bdiskpart\b",
        r"\bdrop\s+database\b",
        r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;",
        r"\bshutdown(?:\.exe)?\b",
        r"\breboot\b",
        r"\breg\s+(?:add|delete|copy|restore|import)\b",
        r"\bset-mppreference\b",
        r"\bnet\s+(?:user|localgroup|group)\s+.*\/add\b",
    ]
    for fp in fatal_patterns:
        if re.search(fp, seg_lower):
            return "ask"

    # Check unquoted shell write redirection (> or >>)
    seg_no_quotes = re.sub(r'"[^"]*"|\'[^\']*\'', "", seg)
    if re.search(r"(?<![-=])>[>]?", seg_no_quotes):
        return "mutating"

    # Tokenize arguments
    try:
        raw_tokens = shlex.split(seg, posix=False)
    except Exception:
        raw_tokens = seg.split()

    tokens = [t.strip("\"'") for t in raw_tokens if t.strip("\"'")]
    if not tokens:
        return "read_only"

    # Unwrap shell wrappers (cmd.exe /c, powershell -command, etc.)
    first = tokens[0].lower().rstrip(".exe")
    if first in ("cmd", "command") and len(tokens) > 2 and tokens[1].lower() in ("/c", "/k"):
        tokens = tokens[2:]
        if not tokens:
            return "read_only"
        first = tokens[0].lower().rstrip(".exe")

    if first in ("powershell", "pwsh") and len(tokens) > 2:
        for p_idx, tok in enumerate(tokens[:-1]):
            if tok.lower() in ("-command", "-c"):
                sub_cmd_str = tokens[p_idx + 1]
                return evaluate_command_safety(sub_cmd_str)

    if first == "&" and len(tokens) > 1:
        tokens = tokens[1:]
        first = tokens[0].lower().rstrip(".exe")

    binary = first
    subcmd = tokens[1].lower() if len(tokens) > 1 else ""
    flags: Set[str] = {t.lower() for t in tokens[1:] if t.startswith("-") or t.startswith("/")}
    non_flag_args = [t for t in tokens[1:] if not (t.startswith("-") or t.startswith("/"))]

    # --- Git ---
    if binary == "git":
        if not subcmd or subcmd in ("--version", "-v", "--help", "-h"):
            return "read_only"
        safe_git_subcmds = {
            "status", "log", "diff", "show", "tag", "rev-parse", "describe",
            "remote", "config", "var", "version", "check-ref-format", "help",
            "shortlog", "whatchanged", "ls-files", "ls-tree", "cat-file", "grep"
        }
        if subcmd == "branch":
            if any(f in flags for f in ("-d", "-D", "--delete")):
                return "mutating"
            return "read_only"
        if subcmd == "remote":
            if any(a.lower() in ("add", "remove", "rm", "rename", "set-url") for a in non_flag_args):
                return "mutating"
            return "read_only"
        if subcmd == "config":
            if any(f in flags for f in ("-l", "--list", "--get", "--get-all")):
                return "read_only"
            if len(non_flag_args) >= 2:
                return "mutating"
            return "read_only"
        if subcmd in safe_git_subcmds:
            return "read_only"
        return "mutating"

    # --- NPM / PNPM / YARN / BUN ---
    if binary in ("npm", "pnpm", "yarn", "bun"):
        if not subcmd or subcmd in ("-v", "-V", "--version", "-h", "--help"):
            return "read_only"
        safe_npm_subcmds = {"list", "ls", "view", "info", "outdated", "why", "audit", "explain"}
        if subcmd == "audit" and "fix" in [a.lower() for a in non_flag_args]:
            return "mutating"
        if subcmd == "config":
            if "get" in [a.lower() for a in non_flag_args] or any(f in flags for f in ("-l", "--list")):
                return "read_only"
            return "mutating"
        if subcmd in safe_npm_subcmds:
            return "read_only"
        return "mutating"

    # --- PIP ---
    if binary in ("pip", "pip3"):
        if not subcmd or subcmd in ("-v", "-V", "--version", "-h", "--help"):
            return "read_only"
        safe_pip_subcmds = {"list", "show", "check", "config", "inspect"}
        if subcmd in safe_pip_subcmds:
            return "read_only"
        return "mutating"

    # --- Docker ---
    if binary == "docker":
        if not subcmd or subcmd in ("--version", "-v", "--help", "-h"):
            return "read_only"
        safe_docker_subcmds = {"ps", "images", "version", "info", "logs", "inspect", "stats", "top", "port"}
        if subcmd in safe_docker_subcmds:
            return "read_only"
        return "mutating"

    # --- Python / Node ---
    if binary in ("python", "python3", "py", "node"):
        if not subcmd or subcmd in ("-v", "-V", "--version", "-h", "--help"):
            return "read_only"
        if binary in ("python", "python3", "py") and any(t in tokens for t in ("-c", "/c")):
            # Inspect one-liner python script
            py_mutating = [
                "open(", "write(", ".write", "os.remove", "os.unlink", "os.rmdir", "shutil.rmtree",
                "os.rename", "os.replace", "shutil.move", "shutil.copy", "subprocess.", "os.system"
            ]
            if not any(pm in seg_lower for pm in py_mutating):
                return "read_only"
            return "mutating"
        # Executing a standalone script file -> mutating
        return "mutating"

    # --- PowerShell Cmdlets ---
    if binary.startswith("get-") or binary.startswith("test-") or binary in (
        "select-object", "where-object", "measure-object", "sort-object",
        "format-table", "format-list", "out-string", "convertfrom-json",
        "convertto-json", "export-clixml"
    ):
        return "read_only"

    if binary.startswith((
        "set-", "new-", "remove-", "move-", "copy-", "rename-",
        "clear-", "stop-", "restart-", "install-", "update-", "add-", "invoke-"
    )):
        return "mutating"

    # --- Shell & OS Utilities ---
    safe_os_commands = {
        "dir", "ls", "type", "cat", "find", "findstr", "echo", "ver", "vol",
        "whoami", "where", "which", "whereis", "set", "env", "printenv",
        "hostname", "systeminfo", "driverquery", "tasklist", "ipconfig",
        "netstat", "nslookup", "ping", "tracert", "path", "pwd", "head",
        "tail", "grep", "wc", "awk", "sed", "uname", "uptime", "free", "df",
        "ps", "id", "groups", "file", "stat"
    }
    if binary in safe_os_commands:
        return "read_only"

    mutating_os_commands = {
        "rm", "del", "erase", "rmdir", "rd", "mkdir", "md", "ren", "rename",
        "move", "copy", "robocopy", "xcopy", "attrib", "icacls", "takeown",
        "taskkill", "kill", "pkill", "touch", "chmod", "chown", "mv", "cp",
        "tar", "unzip", "curl", "wget"
    }
    if binary in mutating_os_commands:
        return "mutating"

    # Fallback to catalog check
    from tools.catalog import is_safe_read_only_cli_command
    if is_safe_read_only_cli_command(seg):
        return "read_only"

    return "mutating"


def evaluate_command_safety(command: str) -> str:
    """
    Parameter-Aware Risk Evaluator for terminal commands ('read_only', 'mutating', 'ask').
    Splits chained pipelines (;, &&, ||, |) without breaking quoted parameters,
    performs AST argument tokenization, and escalates to highest risk.
    """
    cmd = (command or "").strip()
    if not cmd:
        return "read_only"

    segments = split_shell_pipeline(cmd)
    if not segments:
        return "read_only"

    highest = "read_only"
    risk_weights = {"read_only": 0, "action": 1, "mutating": 2, "ask": 3}

    for seg in segments:
        r = classify_single_command_ast(seg)
        if risk_weights.get(r, 2) > risk_weights.get(highest, 0):
            highest = r
        if highest == "ask":
            break

    return highest


def detect_tools_from_text(request_text: str) -> List[str]:
    """
    Zero-hardcode policy: No tool is guessed from raw user text via regex heuristics.
    Tools are exclusively selected by the model dynamically at runtime.
    """
    return []


def get_highest_risk(tools: List[str]) -> str:
    """Returns the highest risk tier ('read_only', 'action', 'mutating', 'ask') from a list of tools."""
    if not tools:
        return "read_only"
    highest = "read_only"
    highest_val = 0
    for t in tools:
        risk = get_tool_risk(t)
        val = RISK_ORDER.get(risk, 2)
        if val > highest_val:
            highest_val = val
            highest = risk
    return highest


def is_significant_action(request_text: str, tools: List[str]) -> bool:
    """
    Evaluates if an 'action' tier tool has significant side effects
    (e.g., messaging multiple recipients, destructive todo clears, production webhooks).
    """
    text = (request_text or "").lower()
    significant_patterns = [
        r"\b(?:semua|all|broadcast|group|grup|banyak)\b",
        r"\b(?:penting|urgent|darurat|kritis)\b",
        r"\b(?:hapus\s+semua|reset|clear)\b",
    ]
    return any(re.search(pat, text) for pat in significant_patterns)


def is_explicit_plan_approval(user_text: str) -> bool:
    """Returns True if the user text explicitly approves a pending plan for execution."""
    text = (user_text or "").strip().lower()
    if not text:
        return False
    return any(re.search(pat, text) for pat in EXPLICIT_APPROVAL_PATTERNS)


def needs_plan(
    request_text: str,
    detected_tools: Optional[List[str]] = None,
    session_mode: str = "conversational",
) -> bool:
    """
    Unified Plan Detector:
    1. If detected_tools are provided (from LLM runtime tool-call selection):
       - 'read_only': False (direct zero-friction answer)
       - 'action': True only if significant side-effects are detected
       - 'mutating' or 'ask': True ALWAYS (mandatory Plan mode)
    2. In 'explicit_plan_build' mode:
       Requires Plan mode for any non-read_only operation.
    3. In 'conversational' mode without detected tools:
       Delegates directly to LLM with runtime tool interception (Zero-hardcoding).
    """
    tools = list(detected_tools) if detected_tools else detect_tools_from_text(request_text)
    risk = get_highest_risk(tools)

    if session_mode == "explicit_plan_build":
        return risk != "read_only"

    if risk == "read_only":
        return False
    if risk == "action":
        return is_significant_action(request_text, tools)
    if risk in ("mutating", "ask"):
        return True

    return False
