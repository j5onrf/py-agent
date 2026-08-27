#!/usr/bin/env python3
"""SQLite-backed semantic recall and Temporal Personality Memory (TPM) manager [In-Memory Module & CLI]"""

import json
import os
import re
import select
import sqlite3
import sys
import time
from contextlib import closing

try:
    import termios
    import tty
except ImportError:
    pass

CFG_DIR: str = os.path.expanduser("~/.config/py-agent")
SESSIONS_DIR: str = os.path.join(CFG_DIR, "projects", "database")
BLACKLIST = frozenset(
    {
        "files",
        "file",
        "file_list",
        "project",
        "code",
        "description",
        "features",
        "dependencies",
        "project_type",
        "directory",
        "folder",
        "workspace",
    }
)

sys.path.append(os.path.join(CFG_DIR, "modules"))
try:
    from agent_context import STOP_WORDS, tokenize
except ImportError:
    TOKEN_RE: re.Pattern = re.compile(r"[^\w\s]")
    STOP_WORDS = frozenset(
        {
            "is",
            "what",
            "it",
            "do",
            "any",
            "i",
            "have",
            "the",
            "a",
            "an",
            "on",
            "to",
            "for",
            "me",
            "you",
            "my",
            "your",
            "we",
            "us",
            "are",
            "about",
            "in",
            "how",
        }
    )

    def tokenize(text: str) -> list[str]:
        return (
            [
                w
                for w in TOKEN_RE.sub(" ", text.lower()).split()
                if len(w) > 1 and w not in STOP_WORDS
            ]
            if text
            else []
        )


def get_key() -> str:
    """Self-contained keyboard reader without importing agent_ui."""
    if not sys.stdin.isatty():
        try:
            with open("/dev/tty", "r") as f:
                fd = f.fileno()
                old = termios.tcgetattr(fd)
                try:
                    tty.setraw(fd)
                    r = os.read(fd, 1)
                    if r == b"\x1b" and select.select([fd], [], [], 0.05)[0]:
                        r += os.read(fd, 2)
                    return r.decode("utf-8", errors="ignore")
                finally:
                    termios.tcsetattr(fd, termios.TCSADRAIN, old)
        except Exception:
            return ""
    fd = sys.stdin.fileno()
    try:
        old = termios.tcgetattr(fd)
    except Exception:
        return sys.stdin.read(1)
    try:
        tty.setraw(fd)
        r = os.read(fd, 1)
        if r == b"\x1b" and select.select([fd], [], [], 0.05)[0]:
            r += os.read(fd, 2)
        return r.decode("utf-8", errors="ignore")
    except Exception:
        return ""
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def connect_db(db_path: str) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=30.0)
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout = 30000;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS tpm_memories (key TEXT PRIMARY KEY, value TEXT, timestamp INTEGER);"
        )
        conn.commit()
    except sqlite3.Error:
        pass
    return conn


def tpm_get(workspace: str) -> str:
    """Direct in-memory fact retrieval (< 0.1ms)."""
    db_path = os.path.join(SESSIONS_DIR, f"{workspace}.db")
    if os.path.exists(db_path):
        try:
            with closing(connect_db(db_path)) as conn:
                if (
                    rows := conn.cursor()
                    .execute("SELECT key, value FROM tpm_memories ORDER BY key")
                    .fetchall()
                ):
                    return (
                        "### TEMPORAL PERSONALITY MEMORY (TPM):\nThe following are compiled, up-to-date facts and style preferences about the user:\n"
                        + "\n".join(f"* **{k}**: {v}" for k, v in rows)
                        + "\n"
                    )
        except sqlite3.Error:
            pass
    return ""


def tpm_reconcile(workspace: str, facts: dict[str, str] | None = None) -> None:
    """Direct in-memory or stdin reconciliation into SQLite (< 0.2ms)."""
    if facts is None:
        try:
            facts = json.loads(sys.stdin.read().strip())
        except Exception:
            return
    if not facts or not isinstance(facts, dict):
        return

    with closing(connect_db(os.path.join(SESSIONS_DIR, f"{workspace}.db"))) as conn:
        with conn:
            cur, now = conn.cursor(), int(time.time())
            for k, v in facts.items():
                k_clean, v_clean = str(k).strip().lower(), str(v).strip()
                if k_clean in BLACKLIST:
                    continue
                if not v_clean or v_clean.lower() in (
                    "none",
                    "null",
                    "removed",
                    "deleted",
                ):
                    cur.execute("DELETE FROM tpm_memories WHERE key = ?", (k_clean,))
                else:
                    cur.execute(
                        "INSERT OR REPLACE INTO tpm_memories (key, value, timestamp) VALUES (?, ?, ?)",
                        (k_clean, v_clean, now),
                    )


def tpm_clear(workspace: str) -> None:
    db_path = os.path.join(SESSIONS_DIR, f"{workspace}.db")
    if os.path.exists(db_path):
        try:
            with closing(connect_db(db_path)) as conn, conn:
                conn.cursor().execute("DELETE FROM tpm_memories")
        except sqlite3.Error:
            pass


def get_tpm_count(workspace: str) -> int:
    db_path = os.path.join(SESSIONS_DIR, f"{workspace}.db")
    if os.path.exists(db_path):
        try:
            with closing(connect_db(db_path)) as conn:
                return (
                    conn.cursor()
                    .execute("SELECT COUNT(*) FROM tpm_memories")
                    .fetchone()[0]
                )
        except sqlite3.Error:
            pass
    return 0


def search_past_context(workspace: str, query: str) -> str:
    """Semantic Recall: Searches past turns directly in-memory."""
    q_tokens = set(tokenize(query))
    if not q_tokens:
        return ""
    db_path = os.path.join(SESSIONS_DIR, f"{workspace}.db")
    if not os.path.exists(db_path):
        return ""

    with closing(connect_db(db_path)) as conn:
        try:
            rows = (
                conn.cursor()
                .execute(
                    "SELECT id, tokens, timestamp FROM turns WHERE workspace = ? ORDER BY timestamp DESC LIMIT 500",
                    (workspace,),
                )
                .fetchall()
            )
        except sqlite3.OperationalError:
            return ""

        matching_ids = []
        for row_id, tokens, ts in rows:
            t_tokens = set(tokens.split()) if tokens else set()
            if (
                score := len(q_tokens & t_tokens) / len(q_tokens | t_tokens)
                if (q_tokens & t_tokens)
                else 0.0
            ) >= 0.35:
                matching_ids.append((score, row_id, ts))

        if not matching_ids:
            return ""
        matching_ids.sort(key=lambda x: -x[0])
        top_matches = matching_ids[:10]

        candidates = []
        for score, row_id, ts in top_matches:
            try:
                row = (
                    conn.cursor()
                    .execute(
                        "SELECT user_msg, assistant_msg FROM turns WHERE id = ?",
                        (row_id,),
                    )
                    .fetchone()
                )
                if row:
                    candidates.append((score, row[0], row[1], ts))
            except sqlite3.OperationalError:
                pass

    if not candidates:
        return ""
    num_opts, current_idx = len(candidates), 0
    sys.stderr.write("\033[?25l")
    sys.stderr.flush()

    try:
        while True:
            _, user_msg, assistant_msg, ts = candidates[current_idx]
            idx_str = (
                f"[{current_idx + 1:02d}/{num_opts:02d}] ❯ " if num_opts > 1 else ""
            )
            disp = user_msg.strip().replace("\n", " ")
            date_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))
            sys.stderr.write(
                f'\r\x1b[K\033[2m{idx_str}[memory] ({date_str})\033[0m\n\r\x1b[K\033[3m   "{disp[:47] + "..." if len(disp) > 40 else disp}"\033[0m [↵ load  d: disable  Esc/Arrows: skip]: '
            )
            sys.stderr.flush()

            key = get_key()
            sys.stderr.write("\r\x1b[K\x1b[1A\r\x1b[K")
            sys.stderr.flush()

            if key == "\x03":
                sys.stderr.write("Cancelled.\n")
                return "__CANCELLED__"
            elif key in ("\r", "\n"):
                sys.stderr.write("\033[2;32m[sys] Memory injected.\033[0m\n")
                return f'\n### Relevant Past Discussion (Retrieved from Session Memory):\n* **On {date_str} you asked**: "{user_msg}"\n  **Agent responded**: "{assistant_msg.strip()}"'
            elif key in ("d", "D"):
                sys.stderr.write(
                    "\033[2;31m[sys] Memory recall disabled. (Type /m to re-enable)\033[0m\n"
                )
                return "__DISABLE_MEMORY__"
            elif key in ("\x1b[A", "\x1b[B"):
                current_idx = (
                    current_idx + (1 if key == "\x1b[B" else -1) + num_opts
                ) % num_opts
            else:
                sys.stderr.write("\033[2;31m[sys] Memory recall skipped.\033[0m\n")
                return ""
    finally:
        sys.stderr.write("\033[?25h")
        sys.stderr.flush()


if __name__ == "__main__":
    if len(args := sys.argv[1:]) >= 2:
        cmd, ws = args[0], args[1]
        if cmd == "get-context":
            if out := search_past_context(ws, args[2] if len(args) > 2 else ""):
                if out not in ("__CANCELLED__", "__DISABLE_MEMORY__"):
                    print(out)
        elif cmd == "tpm-reconcile":
            tpm_reconcile(ws)
        elif cmd == "tpm-get":
            if res := tpm_get(ws):
                print(res)
        elif cmd == "tpm-clear":
            tpm_clear(ws)
        elif cmd == "get-tpm-count":
            print(get_tpm_count(ws))
