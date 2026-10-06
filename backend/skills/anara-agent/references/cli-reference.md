# Anara CLI Reference

Live sources when anything looks stale: `anara --help`, `anara <command> --help`,
https://project-anara.dev/docs/reference/cli-commands

### Global Flags

```
anara [flags] [command]        (no subcommand = interactive chat)

  --version, -V             Show version
  -z, --oneshot PROMPT      One-shot: print ONLY the final response (for scripts/pipes)
  -m MODEL  --provider P    Model/provider override for this invocation
  -t, --toolsets LIST       Comma-separated toolsets for this invocation
  --resume, -r SESSION      Resume session by ID or title
  --continue, -c [NAME]     Resume by name, or most recent session
  --worktree, -w            Isolated git worktree mode (parallel agents)
  --skills, -s SKILL        Preload skills (comma-separate or repeat)
  --profile, -p NAME        Use a named profile
  --yolo                    Skip dangerous command approval
  --tui / --cli             Force the Ink TUI / classic REPL
  --ignore-rules            Skip AGENTS.md/SOUL.md/memory/skill injection
  --safe-mode               Disable ALL customizations (troubleshooting)
  --pass-session-id         Include session ID in system prompt
```

### Chat

```
anara chat [flags]
  -q, --query TEXT          Single query, non-interactive
  --image PATH              Attach a local image to a single query
  -Q, --quiet               Suppress banner, spinner, tool previews
  --checkpoints             Enable filesystem checkpoints (/rollback)
  --max-turns N             Cap tool-calling iterations
  --source TAG              Session source tag (default: cli)
```
(plus the global flags above)

### Configuration

```
anara setup [section]      Wizard (model|tts|terminal|gateway|tools|agent)
anara model                Interactive model/provider picker
anara fallback [add|remove|list]  Fallback provider chain
anara config [show|edit|get|set|unset|path|env-path|check|migrate]
anara login / logout       OAuth sign-in / clear stored auth
anara doctor [--fix]       Check dependencies and config
anara status [--full]      Component summary (--full: every section)
```

### Tools & Skills

```
anara tools [list|enable NAME|disable NAME]   Per-platform toolsets (curses UI with no args)

anara skills list|browse|search QUERY|inspect ID
anara skills install ID    Hub identifier OR a direct https://…/SKILL.md URL
anara skills config        Enable/disable skills per platform
anara skills check|update|uninstall|publish PATH
anara skills tap add REPO  Add a GitHub repo as a skill source
anara bundles              Skill bundles (one /<name> alias loads several skills)
```

### MCP Servers

```
anara mcp add NAME (--url or --command) | remove | list | test NAME
anara mcp catalog | install NAME     Curated catalog install
anara mcp configure NAME             Toggle tool selection
anara mcp serve                      Run Anara as an MCP server
```
Details (transport, tool discovery, catalog): `references/native-mcp.md`.

### Gateway (Messaging Platforms)

```
anara gateway run|install|start|stop|restart|status|setup
```

20+ platforms: Telegram, Discord, Slack, WhatsApp (Baileys + Business Cloud API), iMessage (Photon — `anara photon setup`), Signal, Email, SMS, Matrix, Mattermost, Teams, LINE, SimpleX, ntfy, Google Chat, Home Assistant, DingTalk, Feishu, WeCom, Weixin, API Server, Webhooks. Open WebUI connects via the API Server adapter. Most adapters ship under `plugins/platforms/`.
Docs: https://project-anara.dev/docs/user-guide/messaging/

### Sessions

```
anara sessions list|browse|rename ID TITLE|delete ID|export OUT|prune|stats
```

### Cron / Webhooks

```
anara cron list|create SCHED|edit ID|pause|resume|run ID|remove|status
    Schedules: '30m', 'every 2h', '0 9 * * *', ISO timestamp
anara webhook subscribe NAME|list|remove NAME|test NAME
```
Webhook payloads/routes: `references/webhooks.md`.

### Profiles

```
anara profile list|create NAME (--clone|--clone-all|--clone-from)|use|show|delete
anara profile rename A B | alias NAME | export NAME | import FILE
anara profile migrate-identity A B   Retry a completed rename's session/routing identity migration
```

### Credentials & Pools

```
anara auth                 Interactive credential manager
anara auth add [PROVIDER]  Add OAuth or API-key credential (nous, openai-codex, qwen-oauth, …)
anara auth list|remove P IDX|reset PROVIDER|status
```
Multiple credentials per provider form a pool that rotates automatically and skips exhausted keys.

### Other

```
anara desktop / gui        Native desktop app
anara dashboard            Web admin panel + embedded chat (--stop / --status)
anara proxy                OpenAI-compatible local proxy backed by an OAuth provider
anara portal               Quick setup / sign in via Nous Portal
anara kanban <verb>        Multi-agent work-queue board
anara project              Named multi-folder workspaces
anara skin list|use|set    Switch/tweak skins (see references/themes.md)
anara pets <verb>          Pet mascots (see references/petdex.md)
anara memory setup|status|off|reset   Memory provider
anara secrets bitwarden|onepassword   External secret stores
anara moa                  Mixture-of-Agents slots
anara hooks / security / backup / import / checkpoints / console
anara logs [-f] [errors]   View agent/error logs
anara send                 One-off message through a gateway platform
anara pairing / plugins / insights / journey / computer-use
anara acp                  ACP server (IDE integration)
anara completion bash|zsh|fish
anara update / uninstall / claw migrate
```

Plugin- and provider-supplied subcommands (e.g. `anara photon setup`) only appear once their plugin is installed/active.

### Where to Find Things

| Looking for... | Location |
|---|---|
| Config options | `anara config edit` · [Configuration docs](https://project-anara.dev/docs/user-guide/configuration) |
| Tools / toolsets | `anara tools list` · [Tools reference](https://project-anara.dev/docs/reference/tools-reference) |
| Skills catalog | `anara skills browse` · [Skills catalog](https://project-anara.dev/docs/reference/skills-catalog) |
| Provider setup | `anara model` · [Providers guide](https://project-anara.dev/docs/integrations/providers) |
| Env variables | `anara config env-path` · [Env vars reference](https://project-anara.dev/docs/reference/environment-variables) |
| Gateway logs | `~/.anara/logs/gateway.log` (or `anara logs`) |
| Sessions | `anara sessions browse` (reads state.db) |
