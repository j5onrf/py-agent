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
```

## 2. Plugins

```properties
# --- Index Map ---
[TOOL] ~/.config/py-agent/tools/index-map/index-map --cat ---> index map, imap
# --- PyCode Setup & Build ---
~/.config/py-agent/plugins/pycode/setup.sh ---> install-pycode, setup-pycode, setup pycode
```

## 3. Projects

```properties
# --- Workspaces ---
ai init ~/.config/py-agent/projects/nex-n2 ---> nex-n2, nex n2
ai init ~/.config/py-agent/projects/qwen2b ---> qwen2b
ai init ~/.config/py-agent/projects/deepseek ---> deepseek-v4
ai init ~/.config/py-agent/projects/gemini ---> gemini
ai init ~/.config/py-agent/projects/ling-tiny ---> ling-tiny
ai init ~/.config/py-agent/projects/omarchyv4 ---> omarchyv4
ai init ~/.config/py-agent/projects/minicpm ---> minicpm
ai init ~/.config/py-agent/projects/session-test ---> session test, projects session
```

## 4 System & Health

```properties
# --- System Profile ---
[TOOL] cat ~/.config/py-agent/skills/system/mysys.md --s ---> mysys
[TOOL] ~/.config/py-agent/tools/generate-profile ---> generate profile, genp

# --- System Health ---
[TOOL] ~/.config/py-agent/tools/agentic/system/system-health --s ---> system health, sysh
# --- Log Checker ---
[TOOL] ~/.config/py-agent/tools/agentic/system/log-checker --s ---> log checker, ailog
# --- AUR Audit ---
[TOOL] ~/.config/py-agent/tools/agentic/system/aur-audit --s ---> aur audit, audit package
# --- Security Audit ---
[TOOL] ~/.config/py-agent/tools/agentic/system/security-audit --s ---> security audit, secaud
# --- System Optimizer ---
[TOOL] ~/.config/py-agent/tools/agentic/system/system-optimizer ---> system optimizer, sysop
# --- Update Inspector ---
[TOOL] ~/.config/py-agent/tools/agentic/system/update-inspector --s ---> update inspector
# --- Composite System Triage ---
[TOOL] ~/.config/py-agent/tools/agentic/system/system-health --s && ~/.config/py-agent/tools/agentic/system/log-checker --s && ~/.config/py-agent/tools/agentic/system/update-inspector --s ---> triage, full check, syscheck
```

## 5. TUI Apps

```properties
# --- APPS Stopwatch ---
~/.config/py-agent/tools/subsec/apps/stopwatch/stopwatch.py ---> stopwatch app
# --- APPS Media ---
~/.config/py-agent/tools/subsec/apps/media/media.py ---> tuiamp app
# --- Email TUI ---
~/.config/py-agent/tools/email/email-agent ---> email agent
# --- Hyprland State ---
~/.config/py-agent/tools/subsec/hyprstate/work ---> hyprstate work, hyprwork
~/.config/py-agent/tools/subsec/hyprstate/gitcom ---> hyprstate gitcom, gitcom
```

## 5. Tools & Utilities

```properties
# --- eval-agent (HumanEval Benchmark) ---
~/.config/py-agent/tools/evals/eval-agent ---> eval-agent, eval agent
# --- AI Commit ---
~/.config/py-agent/tools/agentic/system/ai-commit ---> ai-commit, gc, git commit
# --- Weather ---
[TOOL] curl -s "wttr.in/?format=3" --cat ---> weather simple, get weather
[TOOL] curl -s wttr.in --cat ---> weather full, get weather
# --- Time & Date ---
[TOOL] date "+Current System Date, Time: %-I %M %p on %A, %B %-d, %Y" ---> get date, get time
