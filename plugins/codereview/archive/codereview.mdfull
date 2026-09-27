# Py-Agent Architectural Review Directives

This project is a lightweight, zero-daemon terminal AI runtime (`rich` + `requests`). Review files against these project-specific architectural invariants:

---

## 1. Intentional Designs (DO NOT Flag as Bugs)

* **Raw TTY / Termios in `agent_ui.py`:** 
  The `_read_fd()` routine intentionally uses `tty.setraw()`, `termios.tcflush()`, and single-byte reads (`os.read(fd, 1)`). Do NOT suggest replacing this with `input()` or higher-level libraries; it is required for non-blocking single-key hotkey navigation.
* **Resilient Diffing in `agent_tools.py`:** 
  The 3-stage replacement (`Exact` -> `Whitespace-Normalized` -> `88% Fuzzy Match`) in `_resilient_replace()` is deliberate to handle indentation drift from small local models. Do NOT suggest strict string matching.
* **Self-Healing Parsers in `agent_adapters.py`:** 
  Custom regex and partial JSON extractors are intentional to rescue malformed JSON and XML calls from ≤27B models. Do NOT suggest replacing them with strict `json.loads()`.
* **Zero-Daemon Architecture:** 
  Do NOT suggest adding background services, Docker containers, Redis, or external vector databases. The architecture is strictly standard library Python + SQLite + Rich.
* **Host Telemetry & System Inspections (`tools/agentic/system/`):**
  Scripts in this directory are administrative triage tools. Reading `/proc`, `/sys/class/hwmon`, `/var/log`, and executing read-only inspection commands (`journalctl`, `systemctl list-units`, `ss -tulnpH`, `pacman -Qm`, `checkupdates`, `df`) is deliberate and authorized. Do NOT flag these inspection commands as security breaches.
* **Semantic IP Masking (`AI_CONTEXT_RUN=1`):**
  In `security-audit`, substituting raw IP addresses and local subnets with semantic tokens (`[localhost]`, `[private-ip]`, `[all-interfaces]`) is an intentional zero-trust privacy layer to prevent leaking network topology to cloud LLMs.

---

## 2. High-Priority Bugs to Hunt (Real Vulnerabilities)

### A. Terminal State & Cursor Restoration
* In `agent_ui.py`, `agent_core.py`, and shell spinner routines (`MinimalSpinner`, `start_spinner`), verify that cursor un-hiding (`\033[?25h`) and terminal mode restoration (`termios.tcsetattr`) are guaranteed inside `finally:` blocks or signal traps (`EXIT INT TERM`).
* Flag any early `return` or unhandled exit that leaves the terminal in raw or invisible cursor mode.

### B. Subprocess Pipe Deadlocks, Signals & `E2BIG` Argv Limits
* In `run-review`, `agent_tools.py`, `agent_ipython.py`, and `aur-audit`, ensure that large multiline inputs (e.g. PKGBUILDs, full diffs, multi-file codeblocks) are streamed via `stdin` or temporary files rather than passed as command-line arguments (`python3 script.py "$PROMPT"`), which crashes with Linux `E2BIG` (Argument list too long).
* Ensure all `subprocess.run` calls without interactive requirements pass `stdin=subprocess.DEVNULL` to prevent blocking the engine indefinitely.
* Ensure all background subshells and processes (`$!`) are tracked and killed in exit traps to prevent orphaned processes.

### C. Symlink & Path Resolution in Shell Utilities
* In `tools/agentic/system/*` (e.g. `syscheck`), verify that script directory resolution uses canonical bash source inspection:
  `cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P`
  Flag any use of raw `dirname "$0"`, which breaks when utilities are symlinked into `~/.local/bin` or executed via `$PATH`.

### D. Safe Environment & Secret Parsing
* In `ai-status` and CLI launchers, flag any use of `source "$ENV_PATH"` or `source .env`. Environment files must be parsed statically to prevent arbitrary code execution from user-controlled strings.
* Verify that indirect variable expansions (such as `${!m_var}`) cannot crash under `set -u` when variable names contain hyphens or non-alphanumeric characters.

### E. Zero-Trust Boundary Escapes
* In `agent_security.py` and `agent_tools.py`, scrutinize `resolve_path()`, `is_outside()`, and path containment logic.
* Ensure path comparisons resolve symlinks (`os.path.realpath`) and use `os.path.commonpath` rather than raw string `.startswith()`.
* Verify that single-component path healing never remaps protected system trees (`/etc`, `/usr`, `/root`, `/tmp`, `/var`) into workspace relative paths.
* Verify that destructive system actions (`sudo`, mutating `pacman`, `systemctl`, `rm -rf /`) can NEVER bypass interactive confirmation gates.

### F. Git Command Flag Injections
* In `ai-commit` and git automation scripts, ensure user-provided strings passed to `git commit -m "$msg"` are terminated with `--` to prevent commit messages starting with `-` from being parsed as command options.
