# Py-Agent Plugins

> **Syntax**: `[command / execution] ──> [intent1], [intent2], [intent3]`  
> **Delimiter**: `" ---> "` (Three-dash arrow with a trailing space)

---

### Syntax Guide
1. `~/path`: Index workspace and launch session.
2. `ai init --<skill>`: Index workspace with primed skill.
3. `[TOOL] <command> [--s]`: Run background context tool.
4. `<command>`: Launch terminal alias or viewer (`view`).

---

## 0. Start Agent

```properties
# --- Stack Diagnostic Suite ---
[TOOL] ~/.config/py-agent/tools/test-agent --cat --s ---> agent test, ta
# --- Model Selector & .env Provider Configurator ---
~/.config/py-agent/modules/model-select.py ---> model select, cloud model
# --- AI Status Model Route ---
[TOOL] ~/.config/py-agent/tools/agentic/system/ai-status ---> aistatus, aistat, ais
# --- Plugins Cheatsheet ---
[TOOL] ~/.config/py-agent/tools/cheatsheet ---> cheatsheet, cs
# --- Test Model & Profile (Agentic Tool Benchmark) ---
~/.config/py-agent/tools/evals/eval-stack ---> eval-stack, eval stack
```

## 1. Plugins

```properties
# --- PyCode Setup & Build ---
~/.config/py-agent/plugins/pycode/setup.sh ---> install-pycode, setup-pycode, setup pycode
```

## 2. Workspaces

```properties
# --- Workspaces ---
ai init ~/.config/py-agent/projects/sys-ops ---> sys-ops

ai init ~/.config/py-agent/projects/gemini ---> gemini
ai init ~/.config/py-agent/projects/ling-tiny ---> ling-tiny
ai init ~/.config/py-agent/projects/omarchyv4 ---> omarchyv4
ai init ~/.config/py-agent/projects/pysmol-test ---> pysmol test, pysmol
ai init ~/.config/py-agent/projects/minicpm ---> minicpm
ai init ~/.config/py-agent/projects/session-test ---> session test, projects session
ai init ~/.config/py-agent/projects/session-test-2 ---> session test 2, projects session
ai init ~/.config/py-agent/projects/session-test-3 ---> session test 3, projects session
```

## 3. Codebase Map

```properties
# --- Index Map ---
[TOOL] ~/.config/py-agent/tools/index-map/index-map --cat ---> index map, imap
```

## 4. Voice & TTS

```properties
# --- Voice to Text ---
~/.config/py-agent/modules/agent_voice.py ---> voice to text, v2t
# --- Text to Speech (TTS) ---
# killall -9 pw-play koko 2>/dev/null || true --s ---> stop speech, stop talking, kill tts
```

## 5. Web & Files

```properties
# --- Web Reader ---
[TOOL] ~/.config/py-agent/tools/agentic/web/web-reader web $1 ---> web reader, webr
[TOOL] ~/.config/py-agent/tools/agentic/web/web-reader youtube $1 ---> web reader yt, webr
# --- File Reader ---
[TOOL] cat $1 ---> view file, read file, show file, vf

# --- Memories & Hindsight (OKF) ---
[TOOL] cat ~/.config/py-agent/skills/on-demand/hindsight.md --s ---> hindsight
[TOOL] d=".agent/memory"; [[ -d "$d" ]] && (for f in "$d"/*.md; do [[ -f "$f" ]] && { echo -e "\033[1;36m=== $(basename "$f") ===\033[0m"; cat "$f"; echo ""; }; done | less -R) || echo "No memory files found in .agent/memory/." ---> show memories, mem
[TOOL] q="$1"; [[ -z "$q" ]] && read -p "Search Memories: " q; d=".agent/memory"; [[ -d "$d" ]] && grep --color=always -H -n -A 4 -B 1 -i "$q" "$d"/*.md 2>/dev/null || echo "No matches found in .agent/memory/." ---> search memories, ms

# --- History & Transcript Search ---
[TOOL] f=".agent/history.md"; [[ -f "$f" ]] || f="history.md"; [[ -f "$f" ]] && view "$f" | less -R || echo "No history recorded yet." ---> show history, hist, history
[TOOL] q="$1"; [[ -z "$q" ]] && read -p "Search Page: " q; f=".agent/history.md"; [[ -f "$f" ]] || f="history.md"; [[ -f "$f" ]] && grep --color=always -A 15 -B 2 -i "$q" "$f" || echo "No history found." ---> search page, hs
```

## 6. System & Health

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

## 7. TUI Apps

```properties
# --- Email TUI ---
~/.config/py-agent/tools/email/email-agent ---> email agent
# --- Hyprland State ---
~/.config/py-agent/tools/subsec/hyprstate/work ---> hyprstate work, hyprwork
~/.config/py-agent/tools/subsec/hyprstate/gitcom ---> hyprstate gitcom, gitcom
```

## 8. Tools & Utilities

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
