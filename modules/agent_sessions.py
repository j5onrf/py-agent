#!/usr/bin/env python3
"""SQLite-backed session, checkpoint, and turn logger with sub-agent registry [Self-Healing In-Memory Module & CLI]"""

import glob
import json
import os
import re
import sqlite3
import sys
import time
from contextlib import closing
from typing import Any, List, Optional

CFG_DIR: str = os.path.expanduser("~/.config/py-agent")
SESSIONS_DIR: str = os.path.join(CFG_DIR, "projects", "database")
os.makedirs(SESSIONS_DIR, exist_ok=True)

sys.path.append(os.path.join(CFG_DIR, "modules"))
try:
    from agent_context import STOP_WORDS, tokenize
except ImportError:
    TOKEN_RE: re.Pattern = re.compile(r"[^\w\s]")
    STOP_WORDS = frozenset({"is", "what", "it", "do", "any", "i", "have", "the", "a", "an", "on", "to", "for", "me", "you", "my", "your", "we", "us", "are", "about", "in", "how"})
    def tokenize(text: str) -> List[str]:
        return [w for w in TOKEN_RE.sub(" ", text.lower()).split() if len(w) > 1 and w not in STOP_WORDS] if text else []


def get_key() -> str:
    """Self-contained keyboard reader without importing agent_ui."""
    import select, termios, tty
    if not sys.stdin.isatty():
        try:
            with open("/dev/tty", "r") as f:
                fd = f.fileno()
                old = termios.tcgetattr(fd)
                try:
                    tty.setraw(fd)
                    r = os.read(fd, 1)
                    if r == b'\x1b' and select.select([fd], [], [], 0.05)[0]: r += os.read(fd, 2)
                    return r.decode("utf-8", errors="ignore")
                finally: termios.tcsetattr(fd, termios.TCSADRAIN, old)
        except Exception: return ""
    fd = sys.stdin.fileno()
    try: old = termios.tcgetattr(fd)
    except Exception: return sys.stdin.read(1)
    try:
        tty.setraw(fd)
        r = os.read(fd, 1)
        if r == b'\x1b' and select.select([fd], [], [], 0.05)[0]: r += os.read(fd, 2)
        return r.decode("utf-8", errors="ignore")
    except Exception: return ""
    finally: termios.tcsetattr(fd, termios.TCSADRAIN, old)


def connect_db(db_path: str) -> sqlite3.Connection:
    """Self-healing SQLite connection that automatically ensures all tables & indexes exist."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=30.0)
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout = 30000;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS checkpoints (id INTEGER PRIMARY KEY AUTOINCREMENT, workspace TEXT NOT NULL, tag TEXT NOT NULL, history TEXT NOT NULL, timestamp INTEGER NOT NULL);")
        cur.execute("CREATE TABLE IF NOT EXISTS turns (id INTEGER PRIMARY KEY AUTOINCREMENT, workspace TEXT NOT NULL, user_msg TEXT NOT NULL, assistant_msg TEXT NOT NULL, tokens TEXT NOT NULL, timestamp INTEGER NOT NULL);")
        cur.execute("CREATE TABLE IF NOT EXISTS tpm_memories (key TEXT PRIMARY KEY, value TEXT NOT NULL, timestamp INTEGER NOT NULL);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_turns_workspace ON turns (workspace);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_checkpoints_workspace ON checkpoints (workspace);")
        conn.commit()
    except sqlite3.Error:
        pass
    return conn


def get_sub_agent_id(workspace: str, target_pid: Optional[int] = None) -> int:
    session_dir = os.path.join(CFG_DIR, ".active_sessions")
    os.makedirs(session_dir, exist_ok=True)
    current_pid = target_pid or os.getpid()

    active_pids = []
    for fpath in glob.glob(os.path.join(session_dir, f"{workspace}-*.session")):
        try:
            pid = int(os.path.basename(fpath).replace(f"{workspace}-", "").replace(".session", ""))
            os.kill(pid, 0)
            active_pids.append(pid)
        except ProcessLookupError:
            try: os.remove(fpath)
            except OSError: pass
        except (ValueError, OSError):
            active_pids.append(pid)

    if current_pid not in active_pids: active_pids.append(current_pid)
    active_pids.sort()
    agent_index = active_pids.index(current_pid)

    try:
        with open(os.path.join(session_dir, f"{workspace}-{current_pid}.session"), "w", encoding="utf-8") as f:
            f.write(str(agent_index))
    except OSError: pass
    return agent_index


def cleanup_sub_agent(workspace: str, target_pid: Optional[int] = None) -> None:
    try:
        p = os.path.join(CFG_DIR, ".active_sessions", f"{workspace}-{(target_pid or os.getpid())}.session")
        if os.path.exists(p): os.remove(p)
    except OSError: pass


def init_db(workspace: str) -> None:
    """Wrapper that ensures DB and tables exist."""
    db_path = os.path.join(SESSIONS_DIR, f"{workspace}.db")
    with closing(connect_db(db_path)) as conn:
        pass


def save_checkpoint(workspace: str, tag: str, history_obj: Any = None) -> None:
    if history_obj is not None:
        hist_data = json.dumps(history_obj) if not isinstance(history_obj, str) else history_obj
    else:
        try: hist_data = sys.stdin.read().strip(); json.loads(hist_data)
        except Exception: return

    with closing(connect_db(os.path.join(SESSIONS_DIR, f"{workspace}.db"))) as conn:
        conn.cursor().execute("INSERT INTO checkpoints (workspace, tag, history, timestamp) VALUES (?, ?, ?, ?)", (workspace, tag, hist_data, int(time.time())))
        conn.commit()
    sys.stderr.write(f"\033[1;32m[session-mgr] Checkpoint '{tag}' saved to SQLite.\033[0m\n")


def rollback_checkpoint(workspace: str) -> Optional[list[dict[str, Any]]]:
    db_path, rows, global_rows = os.path.join(SESSIONS_DIR, f"{workspace}.db"), [], []
    if os.path.exists(db_path):
        with closing(connect_db(db_path)) as conn:
            rows = conn.cursor().execute("SELECT tag, history, timestamp FROM checkpoints WHERE workspace = ? ORDER BY timestamp DESC LIMIT 50", (workspace,)).fetchall()

    is_global = not bool(rows)
    if is_global:
        for f in os.listdir(SESSIONS_DIR):
            if f.endswith(".db") and f != f"{workspace}.db":
                try:
                    with closing(connect_db(os.path.join(SESSIONS_DIR, f))) as conn_g:
                        for tag, history, ts in conn_g.cursor().execute("SELECT tag, history, timestamp FROM checkpoints ORDER BY timestamp DESC LIMIT 5").fetchall():
                            global_rows.append((tag, history, ts, f[:-3]))
                except sqlite3.Error: pass

    if not rows and not global_rows:
        sys.stderr.write("\033[1;31m[session-mgr] No checkpoints found locally or globally.\033[0m\n")
        return None

    display_rows = global_rows if is_global else rows
    sys.stderr.write(f"\n\033[1;36m--- {'Global Checkpoints (Clonable)' if is_global else 'Active Checkpoints (SQLite)'} ---\033[0m\n")

    for idx, item in enumerate(display_rows):
        tag, history, ts = item[0], item[1], item[2]
        src_info = f" \033[1;30m(from '{item[3]}')\033[0m" if is_global else ""
        try: turns_len = len(json.loads(history))
        except json.JSONDecodeError: turns_len = 0
        sys.stderr.write(f"[{idx}] \033[1;32m{tag}\033[0m ({turns_len} turns){src_info} - {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(ts))}\n")

    sys.stderr.write(f"\n\033[2mSelect index to {'clone and load' if is_global else 'load'}, or press Esc to cancel: \033[0m\033[?25l")
    sys.stderr.flush()

    try:
        while True:
            key = get_key()
            if key in ('\x03', '\x1b', 'q', 'Q', ''):
                sys.stderr.write("\r\x1b[KCancelled.\n")
                return None

            if key.isdigit() and int(key) < len(display_rows):
                selected = display_rows[int(key)]
                if is_global:
                    tag, history, ts, src_ws = selected
                    with closing(connect_db(db_path)) as conn3:
                        conn3.cursor().execute("INSERT OR REPLACE INTO checkpoints (workspace, tag, history, timestamp) VALUES (?, ?, ?, ?)", (workspace, tag, history, int(time.time())))
                        conn3.commit()
                sys.stderr.write(f"\r\x1b[K\033[1;32m[session-mgr] Checkpoint '{selected[0]}' loaded!\033[0m\n")
                return json.loads(selected[1])
    finally:
        sys.stderr.write("\033[?25h")
        sys.stderr.flush()


def log_turn(workspace: str, user_msg: str, assistant_msg: str) -> None:
    clean_user = user_msg.split("User Question:", 1)[-1].strip() if "User Question:" in user_msg else user_msg
    tokens_str = " ".join(tokenize(clean_user))
    with closing(connect_db(os.path.join(SESSIONS_DIR, f"{workspace}.db"))) as conn:
        conn.cursor().execute("INSERT INTO turns (workspace, user_msg, assistant_msg, tokens, timestamp) VALUES (?, ?, ?, ?, ?)", (workspace, clean_user, assistant_msg, tokens_str, int(time.time())))
        conn.commit()


def get_turns_count(workspace: str) -> int:
    db_path = os.path.join(SESSIONS_DIR, f"{workspace}.db")
    if os.path.exists(db_path):
        try:
            with closing(connect_db(db_path)) as conn:
                return conn.cursor().execute("SELECT COUNT(*) FROM turns WHERE workspace = ?", (workspace,)).fetchone()[0]
        except sqlite3.Error: pass
    return 0


def clear_turns(workspace: str) -> None:
    db_path = os.path.join(SESSIONS_DIR, f"{workspace}.db")
    if os.path.exists(db_path):
        try:
            with closing(connect_db(db_path)) as conn:
                conn.cursor().execute("DELETE FROM turns WHERE workspace = ?", (workspace,))
                conn.commit()
        except sqlite3.Error: pass


if __name__ == "__main__":
    if not (args := sys.argv[1:]): sys.exit(1)
    cmd = args[0]
    if len(args) < 2: sys.exit(1)
    workspace_name = args[1]

    if cmd == "save": save_checkpoint(workspace_name, args[2] if len(args) > 2 else "")
    elif cmd == "load":
        if hist := rollback_checkpoint(workspace_name): print(json.dumps(hist))
    elif cmd == "log-turn" and len(args) >= 4: log_turn(workspace_name, args[2], args[3])
    elif cmd == "get-count": print(get_turns_count(workspace_name))
    elif cmd == "clear": clear_turns(workspace_name)
    elif cmd == "get-sub-id": print(get_sub_agent_id(workspace_name, int(args[2]) if len(args) > 2 else os.getppid()))
    elif cmd == "cleanup-sub": cleanup_sub_agent(workspace_name, int(args[2]) if len(args) > 2 else os.getppid())
