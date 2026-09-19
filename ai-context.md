# Py-Agent Config

> **Syntax**: `[command / execution] ──> [intent1], [intent2], [intent3]`  
> **Delimiter**: `" ---> "` (Three-dash arrow with a trailing space)

---

### Syntax Guide
1. `ai init [path]`: Index workspace and launch interactive agent session.
2. `ai init --<skill> [path]`: Index workspace primed with a specific agent profile.
3. `[TOOL] <command>`: Execute system tool (prompts for `[Y/n]` authorization).
4. `[TOOL] <command> --s`: Execute tool silently (bypasses confirmation gate).
5. `<command>`: Terminal shortcut, alias, or file viewer.

---

## 1. Start Agent

```properties
# --- Agent Diagnostic ---
[TOOL] ~/.config/py-agent/tools/test-agent --cat --s ---> agent test, ta
# --- Model Selector ---
~/.config/py-agent/modules/model-select.py ---> model select, cloud model
# --- Project Creator ---
~/.config/py-agent/tools/new-project ---> new project, newproject, newp, new-project
# --- AI Status ---
[TOOL] ~/.config/py-agent/tools/agentic/system/ai-status ---> aistatus, aistat, ais
# --- Cheatsheet ---
[TOOL] ~/.config/py-agent/tools/cheatsheet ---> cheatsheet, cs
# --- Eval Model & Profile (Agentic Tool Benchmark) ---
~/.config/py-agent/tools/evals/eval-stack --->  eval stack, eval-stack
# --- System Orchestrator TUI ---
[TOOL] ~/.config/py-agent/tools/system-stack ---> system stack, sysstack
```

## 2. Projects

```properties
# --- Workspaces ---
ai init ~/.config/py-agent/projects/occamy ---> occamy
ai init ~/.config/py-agent/projects/tini-cybersec ---> tini-cybersec, tini cybersec
ai init ~/.config/py-agent/projects/ornith ---> ornith
ai init ~/.config/py-agent/projects/katcoder ---> katcoder
ai init ~/.config/py-agent/projects/nex-n2 ---> nex-n2, nex n2
ai init ~/.config/py-agent/projects/qwen2b ---> qwen2b
ai init ~/.config/py-agent/projects/deepseek ---> deepseek-v4
ai init ~/.config/py-agent/projects/gemini ---> gemini
ai init ~/.config/py-agent/projects/ling-tiny ---> ling-tiny
ai init ~/.config/py-agent/projects/omarchyv4 ---> omarchyv4
ai init ~/.config/py-agent/projects/minicpm ---> minicpm
ai init ~/.config/py-agent/projects/session-test ---> session test, projects session
```

## 3. Plugins

```properties
# --- PyCode Setup & Build ---
~/.config/py-agent/plugins/pycode/setup.sh ---> install-pycode, setup-pycode, setup pycode
# --- Model Context Protocol (MCP) ---
~/.config/py-agent/plugins/mcp/mcp_client.py list ---> mcp list, mcp tools, mcpl
~/.config/py-agent/plugins/mcp/mcp_client.py schemas ---> mcp schemas, mcp export
# Fetch: fetch <url> — Fast standard URL markdown scraper. Example: fetch https://docs.python.org/3
[TOOL] ~/.config/py-agent/plugins/mcp/mcp_client.py fetch ---> fetch, mcp fetch
[TOOL] ~/.config/py-agent/plugins/mcp/mcp_client.py call sqlite query ---> mcp sqlite, query db
# Context7: docs <libraryId> <query> — Injects official markdown API docs into context. Example: docs /vercel/next.js middleware
[TOOL] ~/.config/py-agent/plugins/mcp/mcp_client.py docs ---> context7, get docs
# Firecrawl Scrape: scrape <url> — Bypasses JS/anti-bot to extract clean markdown. Example: scrape https://react.dev/reference/react
[TOOL] ~/.config/py-agent/plugins/mcp/mcp_client.py scrape ---> firecrawl scrape
# Firecrawl Search: search <query> — Web search + markdown extraction in 1 step. Example: search llama.cpp metal performance
[TOOL] ~/.config/py-agent/plugins/mcp/mcp_client.py search ---> firecrawl search
```

## 4. Apps (Tools & Utilities)

```properties
# --- Index Map ---
[TOOL] ~/.config/py-agent/tools/index-map/index-map --cat ---> index map, imap
# --- eval-agent (HumanEval Benchmark) ---
~/.config/py-agent/tools/evals/eval-agent ---> eval-agent, eval agent
# --- Weather ---
[TOOL] curl -s "wttr.in/?format=3" --cat ---> weather simple, get weather
[TOOL] curl -s wttr.in --cat ---> weather full, get weather
# --- Time & Date ---
[TOOL] date "+Current System Date, Time: %-I %M %p on %A, %B %-d, %Y" ---> get date, get time
# --- APPS Stopwatch ---
~/.config/py-agent/tools/subsec/apps/stopwatch/stopwatch.py ---> stopwatch app
# --- APPS Media ---
~/.config/py-agent/tools/subsec/apps/media/media.py ---> tuiamp app, tuiamp
# --- Email TUI ---
~/.config/py-agent/tools/email/email-agent ---> email agent
# --- AI Commit ---
~/.config/py-agent/tools/agentic/system/ai-commit ---> ai-commit, gc, git commit
# --- Hyprland State ---
~/.config/py-agent/tools/subsec/hyprstate/work ---> hyprstate work, hyprwork
~/.config/py-agent/tools/subsec/hyprstate/gitcom ---> hyprstate gitcom, gitcom
```

## 5 System & Health

```properties
# --- System Profile ---
[TOOL] cat ~/.config/py-agent/skills/system/mysys.md ---> mysys
[TOOL] ~/.config/py-agent/tools/generate-profile ---> generate profile, genp
# --- System Health ---
[TOOL] ~/.config/py-agent/tools/agentic/system/system-health ---> system health, sysh
# --- Log Checker ---
[TOOL] ~/.config/py-agent/tools/agentic/system/log-checker ---> log checker, ailog
# --- AUR Audit ---
[TOOL] ~/.config/py-agent/tools/agentic/system/aur-audit ---> aur audit, audit package
# --- Security Audit ---
[TOOL] ~/.config/py-agent/tools/agentic/system/security-audit ---> security audit, secaud
# --- System Optimizer ---
[TOOL] ~/.config/py-agent/tools/agentic/system/system-optimizer ---> system optimizer, sysop
# --- Update Inspector ---
[TOOL] ~/.config/py-agent/tools/agentic/system/update-inspector ---> update inspector
```
