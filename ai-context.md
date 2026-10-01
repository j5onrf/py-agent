# Py-Agent Config

> **Syntax**: `[command / execution] ──> [intent1], [intent2], [intent3]`  
> **Delimiter**: `" ‑‑‑> "` (Three-dash arrow with a trailing space)

---

### Syntax Guide
1. `ai init [path]`: Index workspace and launch interactive agent session.
2. `ai init --<skill> [path]`: Index workspace primed with a specific agent skill.
3. `[TOOL] <command>`: Execute system tool (prompts for `[Y/n]` authorization).
4. `[TOOL] <command> --s`: Execute tool silently (bypasses confirmation gate).
5. `<command>`: Terminal shortcut, alias, or file viewer.

---

## 1. Start Agent

```properties
# --- Agent Diagnostic ---
[TOOL] ~/.config/py-agent/tools/test-agent --cat ---> agent test, ta
# --- Model Selector ---
~/.config/py-agent/modules/model-select.py ---> model select, cloud model
# --- Project Creator ---
~/.config/py-agent/tools/new-project ---> new project, newp
# --- AI Status ---
[TOOL] ~/.config/py-agent/tools/system/ai-status --cat ---> aistatus, aistat, ais
# --- Cheatsheet ---
[TOOL] ~/.config/py-agent/tools/cheatsheet --cat ---> cheatsheet, cs
# --- Eval Model & Profile (Agentic Tool Benchmark) ---
~/.config/py-agent/tools/evals/eval-stack --->  eval stack, eval-stack, eva
# --- System Orchestrator TUI ---
[TOOL] ~/.config/py-agent/tools/system-stack ---> system stack, sysstack, syscheck
# --- Omarchy Desktop Control Hub ---
~/.config/py-agent/tools/omarchy ---> omarchy hub, oma
```

## 2. Projects

```properties
# --- Workspaces ---
ai init ~/.config/py-agent/projects/tielcoder ---> tielcoder
ai init ~/.config/py-agent/projects/qwen38d ---> qwen38d
ai init ~/.config/py-agent/projects/nemotron ---> nemotron
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
# --- Open-Code-Review ---
~/.config/py-agent/plugins/codereview/run-review ---> open code review, cr
# --- Model Context Protocol (MCP) ---
~/.config/py-agent/plugins/mcp/mcp_client.py list ---> mcp list, mcp tools, mcpl
```

## 4. Apps (Tools & Utilities)

```properties
# --- Index Map ---
[TOOL] ~/.config/py-agent/tools/index-map/index-map --cat ---> index map, imap
# --- Weather ---
[TOOL] curl -s "wttr.in/?format=3" --cat ---> weather simple, get weather
[TOOL] curl -s wttr.in --cat ---> weather full, get weather
# --- Time & Date ---
[TOOL] date "+Current System Date, Time: %-I %M %p on %A, %B %-d, %Y" ---> get date, get time
# --- APPS Stopwatch ---
~/.config/py-agent/tools/subsec/apps/stopwatch/stopwatch.py ---> stopwatch app
# --- APPS Tuiamp ---
~/.config/py-agent/tools/subsec/apps/media/media.py ---> tuiamp app, tuiamp
# --- Email TUI ---
~/.config/py-agent/tools/email/email-agent ---> email agent
# --- AI Commit ---
~/.config/py-agent/tools/system/ai-commit ---> ai-commit, gc, git commit
# --- Hyprland State ---
~/.config/py-agent/tools/subsec/hyprstate/work ---> hyprstate work, hyprwork, hyprw
~/.config/py-agent/tools/subsec/hyprstate/gitcom ---> hyprstate gitcom, gitcom, gitc
```

## 5. System & Health

```properties
# --- System Profile ---
[TOOL] cat ~/.config/py-agent/skills/system/mysys.md --cat ---> mysys
[TOOL] ~/.config/py-agent/tools/generate-profile --cat ---> generate profile, genp
# --- System Health ---
[TOOL] ~/.config/py-agent/tools/system/system-health --cat ---> system health, sysh
# --- Log Checker ---
[TOOL] ~/.config/py-agent/tools/system/log-checker --cat ---> log checker, ailog
# --- AUR Audit ---
[TOOL] ~/.config/py-agent/tools/system/aur-audit --cat ---> aur audit, aurp
# --- Security Audit ---
[TOOL] ~/.config/py-agent/tools/system/security-audit --cat ---> security audit, secaud
# --- System Optimizer ---
[TOOL] ~/.config/py-agent/tools/system/system-optimizer --cat ---> system optimizer, sysop
# --- Update Inspector ---
[TOOL] ~/.config/py-agent/tools/system/update-inspector --cat ---> update inspector, upi
```
