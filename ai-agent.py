#!/usr/bin/env python3
"""Py Agent [j5onrf] [v0.9.9.41] - Main CLI Runtime, Workspace Agent & Command Dispatcher [Production Ready]"""

import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from contextlib import closing
from typing import Any

CFG_DIR: str = os.path.expanduser("~/.config/py-agent")
CONTEXT_FILE: str = os.path.join(CFG_DIR, "ai-context.md")
SKILLS_DIR: str = os.path.join(CFG_DIR, "skills")
SESSIONS_DIR: str = os.path.join(CFG_DIR, "projects", ".database")

BASE_PROMPT_CHAT: str = "Active, natural conversational assistant."
BASE_PROMPT_AGENT: str = "Active local workspace developer agent."

# Precompiled hot-path regular expressions
RE_THINK_TAGS: re.Pattern = re.compile(r"<think>[\s\S]*?(?:</think>|$)", re.DOTALL)
RE_AUTO_RUN: re.Pattern = re.compile(r"Run:\s*((?:trace symbol|blast radius|read function|find symbol)\s+\S+|architecture overview)")
RE_THINK_BIN: re.Pattern = re.compile(r"^/?(tk|[fba])(?:\s+(\d+))?$", re.IGNORECASE)
RE_SHELL_META: re.Pattern = re.compile(r"[\[\]{}()='\",;|#<>]")


def load_env_file(path: str) -> None:
    """Auto-publishes .env from .env.example and loads variables into os.environ."""
    if not os.path.isfile(path):
        example_p = os.path.join(os.path.dirname(path), ".env.example")
        if os.path.isfile(example_p):
            try:
                shutil.copy2(example_p, path)
            except OSError:
                pass

    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    if (l := line.strip()) and not l.startswith("#") and "=" in l:
                        k, v = l.replace("export ", "", 1).split("=", 1)
                        if (k := k.strip()) and k not in os.environ:
                            os.environ[k] = v.split(" #")[0].strip().strip('"').strip("'")
        except OSError:
            pass


load_env_file(os.path.join(CFG_DIR, ".env"))
if (mod_dir := os.path.join(CFG_DIR, "modules")) not in sys.path:
    sys.path.append(mod_dir)

try:
    import readline
    readline.parse_and_bind(r'"\e[A": previous-history')
    readline.parse_and_bind(r'"\e[B": next-history')
except ImportError:
    pass

try:
    import agent_commands as commands
    import agent_context as context
    import agent_core as core
    import agent_memories as memories
    import agent_sessions as sessions
    import agent_skills as skills
    import agent_tts as tts
    import agent_ui as ui
    import agent_voice as voice
    from agent_context import STOP_WORDS
except ImportError as e:
    sys.stderr.write(f"\033[1;31m[CRITICAL]: Failed to load modules: {e}\033[0m\n")
    sys.exit(1)


_transient_cmd_count: int = 0


def _show_transient_status(tag: str) -> None:
    """Displays an inline status tag with breathing room, accumulating for batch removal on next query."""
    global _transient_cmd_count
    sys.stdout.write(f"  \033[2m[{tag}]\033[0m\n\n")
    sys.stdout.flush()
    _transient_cmd_count += 2


_flash_status = _show_transient_status


def _clear_transient_status(query: str) -> None:
    """Erases the ephemeral slash command block and repositions the real query prompt."""
    global _transient_cmd_count
    if _transient_cmd_count > 0:
        try:
            sys.stdout.write(f"\033[{_transient_cmd_count + 1}A\r\x1b[0J❯ {query}\n")
            sys.stdout.flush()
        except OSError:
            pass
        _transient_cmd_count = 0


def workspace_db_counts(safe_name: str, workspace_path: str = "") -> tuple[int, int]:
    """Retrieves SQLite turn counts and OKF memory counts without spawning empty databases."""
    db_path = os.path.join(SESSIONS_DIR, f"{safe_name}.db")
    t = 0
    if os.path.isfile(db_path):
        try:
            with closing(sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=1.5)) as conn:
                try:
                    t = conn.execute("SELECT COUNT(*) FROM turns WHERE workspace = ?", (safe_name,)).fetchone()[0]
                except (sqlite3.Error, TypeError, IndexError):
                    t = 0
        except sqlite3.Error:
            t = 0
    m_count = memories.get_memory_count(workspace_path) if workspace_path else 0
    return t, m_count


def ensure_clean_agent_dir(workspace_path: str) -> None:
    if not (ws_name := os.path.basename(workspace_path)):
        return
    agent_dir = os.path.join(workspace_path, ".agent")
    try:
        os.makedirs(os.path.join(agent_dir, "memory"), exist_ok=True)
    except OSError:
        return

    targets = [
        f"index-map-{ws_name}.txt",
        f"index-map-memory-{ws_name}.db",
        f"index-map-memory-{ws_name}.db-wal",
        f"index-map-memory-{ws_name}.db-shm",
        "history.md"
    ]
    for fname in targets:
        src = os.path.join(workspace_path, fname)
        if os.path.exists(src):
            try:
                os.replace(src, os.path.join(agent_dir, fname))
            except OSError:
                pass


def _sweep_dead_session_locks() -> None:
    """Removes .session lockfiles whose owning process is dead. Ignores alive processes."""
    sess_dir = os.path.join(CFG_DIR, ".active_sessions")
    if not os.path.isdir(sess_dir):
        return
    for f in os.listdir(sess_dir):
        if not f.endswith(".session"):
            continue
        try:
            pid = int(f.rsplit("-", 1)[-1].replace(".session", ""))
            if pid <= 0:
                continue
            os.kill(pid, 0)
        except ProcessLookupError:
            try:
                os.remove(os.path.join(sess_dir, f))
            except OSError:
                pass
        except (PermissionError, ValueError):
            pass


def clean_exit(safe_name: str | None = None) -> None:
    """Cleans active session locks and exits cleanly."""
    if safe_name:
        try:
            sessions.cleanup_sub_agent(safe_name, os.getpid())
        except Exception:
            pass
    _sweep_dead_session_locks()
    ui._console.print("\n[yellow]Exiting conversation.[/yellow]")
    sys.exit(0)


def _launch_surface(script_path: str, is_agent: bool, ws_path: str, skill: str, history: list, args: list[str] | None = None) -> None:
    """Launches secondary surfaces (TUI, PyCode, WebUI) with state continuity and E2BIG protection."""
    if not os.path.exists(script_path):
        ui._console.print(f"[red][sys] Launcher script not found: {script_path}[/red]\n")
        return

    hist_file = None
    try:
        hist_data = json.dumps(history)
        if len(hist_data) > 65536:
            with tempfile.NamedTemporaryFile("w", delete=False, prefix="ai_hist_", suffix=".json", encoding="utf-8") as tf:
                tf.write(hist_data)
                hist_file = tf.name
    except Exception:
        hist_data = ""

    env = {
        **os.environ,
        "AI_IS_AGENT": "1" if is_agent else "0",
        "AI_WORKSPACE_PATH": ws_path,
        "AI_ACTIVE_SKILL": skill,
        "AI_CONFIRM_GATES": os.environ.get("AI_CONFIRM_GATES", "1"),
    }
    if hist_file:
        env["AI_SESSION_HISTORY_FILE"] = hist_file
        env["AI_SESSION_HISTORY"] = ""
    else:
        env["AI_SESSION_HISTORY"] = hist_data

    cmd = [sys.executable, script_path] if script_path.endswith(".py") else ["/bin/bash", script_path] + (args or [])
    try:
        subprocess.run(cmd, env=env)
        st = core.get_state()
        os.environ["AI_SHOW_THINKING"] = "1" if st.get("show_thinking", True) else "0"
        ui._console.print("[green][sys] Resumed CLI session.[/green]\n")
    except Exception as e:
        ui._console.print(f"[red][sys] Launch failed: {e}[/red]\n")
    finally:
        if hist_file and os.path.exists(hist_file):
            try:
                os.remove(hist_file)
            except OSError:
                pass


def run_interactive_chat(args: list[str]) -> None:
    """Primary interactive agent and chat engine."""
    is_agent = (args[0] == "--talk-chat")
    workspace_path = os.environ.get("AI_WORKSPACE_PATH", os.getcwd())
    home_dir = os.path.expanduser("~")
    safe_name = core.workspace_safe_name(workspace_path, home_dir)

    ensure_clean_agent_dir(workspace_path)
    cfg_file = os.path.join(workspace_path, ".agent", "config.json")
    selected_profile = "pi/pro" if is_agent else "chat"
    is_yolo, use_map, is_py, memory_active, adapters_active = False, False, False, False, False

    # 1. Workspace Profile & Config Resolution (Single-Pass)
    if is_agent:
        if not os.path.exists(cfg_file):
            selected_profile, is_yolo, use_map, is_py, memory_active, adapters_active = ui.select_workspace_profile(os.path.basename(workspace_path))
            try:
                os.makedirs(os.path.dirname(cfg_file), exist_ok=True)
                with open(cfg_file, "w", encoding="utf-8") as cf:
                    json.dump({
                        "profile": selected_profile,
                        "yolo": is_yolo,
                        "map": use_map,
                        "py": is_py,
                        "memory": memory_active,
                        "adapters": adapters_active,
                        "created_at": time.strftime("%Y-%m-%d %H:%M")
                    }, cf, indent=2)
            except OSError:
                pass
        else:
            try:
                with open(cfg_file, "r", encoding="utf-8") as cf:
                    d = json.load(cf)
                    selected_profile = d.get("profile", "pi/pro")
                    is_yolo = bool(d.get("yolo", False))
                    use_map = bool(d.get("map", False))
                    is_py = bool(d.get("py", False))
                    memory_active = bool(d.get("memory", False))
                    adapters_active = bool(d.get("adapters", d.get("adp", False)))
                    if "calm" in d:
                        core.save_state("calm_mode", bool(d["calm"]))
            except (OSError, json.JSONDecodeError):
                pass

    # 2. CLI Profile Overrides & Query Token Cleansing
    profile_args = set()
    for arg in args:
        if arg.startswith("-") and arg not in ("--talk", "--talk-chat"):
            selected_profile = arg.lstrip("-").lower()
            profile_args.add(arg)

    # 3. Persona & Prompt Initialization
    if is_agent:
        clean_name = selected_profile if selected_profile != "init" else "pi/pro"
        profile_content = skills.load_skill_content(clean_name, SKILLS_DIR, CFG_DIR)
        if not profile_content and clean_name != "init":
            ui._console.print(f"[dim yellow][sys] Skill '{clean_name}' not found. Using minimal agent prompt.[/dim yellow]")
        active_system_prompt = profile_content or BASE_PROMPT_AGENT
        os.environ["AI_ACTIVE_SKILL"] = clean_name

        st_init = core.get_state()
        reasoning_budget = st_init.get("reasoning_budget", 500)
        reasoning_active = st_init.get("reasoning_active", reasoning_budget > 0)

        # Workspace config takes precedence for reasoning
        if os.path.isfile(cfg_file):
            try:
                with open(cfg_file, "r", encoding="utf-8") as cf:
                    d = json.load(cf)
                    if "reasoning" in d:
                        reasoning_active = bool(d["reasoning"])
                        core.save_state("reasoning_active", reasoning_active)
                    if "reasoning_budget" in d:
                        reasoning_budget = int(d["reasoning_budget"])
                        core.save_state("reasoning_budget", reasoning_budget)
            except Exception:
                pass

        core.save_state("use_map", use_map)
        core.save_state("yolo_mode", is_yolo)
        core.save_state("ipython_mode", is_py)
        core.save_state("memory_active", memory_active)
        core.save_state("adapters_active", adapters_active)

        os.environ["AI_USE_MAP"] = "1" if use_map else "0"
        os.environ["AI_IPYTHON_MODE"] = "1" if is_py else "0"
        if is_yolo:
            os.environ["AI_CONFIRM_GATES"] = "0"

        # Inject Codespace Map at startup if Map is ON
        if use_map:
            agent_dir = os.path.join(workspace_path, ".agent")
            ws_name = os.path.basename(workspace_path)
            txt_p = os.path.join(agent_dir, f"index-map-{ws_name}.txt")
            db_p = os.path.join(agent_dir, f"index-map-memory-{ws_name}.db")

            imap_bin = os.path.join(CFG_DIR, "tools", "index-map", "index-map")
            if not os.path.isfile(txt_p) or not os.path.isfile(db_p):
                if os.path.isfile(imap_bin):
                    res_map = subprocess.run([sys.executable, imap_bin, "--agent", workspace_path], capture_output=True, text=True)
                    if res_map.returncode == 0:
                        ui._console.print("[dim][sys] Map enabled: compiled index-map.[/dim]")
                    else:
                        ui._console.print(f"[dim yellow][sys] Map compilation failed (rc={res_map.returncode}): {res_map.stderr.strip()[:100]}[/dim yellow]")

            map_path = next((p for p in (txt_p, os.path.join(workspace_path, f"index-map-{ws_name}.txt")) if os.path.exists(p)), None)
            if map_path:
                try:
                    with open(map_path, "r", encoding="utf-8") as mf:
                        new_map = mf.read().strip()
                        if "### CODESPACE MAP:" not in active_system_prompt:
                            active_system_prompt += f"\n\n### CODESPACE MAP:\n{new_map}"
                except OSError:
                    pass
    else:
        clean_name = selected_profile if (selected_profile and selected_profile != "pi/pro") else "chat"
        skill_content = skills.load_skill_content(clean_name, SKILLS_DIR, CFG_DIR)
        if not skill_content and clean_name != "chat":
            ui._console.print(f"[dim yellow][sys] Skill '{clean_name}' not found. Using minimal chat prompt.[/dim yellow]")
        active_system_prompt = skill_content or BASE_PROMPT_CHAT
        os.environ["AI_ACTIVE_SKILL"] = clean_name

    inst_p = os.path.join(SKILLS_DIR, "system_instructions.md")
    if os.path.isfile(inst_p) and os.path.getsize(inst_p) > 0:
        try:
            with open(inst_p, "r", encoding="utf-8") as f:
                rules = [l for l in f if l.strip() and not l.strip().startswith("#")]
                if active_rules := "".join(rules).strip():
                    active_system_prompt += f"\n\n{active_rules}"
        except OSError:
            pass

    pending_args = [a for a in args[1:] if a not in profile_args]
    pending_query = " ".join(pending_args) if pending_args else None

    if pending_query and ("CODEBASE INDEX MAP" in pending_query or "index-map" in pending_query):
        if use_map and "### CODESPACE MAP:" not in active_system_prompt:
            active_system_prompt += f"\n\n### CODESPACE MAP:\n{pending_query}"
        pending_query = None

    chat_history = [{"role": "system", "content": active_system_prompt}]
    if is_agent and not pending_query:
        chat_history.append({"role": "assistant", "content": "Agent: Workspace loaded. Awaiting instructions."})

    st = core.get_state()
    show_stats = st.get("show_stats", True)
    if not is_agent:
        memory_active = st.get("memory_active", False)
    reasoning_active, reasoning_budget = st.get("reasoning_active", False), st.get("reasoning_budget", 500)

    os.environ["AI_RENDER_MARKDOWN"] = "1" if st.get("render_markdown", True) else "0"
    os.environ["AI_REASONIX_ACTIVE"] = "1" if st.get("reasonix_active", True) else "0"
    os.environ["AI_SHOW_THINKING"] = "1" if st.get("show_thinking", True) else "0"
    if is_yolo or st.get("yolo_mode", False):
        os.environ["AI_CONFIRM_GATES"] = "0"

    db_turns, mem_count = workspace_db_counts(safe_name, workspace_path) if is_agent else (0, 0)
    _sweep_dead_session_locks()
    sub_id = sessions.get_sub_agent_id(safe_name, os.getpid()) if is_agent else None

    ui.draw_session_box(workspace_path, home_dir, is_agent, db_turns, mem_count, memory_active, active_system_prompt, clean_name, sub_id=sub_id, box_style=st.get("box_style", 2))

    # 4. Interactive Command & Query Loop
    try:
        while True:
            if pending_query:
                query, pending_query = pending_query, None
            else:
                try:
                    query = voice.get_prompt_input()
                except EOFError:
                    break
                finally:
                    try:
                        readline.set_startup_hook(None)
                    except Exception:
                        pass

                if not query:
                    continue

                # Delegate to modular command dispatcher
                ctx = commands.SessionContext(
                    workspace_path=workspace_path,
                    home_dir=home_dir,
                    safe_name=safe_name,
                    cfg_file=cfg_file,
                    is_agent=is_agent,
                    chat_history=chat_history,
                    active_system_prompt=active_system_prompt,
                    clean_name=clean_name,
                    use_map=use_map,
                    memory_active=memory_active,
                    is_yolo=is_yolo,
                    reasoning_active=reasoning_active,
                    reasoning_budget=reasoning_budget,
                    show_stats=show_stats,
                    flash_status=_flash_status,
                    launch_surface_fn=_launch_surface,
                    clean_exit_fn=clean_exit,
                )

                handled, new_query = commands.dispatch_command(query, ctx)

                # Sync back mutated states
                use_map = ctx.use_map
                memory_active = ctx.memory_active
                is_yolo = ctx.is_yolo
                reasoning_active = ctx.reasoning_active
                reasoning_budget = ctx.reasoning_budget
                show_stats = ctx.show_stats

                if handled:
                    continue
                if new_query:
                    query = new_query

            # Cleanly wipe ephemeral slash commands above when real prompt is submitted
            _clear_transient_status(query)

            memory_ctx = memories.get_memory_context(workspace_path) if (is_agent and memory_active) else ""

            if RE_THINK_BIN.match(query):
                think_bin = next((p for p in (f"{CFG_DIR}/modules/agent_chat.py", f"{CFG_DIR}/modules/chat") if os.path.isfile(p)), None)
                if think_bin:
                    try:
                        subprocess.run([sys.executable, think_bin, query], input=json.dumps(chat_history), text=True)
                        continue
                    except Exception as e:
                        sys.stderr.write(f"\033[1;31m[Warning] chat failed: {e}\033[0m\n")
                continue

            sys_ctx = "" if query.startswith("init") and "--init" in query else skills.get_system_context(query, CONTEXT_FILE, STOP_WORDS, SKILLS_DIR, CFG_DIR)
            if sys_ctx == "__ABORT_TURN__":
                ui._console.print("[yellow][sys] Action cancelled.[/yellow]\n")
                continue

            comb_ctx = "\n\n".join(filter(None, [memory_ctx, sys_ctx]))
            prompt = f"<context>\n{comb_ctx}\n</context>\n\nUser Question: {query}" if comb_ctx else f"User Question: {query}"

            chat_history.append({"role": "user", "content": prompt})
            try:
                readline.add_history(query)
            except Exception:
                pass

            if ans := core.stream_response(chat_history, prefix="Agent:" if is_agent else "AI:", show_stats=show_stats, thinking_budget=reasoning_budget if reasoning_active else 0, is_agent=is_agent):
                clean_ans = RE_THINK_TAGS.sub("", ans).strip()
                chat_history.append({"role": "assistant", "content": clean_ans or ans})

                try:
                    tts.speak_response(clean_ans or ans)
                except Exception as e:
                    if os.environ.get("AI_DEBUG") == "1":
                        sys.stderr.write(f"\r\n[debug] TTS playback error: {e}\r\n")

                if not show_stats:
                    print()

                if is_agent:
                    try:
                        sessions.log_turn(safe_name, query, ans)
                    except Exception as e:
                        if os.environ.get("AI_DEBUG") == "1":
                            sys.stderr.write(f"\r\n[debug] Failed to log turn to SQLite: {e}\r\n")

                    if match := RE_AUTO_RUN.search(ans):
                        try:
                            readline.set_startup_hook(lambda: readline.insert_text(match.group(1).strip()))
                        except Exception:
                            pass

                    agent_dir = os.path.join(workspace_path, ".agent")
                    try:
                        os.makedirs(agent_dir, exist_ok=True)
                        hist_file = os.path.join(agent_dir, "history.md")
                        mode = "a" if os.path.exists(hist_file) else "w"
                        with open(hist_file, mode, encoding="utf-8") as hf:
                            if mode == "w":
                                hf.write(f"# Workspace History: {os.path.basename(workspace_path)}\n\n")
                            hf.write(f"## [{time.strftime('%Y-%m-%d %H:%M')}] User:\n{query}\n\n### Agent:\n{ans}\n\n---\n\n")
                    except OSError as e:
                        if os.environ.get("AI_DEBUG") == "1":
                            sys.stderr.write(f"\r\n[debug] Failed to write history.md: {e}\r\n")
    except KeyboardInterrupt:
        clean_exit(safe_name if is_agent else None)


def run_direct_query(args: list[str]) -> None:
    """Executes instant single-turn CLI prompt without interactive session loop."""
    query_parts = args[1:]
    skill_content = ""
    if query_parts and query_parts[-1].startswith("-"):
        skill_content = skills.load_skill_content(query_parts[-1].lstrip("-").lower(), SKILLS_DIR, CFG_DIR)
        query_parts = query_parts[:-1]

    query = " ".join(query_parts).strip()
    if not query:
        ui._console.print("[dim yellow][sys] Usage: ai --talk <prompt> [-skill][/dim yellow]")
        sys.exit(0)

    if query.lower() in ("/help", "/h", "help", "--help", "-h"):
        ui.show_help()
        sys.exit(0)

    sys_ctx = skills.get_system_context(query, CONTEXT_FILE, STOP_WORDS, SKILLS_DIR, CFG_DIR)
    if sys_ctx == "__ABORT_TURN__":
        sys_ctx = ""

    active_p = skill_content or BASE_PROMPT_CHAT
    inst_p = os.path.join(SKILLS_DIR, "system_instructions.md")
    if os.path.isfile(inst_p) and os.path.getsize(inst_p) > 0:
        try:
            with open(inst_p, "r", encoding="utf-8") as f:
                rules = [l for l in f if l.strip() and not l.strip().startswith("#")]
                if active_rules := "".join(rules).strip():
                    active_p += f"\n\n{active_rules}"
        except OSError:
            pass

    messages = [{"role": "system", "content": active_p}, {"role": "user", "content": f"<context>\n{sys_ctx}\n</context>\n\nUser Question: {query}" if sys_ctx else f"User Question: {query}"}]
    core.stream_response(messages, prefix="AI:", show_stats=False, thinking_budget=0)
    sys.exit(0)


def run_matching_search(args: list[str]) -> None:
    """Sub-millisecond shell intent matcher for command not found hook."""
    user_input = re.sub(r"[`$]", "", " ".join(args)).strip()
    if not user_input or args[0].startswith("--"):
        sys.exit(0)
    if user_input.lower() in ("/help", "/h"):
        ui.show_help()
        sys.exit(0)

    shell_name = os.path.basename(os.environ.get("SHELL", "/bin/bash"))
    err_msg = f"{'zsh' if 'zsh' in shell_name else 'bash'}: {f'command not found: {user_input}' if 'zsh' in shell_name else f'{user_input}: command not found'}\n"
    if RE_SHELL_META.search(user_input):
        sys.stderr.write(err_msg)
        sys.exit(127)

    if matched := context.jaccard_search(user_input, CONTEXT_FILE, STOP_WORDS):
        print("\n".join(f"{l.split('|||', 1)[0]}|||{context.clean_tool_prefix(l.split('|||', 1)[1])}" for l in matched.split("\n")))
        sys.exit(0)
    sys.stderr.write(err_msg)
    sys.exit(127)


def main() -> None:
    try:
        args = sys.argv[1:]
        if not args:
            run_direct_query(["--talk"])
        elif args[0] == "--interactive" and len(args) >= 2:
            shell_name = os.path.basename(os.environ.get("SHELL", ""))
            ui.run_interactive_selection(
                " ".join(args[1:]),
                lambda q: context.jaccard_search(q, CONTEXT_FILE, STOP_WORDS),
                context.clean_tool_prefix,
                lambda n: sys.stderr.write(f"zsh: command not found: {n}\n" if "zsh" in shell_name else f"bash: {n}: command not found\n"),
                lambda: skills.ensure_mysys_exists(SKILLS_DIR, CFG_DIR),
            )
            sys.exit(0)
        elif args[0] in ("--talk", "--talk-chat"):
            run_interactive_chat(args) if (args[0] == "--talk-chat" or len(args) == 1) else run_direct_query(args)
            sys.exit(0)
        else:
            run_matching_search(args)
    except KeyboardInterrupt:
        sys.stderr.write("\nCancelled.\n")
        sys.exit(130)


if __name__ == "__main__":
    main()
