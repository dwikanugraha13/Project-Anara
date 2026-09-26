"""
plan_detector.py ? Unified Plan Detector for Project Anara General Agent.
Implements the 4-tier risk gate specified in prd-general-agent.md & rancangan-general-agent.md.

Principle: Security follows the tool invoked, not the channel or interface.
Zero-hardcoding: Tools are exclusively selected dynamically by the LLM, not by regex heuristics.
"""
import asyncio
import concurrent.futures
import hashlib
import logging
import re
import shlex
import time
from typing import List, Optional, Dict, Any, Set, Tuple
from tools import get_tool_risk, TOOL_RISK_CLASSIFICATION

logger = logging.getLogger(__name__)

# Persistent worker pool for synchronous approval intent calls (Hermes Parity)
_SYNC_INTENT_EXECUTOR: Optional[concurrent.futures.ThreadPoolExecutor] = None


def _get_sync_intent_executor() -> concurrent.futures.ThreadPoolExecutor:
    global _SYNC_INTENT_EXECUTOR
    if _SYNC_INTENT_EXECUTOR is None:
        _SYNC_INTENT_EXECUTOR = concurrent.futures.ThreadPoolExecutor(
            max_workers=2, thread_name_prefix="anara_intent_sync"
        )
    return _SYNC_INTENT_EXECUTOR

# Severity hierarchy for tool risk
RISK_ORDER: Dict[str, int] = {
    "read_only": 0,
    "action": 1,
    "mutating": 2,
    "ask": 3,
}


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
        # Bulk wildcard wipe patterns -> 'ask' (Granular human approval required)
        r"\brm\s+-[rf]{1,2}\s+(?:\*|\.\/\*|\.\s*$)",
        r"\bdel\b.*\/[sq].*(?:\*|\.\*)",
        r"\brmdir\b.*\/[sq]\s+(?:\.|\*|[a-zA-Z]:[/\\]?$)",
        r"\bremove-item\b.*-(?:recurse|r)\b.*(?:\*|\.[\/\\]\*|\s\.)",
        r"\bgit\s+clean\s+-[fdx]{1,4}\b",
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
    first = tokens[0].lower()
    if first.endswith(".exe"):
        first = first[:-4]
    if first in ("cmd", "command") and len(tokens) > 2 and tokens[1].lower() in ("/c", "/k"):
        tokens = tokens[2:]
        if not tokens:
            return "read_only"
        first = tokens[0].lower()
        if first.endswith(".exe"):
            first = first[:-4]

    if first in ("powershell", "pwsh") and len(tokens) > 2:
        for p_idx, tok in enumerate(tokens[:-1]):
            if tok.lower() in ("-command", "-c"):
                sub_cmd_str = " ".join(tokens[p_idx + 1:])
                return evaluate_command_safety(sub_cmd_str)

    if first == "&" and len(tokens) > 1:
        tokens = tokens[1:]
        first = tokens[0].lower()
        if first.endswith(".exe"):
            first = first[:-4]

    binary = first
    subcmd = tokens[1].lower() if len(tokens) > 1 else ""
    flags: Set[str] = {t.lower() for t in tokens[1:] if t.startswith("-") or t.startswith("/")}
    non_flag_args = [t for t in tokens[1:] if not (t.startswith("-") or t.startswith("/"))]

    # --- Git ---
    if binary == "git":
        # Resolve real git subcommand by skipping global git options (e.g. -C <dir>, -c <conf>)
        git_idx = 1
        git_subcmd = ""
        git_sub_tokens = []
        while git_idx < len(tokens):
            tok = tokens[git_idx]
            tok_lower = tok.lower()
            if tok_lower == "-c":
                # Global option that takes a path or config argument
                git_idx += 2
                continue
            elif tok_lower.startswith(("-c=", "--git-dir", "--work-tree", "--namespace", "--super-prefix", "--exec-path")):
                git_idx += 1
                continue
            elif tok.startswith("-") or tok.startswith("/"):
                # Other global flags like --paginate, --no-pager, -p, -P, --bare
                if tok_lower in ("--version", "-v", "--help", "-h"):
                    return "read_only"
                git_idx += 1
                continue
            else:
                # First non-flag token is the actual git subcommand
                git_subcmd = tok_lower
                git_sub_tokens = tokens[git_idx + 1:]
                break

        if not git_subcmd or git_subcmd in ("--version", "-v", "--help", "-h"):
            return "read_only"

        git_flags = {t.lower() for t in git_sub_tokens if t.startswith("-") or t.startswith("/")}
        git_non_flags = [t for t in git_sub_tokens if not (t.startswith("-") or t.startswith("/"))]

        safe_git_subcmds = {
            "status", "log", "diff", "show", "rev-parse", "describe",
            "remote", "config", "var", "version", "check-ref-format", "help",
            "shortlog", "whatchanged", "ls-files", "ls-tree", "cat-file", "grep"
        }
        if git_subcmd == "tag":
            # `git tag` (list) is read_only; `git tag <name>` or `git tag -d` is mutating
            if any(f in git_flags for f in ("-d", "-D", "--delete")):
                return "mutating"
            if git_non_flags:
                return "mutating"
            return "read_only"
        if git_subcmd == "branch":
            if any(f in git_flags for f in ("-d", "-D", "--delete")):
                return "mutating"
            return "read_only"
        if git_subcmd == "remote":
            if any(a.lower() in ("add", "remove", "rm", "rename", "set-url") for a in git_non_flags):
                return "mutating"
            return "read_only"
        if git_subcmd == "config":
            if any(f in git_flags for f in ("-l", "--list", "--get", "--get-all")):
                return "read_only"
            if len(git_non_flags) >= 2:
                return "mutating"
            return "read_only"
        if git_subcmd in safe_git_subcmds:
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
                "os.rename", "os.replace", "shutil.move", "shutil.copy", "subprocess.", "os.system",
                "pathlib.", "pathlib ", "exec(", "eval(", "__import__", "compile(", "importlib.",
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
        "convertto-json"
    ):
        return "read_only"

    if binary.startswith((
        "set-", "new-", "remove-", "move-", "copy-", "rename-",
        "clear-", "stop-", "restart-", "install-", "update-", "add-", "invoke-",
        "export-"
    )):
        return "mutating"

    # --- Shell & OS Utilities ---
    safe_os_commands = {
        "dir", "ls", "type", "cat", "findstr", "echo", "ver", "vol",
        "whoami", "where", "which", "whereis", "printenv",
        "hostname", "systeminfo", "driverquery", "tasklist", "ipconfig",
        "netstat", "nslookup", "ping", "tracert", "path", "pwd", "head",
        "tail", "grep", "wc", "uname", "uptime", "free", "df",
        "ps", "id", "groups", "file", "stat"
    }
    if binary in safe_os_commands:
        return "read_only"

    # Context-aware classification for commands that are read_only only under safe flags
    if binary == "sed":
        if any(f in flags for f in ("-i", "--in-place")):
            return "mutating"
        return "read_only"
    if binary == "awk":
        return "read_only"
    if binary == "find":
        if any(f in flags for f in ("-delete", "-exec", "-execdir")):
            return "mutating"
        if any(a.lower() in ("-delete", "-exec", "-execdir") for a in non_flag_args):
            return "mutating"
        return "read_only"
    if binary == "env":
        # Bare `env` / `env` with no arguments or only flags -> read_only (prints env vars)
        if not non_flag_args:
            return "read_only"
        return "mutating"
    if binary == "set":
        # `set` with no args -> read_only (prints env vars); with assignment -> mutating
        if not non_flag_args and "=" not in seg_lower:
            return "read_only"
        return "mutating"

    mutating_os_commands = {
        "rm", "del", "erase", "rmdir", "rd", "mkdir", "md", "ren", "rename",
        "move", "copy", "robocopy", "xcopy", "attrib", "icacls", "takeown",
        "taskkill", "kill", "pkill", "touch", "chmod", "chown", "mv", "cp",
        "tar", "unzip", "curl", "wget"
    }
    if binary in mutating_os_commands:
        return "mutating"

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
    Evaluates if an 'action' tier tool has significant external side effects (Hermes Parity).
    Evaluates tool characteristics rather than arbitrary keyword heuristics.
    """
    if not tools:
        return False
    significant_tools = {"custom_webhook", "send_document_file"}
    return any(t in significant_tools for t in tools)


_INTENT_CACHE: Dict[str, Any] = {}
_INTENT_CACHE_TTL = 90.0  # 90s short TTL to prevent stale or cross-action intent poisoning


def _get_intent_cache_key(user_text: str, context: str = "") -> str:
    ctx_hash = hashlib.sha256(context.strip().encode("utf-8")).hexdigest()[:12] if context.strip() else "general"
    return f"{user_text.strip().lower()}:::{ctx_hash}"


def _lookup_intent_cache(key: str) -> Optional[str]:
    now = time.time()
    # Check exact key first
    if key in _INTENT_CACHE:
        entry = _INTENT_CACHE[key]
        if isinstance(entry, tuple):
            ts, val = entry
            if now - ts <= _INTENT_CACHE_TTL:
                return val
            _INTENT_CACHE.pop(key, None)
            return None
        elif isinstance(entry, str):
            return entry

    # Also check base key (for backwards compatibility with unit tests pre-seeding _INTENT_CACHE["gas"] = "approve")
    base_key = key.split(":::")[0] if ":::" in key else key
    if base_key in _INTENT_CACHE:
        entry = _INTENT_CACHE[base_key]
        if isinstance(entry, tuple):
            ts, val = entry
            if now - ts <= _INTENT_CACHE_TTL:
                return val
            return None
        elif isinstance(entry, str):
            return entry

    return None


def _store_intent_cache(key: str, val: str):
    now = time.time()
    if len(_INTENT_CACHE) > 200:
        expired_keys = [k for k, (ts, _) in _INTENT_CACHE.items() if now - ts > _INTENT_CACHE_TTL]
        for k in expired_keys:
            _INTENT_CACHE.pop(k, None)
        if len(_INTENT_CACHE) > 200:
            _INTENT_CACHE.clear()
    _INTENT_CACHE[key] = (now, val)


# Universal machine-level binary CLI tokens only (Claude Code & Hermes Parity)
# These represent explicit single-word terminal keypresses [y/N], NOT human slang dictionaries.
_CLI_MACHINE_CONFIRM_TOKENS = {"y", "yes"}
_CLI_MACHINE_CANCEL_TOKENS = {"n", "no"}


def is_explicit_plan_approval(user_text: str, pending_action_context: str = "") -> bool:
    """
    Claude Code & Hermes Parity: 100% Model-Driven Approval Reasoning.
    Zero language-specific keyword dictionaries. All human language utterances
    (Indonesian, English slang, German, Japanese, etc.) are evaluated semantically
    by the reasoning model to correctly detect nuance, conditionals, and negation.
    """
    clean = (user_text or "").strip()
    if not clean:
        return False

    cache_key = _get_intent_cache_key(clean, pending_action_context)
    cached_val = _lookup_intent_cache(cache_key)
    if cached_val is not None:
        return cached_val == "approve"

    # Fast-path for bare single-character CLI machine responses only
    lower_tok = clean.lower()
    if lower_tok in _CLI_MACHINE_CONFIRM_TOKENS:
        _store_intent_cache(cache_key, "approve")
        return True
    if lower_tok in _CLI_MACHINE_CANCEL_TOKENS:
        _store_intent_cache(cache_key, "reject")
        return False

    # Semantic evaluation via model reasoning (100% Model-Driven Parity)
    try:
        executor = _get_sync_intent_executor()
        future = executor.submit(lambda: asyncio.run(classify_approval_intent(clean, pending_action_context)))
        res = future.result(timeout=20.0)
        return res == "approve"
    except Exception as e:
        logger.debug(f"[is_explicit_plan_approval] Error: {e}")
        pass
    return False


async def classify_approval_intent(user_text: str, pending_action_context: str = "") -> str:
    """
    Pure Model-Driven Semantic Intent Classifier (Hermes Parity).
    Evaluates whether incoming user response is:
    - 'approve': user agrees, affirms, gives green light, or says to proceed.
    - 'reject': user declines, cancels, says no, tells to stop, or rejects the action.
    - 'other': user is asking something else or ignoring the prompt.
    Operates across all human languages via LLM reasoning without language-specific word dictionaries.
    """
    clean = (user_text or "").strip()
    if not clean:
        return "other"

    cache_key = _get_intent_cache_key(clean, pending_action_context)
    cached_val = _lookup_intent_cache(cache_key)
    if cached_val is not None:
        return cached_val

    # Fast-path for bare single-character CLI machine responses only
    lower_tok = clean.lower()
    if lower_tok in _CLI_MACHINE_CONFIRM_TOKENS:
        _store_intent_cache(cache_key, "approve")
        return "approve"
    if lower_tok in _CLI_MACHINE_CANCEL_TOKENS:
        _store_intent_cache(cache_key, "reject")
        return "reject"

    # Semantic LLM-Driven Classification for any human language, slang, or idiom
    try:
        from providers import call_universal_chat_model
        from core.capabilities import get_fast_auxiliary_model
        from core.prompt_loader import load_prompt

        sys_instruction = load_prompt("classifiers/approval_intent")
        user_p = (
            f"Pending action: {pending_action_context or 'System action awaiting confirmation'}\n"
            f"User response: \"{clean}\"\n"
            "Classification:"
        )

        model_id = get_fast_auxiliary_model()
        for attempt in range(2):
            try:
                res = await asyncio.wait_for(
                    call_universal_chat_model(
                        model_id=model_id,
                        user_prompt=user_p,
                        system_instruction=sys_instruction,
                        max_tokens=None,
                        temperature=0.0,
                        read_only=True,
                    ),
                    timeout=15.0
                )
                if isinstance(res, str):
                    # Robust multi-format verdict extraction (Hermes Parity)
                    verdict = None
                    m_bold = re.findall(r"\*\*(APPROVE|REJECT|OTHER)\*\*", res, re.IGNORECASE)
                    if m_bold:
                        verdict = m_bold[-1].lower()
                    if not verdict:
                        m_kv = re.search(r"(?:verdict|classification|decision|klasifikasi)\s*[:=]\s*(APPROVE|REJECT|OTHER)\b", res, re.IGNORECASE)
                        if m_kv:
                            verdict = m_kv.group(1).lower()
                    if not verdict:
                        lines = [l.strip().strip('*_`#.:- ').upper() for l in res.splitlines() if l.strip()]
                        for l in reversed(lines):
                            if l in ("APPROVE", "REJECT", "OTHER"):
                                verdict = l.lower()
                                break
                    if not verdict:
                        m_all = re.findall(r"\b(APPROVE|REJECT)\b", res, re.IGNORECASE)
                        if m_all:
                            verdict = m_all[-1].lower()
                    if not verdict:
                        m_v = re.search(r"\b(APPROVE|REJECT|OTHER)\b", res, re.IGNORECASE)
                        if m_v:
                            verdict = m_v.group(1).lower()

                    if verdict in ("approve", "reject"):
                        _store_intent_cache(cache_key, verdict)
                        return verdict
                    elif verdict == "other":
                        _store_intent_cache(cache_key, "other")
                        return "other"
            except Exception as e:
                logger.warning(f"[IntentClassifier] LLM pass attempt {attempt + 1} notice for '{clean}': {e}")
                await asyncio.sleep(0.3)
    except Exception as e:
        logger.warning(f"[IntentClassifier] LLM semantic pass notice for '{clean}': {e}")

    return "other"


async def smart_evaluate_command_safety(command: str, description: str = "") -> str:
    """
    Hermes Smart Approval Guardian (approval_smart.py Parity).
    Evaluates shell command risk using auxiliary LLM security reviewer.
    Guarantees pure model reasoning over raw AST heuristics for complex or ambiguous commands.
    """
    cmd = (command or "").strip()
    if not cmd:
        return "read_only"

    # 1. Fast AST evaluation
    fast_risk = evaluate_command_safety(cmd)
    if fast_risk in ("read_only", "ask"):
        return fast_risk

    # 2. For mutating / complex commands, consult the Guardian LLM
    try:
        from providers import call_universal_chat_model
        from core.capabilities import get_fast_auxiliary_model
        from core.prompt_loader import load_prompt

        sys_p = load_prompt("classifiers/command_safety", command=cmd, description=description or "Shell execution")
        user_p = f"<command>\n{cmd}\n</command>\n\nContext: {description or 'Shell execution'}\nVerdict:"

        model_id = get_fast_auxiliary_model()
        res = await asyncio.wait_for(
            call_universal_chat_model(
                model_id=model_id,
                user_prompt=user_p,
                system_instruction=sys_p,
                max_tokens=None,
                temperature=0.0,
                read_only=True,
            ),
            timeout=3.5
        )
        if isinstance(res, str):
            token = res.strip().upper()
            if "APPROVE" in token:
                return "read_only"
            elif "ESCALATE" in token:
                return "ask"
            elif "DENY" in token:
                return "mutating"
    except Exception as e:
        logger.debug(f"[SmartApproval] Guardian LLM pass notice: {e}")

    return fast_risk


def needs_plan(
    request_text: str = "",
    detected_tools: Optional[List[str]] = None,
    session_mode: str = "conversational",
) -> bool:
    """
    Hermes Model-Driven Parity: Zero text-based regex guessing.
    In explicit plan mode ('explicit_plan_build' or 'plan'), returns True.
    In conversational mode with specific runtime tools provided, checks their risk.
    In conversational mode without tools, returns False to delegate directly
    to the LLM ReAct loop with dynamic runtime tool interception.
    """
    if session_mode in ("explicit_plan_build", "plan"):
        if detected_tools:
            return get_highest_risk(detected_tools) != "read_only"
        return True

    if not detected_tools:
        return False

    risk = get_highest_risk(detected_tools)
    if risk == "read_only":
        return False
    if risk == "action":
        return is_significant_action(request_text, detected_tools)
    return risk in ("mutating", "ask")
