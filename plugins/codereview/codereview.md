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

---

## 2. High-Priority Bugs to Hunt (Real Vulnerabilities)

### A. Terminal State & Cursor Restoration
* In `agent_ui.py` and `agent_core.py`, verify that whenever cursor hiding (`\033[?25l`) or raw terminal mode is enabled, restoration (`\033[?25h` and `termios.tcsetattr`) is guaranteed inside `finally:` blocks or signal handlers. 
* Flag any unhandled exception or early `return` that could leave the user's shell in a corrupted or invisible cursor state.

### B. Subprocess Pipe Deadlocks & Signals
* In `run-review`, `agent_tools.py`, and `agent_ipython.py`, ensure all `subprocess.Popen` or `subprocess.run` calls prevent pipe buffer deadlocks when reading `stdout` and `stderr`.
* Ensure `SIGINT` (Ctrl+C) cleanly terminates child processes without leaving orphaned background processes or hanging subshells.

### C. Zero-Trust Boundary Escapes
* In `agent_security.py` and `agent_tools.py`, scrutinize `_safe_path()` and path containment logic.
* Ensure relative path normalization (`os.path.realpath`, `os.path.abspath`) strictly prevents `../` path traversal outside the active workspace directory, especially when YOLO mode is active.
* Verify that destructive system commands (`sudo`, `pacman`, `systemctl`, `rm -rf`) can NEVER bypass interactive `[y/N]` confirmation gates under any flag.

### D. Concurrency & IPC Hygiene
* In `agent_tui_async.py`, ensure all Unix domain sockets in `/tmp/*.sock` are unlinked upon shutdown or crash.
* Verify thread safety around `threading.Lock()` in `InlineSpinner` to ensure ANSI escape writes to `sys.stderr` cannot interleave with tool output.
* Ensure SQLite database connections in `agent_sessions.py` explicitly handle lock timeouts and close connections on exit.
