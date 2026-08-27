#!/usr/bin/env python3
"""Py Agent [j5onrf] [v0.9.8.95] - Pure Standard In-Memory Architecture"""

import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
from contextlib import closing

CFG_DIR: str = os.path.expanduser("~/.config/py-agent")
CONTEXT_FILE: str = os.path.join(CFG_DIR, "ai-context.md")
SKILLS_DIR: str = os.path.join(CFG_DIR, "skills")
SESSIONS_DIR: str = os.path.join(CFG_DIR, "projects", "database")

BASE_PROMPT_CHAT: str = "Active, natural conversational assistant."
BASE_PROMPT_AGENT: str = "Active local workspace developer agent."

try:
    from agent_context import STOP_WORDS
except ImportError:
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


def load_env_file(path: str) -> None:
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    if (l := line.strip()) and not l.startswith("#") and "=" in l:
                        k, v = l.replace("export ", "", 1).split("=", 1)
                        if (k := k.strip()) and k not in os.environ:
                            os.environ[k] = (
                                v.split(" #")[0].strip().strip('"').strip("'")
                            )
        except OSError:
            pass


load_env_file(os.path.join(CFG_DIR, ".env"))
sys.path.append(os.path.join(CFG_DIR, "modules"))

try:
    import readline

    readline.parse_and_bind(r'"\e[A": previous-history')
    readline.parse_and_bind(r'"\e[B": next-history')
except ImportError:
    pass

try:
    import agent_context as context
    import agent_core as core
    import agent_ipython as ipython
    import agent_memories as memories
    import agent_sessions as sessions
    import agent_skills as skills
    import agent_tts as tts
    import agent_ui as ui
    import agent_voice as voice
except ImportError as e:
    sys.stderr.write(f"\033[1;31m[CRITICAL]: Failed to load modules: {e}\033[0m\n")
    sys.exit(1)


def workspace_db_counts(safe_name: str) -> tuple[int, int]:
    """In-memory direct SQLite counts to eliminate process-spawning startup latency."""
    db_path = os.path.join(SESSIONS_DIR, f"{safe_name}.db")
    turns, facts = 0, 0
    if os.path.exists(db_path):
        try:
            with closing(sqlite3.connect(db_path, timeout=2.0)) as conn:
                cur = conn.cursor()
                try:
                    turns = cur.execute(
                        "SELECT COUNT(*) FROM turns WHERE workspace = ?",
                        (safe_name,),
                    ).fetchone()[0]
                except sqlite3.OperationalError:
                    pass
                try:
                    facts = cur.execute(
                        "SELECT COUNT(*) FROM tpm_memories"
                    ).fetchone()[0]
                except sqlite3.OperationalError:
                    pass
        except sqlite3.Error:
            pass
    return turns, facts


def ensure_clean_agent_dir(workspace_path: str) -> None:
    """Relocates auto-created agent files (and SQLite WAL companions) into project/.agent/."""
    if not (ws_name := os.path.basename(workspace_path)):
        return
    agent_dir = os.path.join(workspace_path, ".agent")

    files_to_relocate = [
        f"index-map-{ws_name}.txt",
        f"index-map-memory-{ws_name}.db",
        f"index-map-memory-{ws_name}.db-wal",
        f"index-map-memory-{ws_name}.db-shm",
        "history.md",
        "tpm.md",
    ]

    for fname in files_to_relocate:
        src = os.path.join(workspace_path, fname)
        if os.path.exists(src):
            os.makedirs(agent_dir, exist_ok=True)
            try:
                os.replace(src, os.path.join(agent_dir, fname))
            except OSError:
                pass


def sync_md_to_sqlite(workspace: str, workspace_path: str) -> None:
    """Direct in-memory TPM synchronization from markdown to SQLite."""
    md_path = os.path.join(workspace_path, ".agent", "tpm.md")
    if os.path.exists(md_path):
        try:
            with open(md_path, "r", encoding="utf-8") as f:
                matches = re.findall(r"\*\s+\*\*([^*]+)\*\*:\s*(.*)", f.read())
            if matches:
                facts_dict = {k.strip().lower(): v.strip() for k, v in matches}
                memories.tpm_reconcile(workspace, facts_dict)
        except Exception:
            pass


def clean_exit(safe_name: str | None = None) -> None:
    if safe_name:
        try:
            sessions.cleanup_sub_agent(safe_name, os.getpid())
        except Exception:
            pass
    ui._console.print("\n[yellow]Exiting conversation.[/yellow]")
    sys.exit(0)


def run_interactive_chat(args: list[str]) -> None:
    is_agent = args[0] == "--talk-chat"
    workspace_path = os.environ.get("AI_WORKSPACE_PATH", os.getcwd())
    home_dir = os.path.expanduser("~")
    safe_name = core.workspace_safe_name(workspace_path, home_dir)

    ensure_clean_agent_dir(workspace_path)
    cfg_file = os.path.join(workspace_path, ".agent", "config.json")
    selected_profile = "pi/pro" if is_agent else "chat"
    is_yolo, use_map = False, False

    if is_agent:
        if not os.path.exists(cfg_file):
            selected_profile, is_yolo, use_map = ui.select_workspace_profile(
                os.path.basename(workspace_path)
            )
            try:
                os.makedirs(os.path.dirname(cfg_file), exist_ok=True)
                with open(cfg_file, "w", encoding="utf-8") as cf:
                    json.dump(
                        {
                            "profile": selected_profile,
                            "yolo": is_yolo,
                            "map": use_map,
                            "created_at": time.strftime("%Y-%m-%d %H:%M"),
                        },
                        cf,
                        indent=2,
                    )
            except OSError:
                pass
        else:
            try:
                with open(cfg_file, "r", encoding="utf-8") as cf:
                    cfg_data = json.load(cf)
                    selected_profile = cfg_data.get("profile", "pi/pro")
                    is_yolo = cfg_data.get("yolo", False)
                    use_map = cfg_data.get("map", False)
            except (OSError, json.JSONDecodeError):
                pass

    for arg in args:
        if arg.startswith("-") and arg not in ("--talk", "--talk-chat"):
            selected_profile = arg.lstrip("-").lower()

    if is_agent:
        clean_name = selected_profile if selected_profile != "init" else "pi/pro"
        profile_content = skills.load_skill_content(clean_name, SKILLS_DIR, CFG_DIR)
        if not profile_content and clean_name != "init":
            ui._console.print(
                f"[dim yellow][sys] Skill '{clean_name}' not found. Using minimal agent prompt.[/dim yellow]"
            )
        active_system_prompt = profile_content or BASE_PROMPT_AGENT
    else:
        clean_name = (
            selected_profile
            if (selected_profile and selected_profile != "pi/pro")
            else "chat"
        )
        skill_content = skills.load_skill_content(clean_name, SKILLS_DIR, CFG_DIR)
        if not skill_content and clean_name != "chat":
            ui._console.print(
                f"[dim yellow][sys] Skill '{clean_name}' not found. Using minimal chat prompt.[/dim yellow]"
            )
        active_system_prompt = skill_content or BASE_PROMPT_CHAT

    pending_query = " ".join(args[1:]) if len(args) > 1 else None
    if pending_query and (
        "CODEBASE INDEX MAP" in pending_query or "index-map" in pending_query
    ):
        if use_map:
            active_system_prompt += f"\n\n### CODESPACE MAP:\n{pending_query}"
        pending_query = None

    chat_history = [{"role": "system", "content": active_system_prompt}]
    if is_agent and not pending_query:
        chat_history.append(
            {"role": "assistant", "content": "Agent: Workspace loaded. Awaiting instructions."}
        )

    st = core.get_state()
    show_stats = st.get("show_stats", True)
    memory_active = st.get("memory_active", False)
    reasoning_active, reasoning_budget = st.get(
        "reasoning_active", False
    ), st.get("reasoning_budget", 500)

    os.environ["AI_REASONIX_ACTIVE"] = (
        "1" if st.get("reasonix_active", True) else "0"
    )
    os.environ["AI_SHOW_THINKING"] = "1" if st.get("show_thinking", True) else "0"
    if is_yolo or st.get("yolo_mode", False):
        os.environ["AI_CONFIRM_GATES"] = "0"

    if is_agent and memory_active:
        sync_md_to_sqlite(safe_name, workspace_path)

    db_turns, tpm_count = (
        workspace_db_counts(safe_name) if is_agent else (0, 0)
    )
    sub_id = None
    if is_agent:
        try:
            sub_id = sessions.get_sub_agent_id(safe_name, os.getpid())
        except Exception:
            pass

    ui.draw_session_box(
        workspace_path,
        home_dir,
        is_agent,
        db_turns,
        tpm_count,
        memory_active,
        active_system_prompt,
        clean_name,
        sub_id=sub_id,
        box_style=st.get("box_style", 2),
    )

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
                q_lower = query.lower()
                if q_lower in ("exit", "quit", "q"):
                    clean_exit(safe_name if is_agent else None)

                parts = query.split()
                if parts and parts[0] in ("/v", "/voice"):
                    is_auto_cmd = len(parts) > 1 and parts[1].lower() == "auto"
                    active, auto_mode = voice.toggle_voice_bridge(
                        auto_toggle=is_auto_cmd
                    )
                    mode_str = "auto-submit" if auto_mode else "manual edit"
                    ui._console.print(
                        f"[cyan][sys] Voice to text {'active (' + mode_str + ' mode, port 9999)' if active else 'disabled'}.[/cyan]\n"
                    )
                    continue

                if parts and parts[0] in ("/tts", "/talk", "/tol"):
                    active = tts.toggle_tts()
                    ui._console.print(
                        f"[cyan][sys] Text to speech {'enabled' if active else 'disabled'}.[/cyan]\n"
                    )
                    continue

                if parts and parts[0] in ("/py", "/ipython"):
                    if len(parts) > 1:
                        cmd_payload = query.split(maxsplit=1)[1]
                        if not ipython.is_ipython_enabled():
                            ipython.toggle_ipython_mode(True)
                            ui._console.print(
                                "[cyan][sys] IPython harness enabled (exec_python single tool mode).[/cyan]\n"
                            )
                            if "py-" not in clean_name:
                                ui._console.print(
                                    f"[yellow][sys] Warning: Active profile ('{clean_name}') is a classic JSON skill. For best in-kernel SDK results, use a Py profile (e.g. pi/py-pro).[/yellow]\n"
                                )
                        query = cmd_payload
                    else:
                        active = ipython.toggle_ipython_mode()
                        ui._console.print(
                            f"[cyan][sys] IPython harness {'enabled (exec_python single tool mode)' if active else 'disabled (classic JSON tools)'}.[/cyan]\n"
                        )
                        if active and "py-" not in clean_name:
                            ui._console.print(
                                f"[yellow][sys] Warning: Active profile ('{clean_name}') is a classic JSON skill. For best in-kernel SDK results, use a Py profile (e.g. pi/py-pro).[/yellow]\n"
                            )
                        continue

                parts = query.split()
                if parts and parts[0] in ("/task", "/loop", "/ralph"):
                    task_text = query.split(maxsplit=1)[1] if len(parts) > 1 else ""
                    ralph_env = {
                        **os.environ,
                        "AI_WORKSPACE_PATH": workspace_path,
                    }
                    subprocess.run(
                        [sys.executable, f"{CFG_DIR}/tools/loop/ralph.py", task_text],
                        cwd=workspace_path,
                        env=ralph_env,
                    )
                    continue

                if query.lower() in ("/help", "/h"):
                    ui.show_help()
                    continue

                if query == "/tui":
                    ui._console.print(
                        "[dim yellow][sys] Suspending chat. Launching TUI...[/dim yellow]"
                    )
                    time.sleep(0.5)
                    try:
                        active_skill_env = os.environ.get(
                            "AI_ACTIVE_SKILL", clean_name or "chat"
                        )
                        tui_env = {
                            **os.environ,
                            "AI_IS_AGENT": "1" if is_agent else "0",
                            "AI_WORKSPACE_PATH": workspace_path,
                            "AI_ACTIVE_SKILL": active_skill_env,
                            "AI_SESSION_HISTORY": json.dumps(chat_history),
                        }
                        subprocess.run(
                            [sys.executable, f"{CFG_DIR}/modules/agent_tui.py"],
                            env=tui_env,
                        )
                        st = core.get_state()
                        reasoning_active, reasoning_budget = st.get(
                            "reasoning_active", False
                        ), st.get("reasoning_budget", 500)
                        os.environ["AI_SHOW_THINKING"] = (
                            "1" if st.get("show_thinking", True) else "0"
                        )
                        ui._console.print(
                            "[green][sys] Resumed CLI session.[/green]\n"
                        )
                    except Exception as e:
                        ui._console.print(f"[red][sys] Failed TUI: {e}[/red]\n")
                    continue

                if query.startswith(("/webui", "/web")):
                    ui._console.print(
                        "[dim yellow][sys] Suspending CLI. Launching Py-Agent WebUI...[/dim yellow]"
                    )
                    web_bin = os.path.join(CFG_DIR, "plugins", "webui", "launch.sh")
                    if os.path.exists(web_bin):
                        try:
                            active_skill_env = os.environ.get(
                                "AI_ACTIVE_SKILL", clean_name or "chat"
                            )
                            web_env = {
                                **os.environ,
                                "AI_IS_AGENT": "1" if is_agent else "0",
                                "AI_WORKSPACE_PATH": workspace_path,
                                "AI_ACTIVE_SKILL": active_skill_env,
                                "AI_CONFIRM_GATES": "0",
                                "AI_SESSION_HISTORY": json.dumps(chat_history),
                            }
                            subprocess.run(["/bin/bash", web_bin], env=web_env)
                            st = core.get_state()
                            reasoning_active, reasoning_budget = st.get(
                                "reasoning_active", False
                            ), st.get("reasoning_budget", 500)
                            os.environ["AI_SHOW_THINKING"] = (
                                "1" if st.get("show_thinking", True) else "0"
                            )
                            ui._console.print(
                                "[green][sys] Resumed CLI session from WebUI.[/green]\n"
                            )
                        except Exception as e:
                            ui._console.print(f"[red][sys] Failed WebUI: {e}[/red]\n")
                    else:
                        ui._console.print(
                            f"[red][sys] Launcher script not found: {web_bin}[/red]\n"
                        )
                    continue

                if query.startswith(("/pycode", "/pyc")):
                    parts = query.split()
                    is_web = len(parts) > 1 and parts[1].lower() in (
                        "web",
                        "--web",
                        "browser",
                    )
                    mode_label = "Browser WebUI" if is_web else "Desktop App"
                    ui._console.print(
                        f"[dim yellow][sys] Suspending CLI. Launching PyCode {mode_label}...[/dim yellow]"
                    )
                    gui_bin = os.path.join(CFG_DIR, "plugins", "pycode", "launch.sh")
                    if os.path.exists(gui_bin):
                        try:
                            active_skill_env = os.environ.get(
                                "AI_ACTIVE_SKILL", clean_name or "chat"
                            )
                            gui_env = {
                                **os.environ,
                                "AI_IS_AGENT": "1" if is_agent else "0",
                                "AI_WORKSPACE_PATH": workspace_path,
                                "AI_ACTIVE_SKILL": active_skill_env,
                            }
                            args = (
                                ["/bin/bash", gui_bin, "web"]
                                if is_web
                                else ["/bin/bash", gui_bin]
                            )
                            subprocess.run(args, env=gui_env)
                            st = core.get_state()
                            reasoning_active, reasoning_budget = st.get(
                                "reasoning_active", False
                            ), st.get("reasoning_budget", 500)
                            os.environ["AI_SHOW_THINKING"] = (
                                "1" if st.get("show_thinking", True) else "0"
                            )
                            ui._console.print(
                                "[green][sys] Resumed CLI session from PyCode.[/green]\n"
                            )
                        except Exception as e:
                            ui._console.print(f"[red][sys] Failed PyCode: {e}[/red]\n")
                    else:
                        ui._console.print(
                            f"[red][sys] Launcher script not found: {gui_bin}[/red]\n"
                        )
                    continue

                parts = query.split()
                if parts and parts[0] in ("/box", "/box-style", "/boxstyle"):
                    val = (
                        int(parts[1])
                        if len(parts) > 1
                        and parts[1].isdigit()
                        and 1 <= int(parts[1]) <= 5
                        else (st.get("box_style", 2) % 5) + 1
                    )
                    core.save_state("box_style", val)
                    ui._console.print(
                        f"[green][sys] Switched box style to #{val}.[/green]\n"
                    )
                    continue

                if query == "/m":
                    memory_active = not memory_active
                    core.save_state("memory_active", memory_active)
                    if is_agent and memory_active:
                        sync_md_to_sqlite(safe_name, workspace_path)
                    ui._console.print(
                        f"[green][sys] Memory & TPM facts {'enabled' if memory_active else 'disabled'}.[/green]\n"
                    )
                    continue

                if query in ("/g", "/yolo"):
                    new_yolo = os.environ.get("AI_CONFIRM_GATES", "1") == "1"
                    os.environ["AI_CONFIRM_GATES"] = "0" if new_yolo else "1"
                    core.save_state("yolo_mode", new_yolo)
                    ui._console.print(
                        f"[yellow][sys] Confirmation gates {'disabled (Autonomous / YOLO mode active)' if new_yolo else 'enabled (y/n confirmation required per action)'}.[/yellow]\n"
                    )
                    continue

                parts = query.split()
                if parts and parts[0] in ("/t", "/thinking"):
                    if len(parts) > 1:
                        sub = parts[1].lower()
                        if sub in ("hide", "off", "mute", "quiet"):
                            os.environ["AI_SHOW_THINKING"] = "0"
                            core.save_state("show_thinking", False)
                            ui._console.print(
                                "[yellow][sys] Thinking display hidden (thinking mode remains active).[/yellow]\n"
                            )
                        elif sub in ("show", "on", "visible"):
                            os.environ["AI_SHOW_THINKING"] = "1"
                            core.save_state("show_thinking", True)
                            ui._console.print(
                                "[yellow][sys] Thinking display enabled.[/yellow]\n"
                            )
                        elif sub in ("toggle", "t"):
                            new_val = not (
                                os.environ.get("AI_SHOW_THINKING", "1") == "1"
                            )
                            os.environ["AI_SHOW_THINKING"] = (
                                "1" if new_val else "0"
                            )
                            core.save_state("show_thinking", new_val)
                            ui._console.print(
                                f"[yellow][sys] Thinking display {'enabled' if new_val else 'hidden'}.[/yellow]\n"
                            )
                        elif parts[1].isdigit():
                            reasoning_budget = max(0, int(parts[1]))
                            reasoning_active = reasoning_budget > 0
                            core.save_state("reasoning_active", reasoning_active)
                            core.save_state("reasoning_budget", reasoning_budget)
                            ui._console.print(
                                f"[yellow][sys] Deep reasoning {'enabled' if reasoning_active else 'disabled'} (budget: {reasoning_budget} tokens).[/yellow]\n"
                            )
                    else:
                        reasoning_active = not reasoning_active
                        core.save_state("reasoning_active", reasoning_active)
                        ui._console.print(
                            f"[yellow][sys] Deep reasoning {'enabled' if reasoning_active else 'disabled'} (budget: {reasoning_budget} tokens).[/yellow]\n"
                        )
                    continue

                if query == "/stats":
                    show_stats = not show_stats
                    core.save_state("show_stats", show_stats)
                    ui._console.print(
                        f"[green][sys] Stats {'enabled' if show_stats else 'disabled'}.[/green]\n"
                    )
                    continue

                if query in ("/sync", "/re"):
                    sys.stdout.write(
                        "\033[2m[sys] Syncing codespace map...\033[0m\r"
                    )
                    sys.stdout.flush()
                    subprocess.run(
                        [
                            sys.executable,
                            f"{CFG_DIR}/tools/index-map/index-map",
                            "--agent",
                            workspace_path,
                        ]
                    )
                    agent_dir = os.path.join(workspace_path, ".agent")
                    txt_path = next(
                        (
                            p
                            for p in (
                                os.path.join(
                                    agent_dir,
                                    f"index-map-{os.path.basename(workspace_path)}.txt",
                                ),
                                os.path.join(
                                    workspace_path,
                                    f"index-map-{os.path.basename(workspace_path)}.txt",
                                ),
                            )
                            if os.path.exists(p)
                        ),
                        None,
                    )
                    if txt_path:
                        try:
                            with open(txt_path, "r", encoding="utf-8") as mf:
                                new_map = mf.read().strip()
                            updated = False
                            for msg in chat_history:
                                if "### CODESPACE MAP:" in msg["content"]:
                                    msg["content"] = (
                                        msg["content"].split(
                                            "### CODESPACE MAP:"
                                        )[0]
                                        + f"### CODESPACE MAP:\n{new_map}"
                                    )
                                    updated = True
                            if not updated:
                                chat_history[0][
                                    "content"
                                ] += f"\n\n### CODESPACE MAP:\n{new_map}"
                            ui._console.print(
                                "\r\x1b[2K[green][sys] Map synchronized.[/green]\n"
                            )
                        except Exception as e:
                            ui._console.print(
                                f"\r\x1b[2K[red][sys] Sync failed: {e}[/red]\n"
                            )
                    continue

                if q_lower in ("/clear", "/c"):
                    chat_history = [
                        {"role": "system", "content": active_system_prompt},
                        {
                            "role": "assistant",
                            "content": "Agent: Workspace loaded. Awaiting instructions.",
                        },
                    ]
                    ui._console.print(
                        "[green][sys] Active chat history cleared.[/green]\n"
                    )
                    continue

                if q_lower in ("/reset", "/purge"):
                    chat_history = [
                        {"role": "system", "content": active_system_prompt},
                        {
                            "role": "assistant",
                            "content": "Agent: Workspace loaded. Awaiting instructions.",
                        },
                    ]
                    agent_dir = os.path.join(workspace_path, ".agent")
                    db_path = os.path.join(SESSIONS_DIR, f"{safe_name}.db")

                    if os.path.exists(agent_dir):
                        try:
                            shutil.rmtree(agent_dir)
                        except OSError:
                            pass

                    if os.path.exists(db_path):
                        try:
                            os.remove(db_path)
                        except OSError:
                            pass

                    sessions.clear_turns(safe_name)
                    memories.tpm_clear(safe_name)

                    ui._console.print(
                        "[yellow][sys] Workspace reset complete. Launching 'ai init' next time will prompt for a new profile.[/yellow]\n"
                    )
                    continue

                if query == "/tok":
                    core.show_memory_status(
                        chat_history,
                        max_context=int(os.environ.get("AI_MAX_TOKENS", 8192)),
                        server_url="http://localhost:8080",
                    )
                    continue

            if query.startswith(("/", "-")) and query.split()[0] in (
                "/skill",
                "/s",
            ):
                parts = query.split(maxsplit=1)
                sub_cmd = parts[1].strip().lower() if len(parts) > 1 else ""
                if sub_cmd in ("off", "clear", "reset", "none", "remove"):
                    chat_history[0]["content"] = active_system_prompt
                    os.environ["AI_ACTIVE_SKILL"] = clean_name or "chat"
                    ui._console.print(
                        f"[green][sys] On-demand skill removed. Reverted to base skill: [bold]{clean_name or 'chat'}[/bold].[/green]\n"
                    )
                    continue

                chat_history, loaded_name = skills.run_skill_selector(
                    safe_name, query, SKILLS_DIR, STOP_WORDS, chat_history
                )
                if loaded_name:
                    os.environ["AI_ACTIVE_SKILL"] = f"{clean_name} {loaded_name}"
                continue

            if query.startswith("-save"):
                tag = query.replace("-save", "").strip() or "checkpoint"
                sessions.save_checkpoint(safe_name, tag, chat_history)
                continue

            if query in ("-load", "-timeline"):
                try:
                    if restored_hist := sessions.rollback_checkpoint(safe_name):
                        chat_history = restored_hist
                        ui._console.print(
                            f"[green][session-mgr] Restored session ({len(chat_history) - 1} turns loaded).[/green]\n"
                        )
                except Exception as e:
                    ui._console.print(f"[red]Error loading session: {e}[/red]")
                continue

            past_memory, tpm_context = "", ""
            is_first_turn = len(chat_history) <= 2
            if is_agent and memory_active:
                if not is_first_turn and len(query) > 5:
                    try:
                        res_mem = memories.search_past_context(safe_name, query)
                        if res_mem == "__CANCELLED__":
                            pending_query = None
                            continue
                        if res_mem == "__DISABLE_MEMORY__":
                            memory_active = False
                            core.save_state("memory_active", False)
                        elif res_mem:
                            past_memory = res_mem
                    except Exception:
                        pass
                tpm_context = memories.tpm_get(safe_name)

            if re.match(r"^/?([ftba])(?:\s+(\d+))?$", query.lower()):
                think_bin = f"{CFG_DIR}/modules/chat"
                if os.path.exists(think_bin):
                    try:
                        subprocess.run(
                            [sys.executable, think_bin, query],
                            input=json.dumps(chat_history),
                            text=True,
                        )
                        continue
                    except Exception as e:
                        sys.stderr.write(
                            f"\033[1;31m[Warning] chat failed: {e}\033[0m\n"
                        )
                continue

            sys_ctx = (
                ""
                if query.startswith("init") and "--init" in query
                else skills.get_system_context(
                    query, CONTEXT_FILE, STOP_WORDS, SKILLS_DIR, CFG_DIR
                )
            )
            if sys_ctx == "__ABORT_TURN__":
                sys_ctx = ""
            comb_ctx = "\n\n".join(
                filter(None, [tpm_context, past_memory, sys_ctx])
            )
            prompt = (
                f"<context>\n{comb_ctx}\n</context>\n\nUser Question: {query}"
                if comb_ctx
                else f"User Question: {query}"
            )

            chat_history.append({"role": "user", "content": prompt})
            try:
                readline.add_history(query)
            except Exception:
                pass

            if ans := core.stream_response(
                chat_history,
                prefix="Agent:" if is_agent else "AI:",
                show_stats=show_stats,
                thinking_budget=reasoning_budget if reasoning_active else 0,
                is_agent=is_agent,
            ):
                chat_history.append({"role": "assistant", "content": ans})
                tts.speak_response(ans)
                if is_agent:
                    sessions.log_turn(safe_name, query, ans)

                    if match := re.search(
                        r"Run:\s*((?:trace symbol|blast radius|read function|find symbol)\s+\S+|architecture overview)",
                        ans,
                    ):
                        try:
                            readline.set_startup_hook(
                                lambda: readline.insert_text(
                                    match.group(1).strip()
                                )
                            )
                        except Exception:
                            pass

                    if memory_active:
                        threading.Thread(
                            target=core.background_tpm_update,
                            args=(query, ans, safe_name, workspace_path),
                            daemon=True,
                        ).start()

                    agent_dir = os.path.join(workspace_path, ".agent")
                    os.makedirs(agent_dir, exist_ok=True)
                    hist_file = os.path.join(agent_dir, "history.md")
                    try:
                        mode = "a" if os.path.exists(hist_file) else "w"
                        with open(hist_file, mode, encoding="utf-8") as hf:
                            if mode == "w":
                                hf.write(
                                    f"# Workspace History: {os.path.basename(workspace_path)}\n\n"
                                )
                            hf.write(
                                f"## [{time.strftime('%Y-%m-%d %H:%M')}] User:\n{query}\n\n### Agent:\n{ans}\n\n---\n\n"
                            )
                    except OSError:
                        pass
    except KeyboardInterrupt:
        clean_exit(safe_name if is_agent else None)


def run_direct_query(args: list[str]) -> None:
    query_parts = args[1:]
    query = " ".join(query_parts).strip()

    if query.lower() in ("/help", "/h", "help", "--help", "-h"):
        ui.show_help()
        sys.exit(0)

    skill_content = ""
    if query_parts and query_parts[-1].startswith("-"):
        skill_content = skills.load_skill_content(
            query_parts[-1].lstrip("-").lower(), SKILLS_DIR, CFG_DIR
        )
        query_parts = query_parts[:-1]
        query = " ".join(query_parts).strip()

    sys_ctx = skills.get_system_context(
        query, CONTEXT_FILE, STOP_WORDS, SKILLS_DIR, CFG_DIR
    )
    if sys_ctx == "__ABORT_TURN__":
        sys_ctx = ""

    active_p = skill_content or BASE_PROMPT_CHAT
    messages = [
        {"role": "system", "content": active_p},
        {
            "role": "user",
            "content": (
                f"<context>\n{sys_ctx}\n</context>\n\nUser Question: {query}"
                if sys_ctx
                else f"User Question: {query}"
            ),
        },
    ]
    core.stream_response(
        messages, prefix="AI:", show_stats=False, thinking_budget=0
    )
    sys.exit(0)


def run_matching_search(args: list[str]) -> None:
    user_input = re.sub(r"[`$]", "", " ".join(args)).strip()
    if not user_input or args[0].startswith("--"):
        sys.exit(0)
    if user_input.lower() in ("/help", "/h"):
        ui.show_help()
        sys.exit(0)

    shell_name = os.path.basename(os.environ.get("SHELL", "/bin/bash"))
    err_msg = f"{'zsh' if 'zsh' in shell_name else 'bash'}: {f'command not found: {user_input}' if 'zsh' in shell_name else f'{user_input}: command not found'}\n"
    if re.search(r"[\[\]{}()='\",;|#<>]", user_input):
        sys.stderr.write(err_msg)
        sys.exit(127)

    if matched := context.jaccard_search(user_input, CONTEXT_FILE, STOP_WORDS):
        print(
            "\n".join(
                f"{l.split('|||', 1)[0]}|||{context.clean_tool_prefix(l.split('|||', 1)[1])}"
                for l in matched.split("\n")
            )
        )
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
                lambda n: sys.stderr.write(
                    f"zsh: command not found: {n}\n"
                    if "zsh" in shell_name
                    else f"bash: {n}: command not found\n"
                ),
                lambda: skills.ensure_mysys_exists(SKILLS_DIR, CFG_DIR),
            )
            sys.exit(0)
        elif args[0] in ("--talk", "--talk-chat"):
            (
                run_interactive_chat(args)
                if (args[0] == "--talk-chat" or len(args) == 1)
                else run_direct_query(args)
            )
            sys.exit(0)
        else:
            run_matching_search(args)
    except KeyboardInterrupt:
        sys.stderr.write("\nCancelled.\n")
        sys.exit(130)


if __name__ == "__main__":
    main()
