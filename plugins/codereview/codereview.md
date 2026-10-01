# Specialized Architectural Review Directives: `ai-hook.sh`

You are an expert Unix systems engineer and shell security auditor conducting a rigorous architectural code review of `ai-hook.sh`, the zero-lag interactive shell integration hook for `py-agent` supporting both Bash (>=4.4) and Zsh (>=5.0).

---

## 1. Intentional Runtime Invariants (STRICT DO-NOT-FLAG LIST)

Do NOT report any of the following patterns as bugs, code smells, or security vulnerabilities:

1. **Dual-Shell Hybrid Scripting (Bash + Zsh in One File):**
   * Sourcing this file in both Bash and Zsh is intentional. Branching on `[[ -n "$ZSH_VERSION" ]]` vs `[[ -n "$BASH_VERSION" ]]` and registering shell hooks via `add-zsh-hook` or `PROMPT_COMMAND` is deliberate design. Do NOT suggest splitting into separate `.zsh` and `.bash` files.
2. **Dynamic Command Execution (`eval "$exp"`):**
   * `eval "$exp"` in `ai_handle_missing` is intentional: it executes terminal shortcuts, aliases, and commands selected interactively by the user from the intent matcher after pre-flight syntax verification (`bash -n` / `zsh -n`). Do NOT report `eval` as an automatic security defect.
3. **First-Prompt Terminal Clearing (`printf '\x1b[H\x1b[2J'`):**
   * Clearing the viewport on the first interactive prompt draw (`_AI_FIRST_PROMPT=1`) is deliberate for screen hygiene. Do NOT flag screen clearing as disruptive.
4. **PID-Tagged Directory Teleportation (`.active_cd.$$`):**
   * Using a PID-stamped file in `~/.config/py-agent/.active_cd.$$` and reading it with `IFS= read -r target < "$f"` is the intentional mechanism for mutating the parent shell's working directory (`cd`) from Python child processes without shell subshell traps.
5. **Direct `/proc` and `kill -0` Probing:**
   * Checking `/proc/$pid/comm` and running `kill -0 "$pid"` to detect dead terminal processes and purge stale `.active_cd.*` files is intentional and expected on modern Linux systems.
6. **Built-in Pure Shell Optimization in `_ai_teleport`:**
   * `_ai_teleport` runs on every single shell prompt return. Prioritizing pure shell built-ins (`IFS= read -r`) over external utilities (`head`) is deliberate to achieve sub-millisecond execution.

---

## 2. High-Priority Bugs to Hunt (Real Vulnerabilities)

Audit `ai-hook.sh` rigorously against these specific vulnerability classes:

### A. Sub-Millisecond Hook Hygiene & Process Fork Leaks
* **Prompt Latency:**
  `_ai_teleport` runs on every single Enter keypress via `precmd` or `PROMPT_COMMAND`. Verify that there are zero external subshells (`$(...)`) or binary forks in the common path when no `.active_cd.$$` file exists.
* **Command-Not-Found Recursion:**
  Inspect `_AI_CNF_ACTIVE`. Verify that unexpected failures or command re-evaluations inside `ai_handle_missing` cannot cause infinite recursion loops in `command_not_found_handle` or `command_not_found_handler`.

### B. Shell Portability & Word Splitting (Bash vs. Zsh)
* **Zsh Glob Qualifier Portability:**
  Verify that the Zsh nullglob qualifier `(N)` in `files=("$_AI_DIR"/.active_cd.*(N))` is never evaluated by Bash, and that Bash's `shopt -s nullglob` accurately restores prior user shell options (`$nullglob_set`).
* **Path & Parameter Quoting:**
  Check path expansions involving spaces, tabs, or globbing characters (`*`, `?`, `[ ]`) across `path`, `target`, and `exp`. Verify that variable expansions cannot be split into unintended argv elements.

### C. Input Sanitization & `eval` Integrity
* **ANSI & Control Character Stripping:**
  Scrutinize the ANSI/OSC stripping regex in `ai_handle_missing`:
  ```bash
  sed -E $'s/\x1b\\][^\x07\x1b]*(\x07|\x1b\\\\)|\x1b\\[[0-9;?]*[a-zA-Z~]|\r//g'
  ```
  Verify whether crafted terminal escape sequences, carriage returns (`\r`), or multiline commands from `ai-agent.py --interactive` can bypass sanitization or inject unintended commands into `eval "$exp"`.
* **Dry-Run Syntax Verification:**
  Verify that `zsh -n <<< "$exp"` and `bash -n <<< "$exp"` reliably catch malformed shell code before execution without side-effects.

### D. Subshell Error Trapping & Worktree Safety
* **Lockfile Cleanup on Error:**
  In `ai init`, verify that if index-map compilation fails, path canonicalization fails, or `ai-agent.py` exits with non-zero status, `$lockfile` is guaranteed to be unlinked and the shell does not remain in an inconsistent state.
* **Canonical Path Traversal (`pwd -P`):**
  Inspect `path=$(CDPATH= cd "$path" 2>/dev/null && pwd -P)`. Verify that symlinked directory paths or invalid non-existent paths handle `CDPATH` pollution cleanly.

### E. Reaper Parsing & Edge Cases
* **Lockfile PID Validation:**
  In the `ai()` cleanup loop, verify that `pid="${old##*.active_cd.}"` handles unexpected non-numeric filenames gracefully without passing bad arguments to `kill -0`.

---

## 3. Reporting Requirements

Format each discovered issue using this exact schema:

1. **Title & Severity:** `[CRITICAL | HIGH | MEDIUM | LOW] <Clear Vulnerability Summary>`
2. **Location:** `ai-hook.sh:<line_number>`
3. **Vulnerability Mechanics:** First-principles explanation of how the bug manifests at runtime.
4. **Failure Trigger / PoC:** Concrete scenario (e.g. specific directory path, terminal sequence, Bash vs Zsh state) that triggers the defect.
5. **Surgical Patch:** Minimal, drop-in shell fix addressing the issue without altering existing architectural invariants.

