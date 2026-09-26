#!/usr/bin/env python3
"""Modular Command Dispatcher & Slash Action Registry for Py-Agent [Production Ready]"""

import json
import os
import re
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

CFG_DIR = os.path.expanduser("~/.config/py-agent")
SKILLS_DIR = os.path.join(CFG_DIR, "skills")
SESSIONS_DIR = os.path.join(CFG_DIR, "projects", ".database")

try:
    import agent_core as core
    import agent_ipython as ipython
    import agent_memories as memories
    import agent_sessions as sessions
    import agent_skills as skills
    import agent_tts as tts
    import agent_ui as ui
    import agent_voice as voice
    from agent_context import STOP_WORDS
except ImportError as e:
    sys.stderr.write(f"\033[1;31m[CRITICAL]: Failed to load modules in commands: {e}\033[0m\n")


@dataclass
class SessionContext:
    workspace_path: str
    home_dir: str
    safe_name: str
    cfg_file: str
    is_agent: bool
    chat_history: list[dict[str, Any]]
    active_system_prompt: str
    clean_name: str
    use_map: bool
    memory_active: bool
    is_yolo: bool
    reasoning_active: bool
    reasoning_budget: int
    show_stats: bool
    flash_status: Callable[[str], None]
    launch_surface_fn: Callable[..., None]
    clean_exit_fn: Callable[..., None]


def update_workspace_config(cfg_file: str, updates: dict[str, Any]) -> None:
    """Atomically updates settings inside .agent/config.json with cleanup on error."""
    if not os.path.exists(cfg_file):
        return
    tmp = f"{cfg_file}.tmp"
    try:
        data = {}
        with open(cfg_file, "r", encoding="utf-8") as cf:
            data = json.load(cf)
        data.update(updates)
        with open(tmp, "w", encoding="utf-8") as cf:
            json.dump(data, cf, indent=2)
        os.replace(tmp, cfg_file)
    except (OSError, json.JSONDecodeError):
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
        ui._console.print("[dim yellow][sys] Failed to persist workspace config.[/dim yellow]")


def handle_map_toggle(ctx: SessionContext, parts: list[str]) -> bool:
    ctx.use_map = not ctx.use_map
    core.save_state("use_map", ctx.use_map)
    os.environ["AI_USE_MAP"] = "1" if ctx.use_map else "0"
    update_workspace_config(ctx.cfg_file, {"map": ctx.use_map})

    if ctx.use_map:
        agent_dir = os.path.join(ctx.workspace_path, ".agent")
        ws_name = os.path.basename(ctx.workspace_path)
        txt_p = next((p for p in (os.path.join(agent_dir, f"index-map-{ws_name}.txt"), os.path.join(ctx.workspace_path, f"index-map-{ws_name}.txt")) if os.path.exists(p)), None)
        if txt_p:
            try:
                with open(txt_p, "r", encoding="utf-8") as mf:
                    new_map = mf.read().strip()
                has_map = False
                for msg in ctx.chat_history:
                    if "### CODESPACE MAP:" in msg["content"]:
                        msg["content"] = msg["content"].split("### CODESPACE MAP:")[0] + f"### CODESPACE MAP:\n{new_map}"
                        has_map = True
                if not has_map:
                    ctx.chat_history[0]["content"] += f"\n\n### CODESPACE MAP:\n{new_map}"
            except Exception:
                pass
    else:
        for msg in ctx.chat_history:
            if "### CODESPACE MAP:" in msg["content"]:
                msg["content"] = msg["content"].split("### CODESPACE MAP:")[0].strip()

    ctx.flash_status(f"map: {'on' if ctx.use_map else 'off'}")
    return True


def handle_memory_cmd(ctx: SessionContext, query: str, parts: list[str]) -> bool:
    sub_parts = query.split(maxsplit=2)
    sub_action = sub_parts[1].lower() if len(sub_parts) > 1 else ""

    if not ctx.is_agent and sub_action not in ("list", "ls", "show"):
        ui._console.print("[dim yellow][sys] Project memory is only available in agent mode.[/dim yellow]\n")
        return True

    if sub_action in ("save", "add", "set", "new"):
        if len(sub_parts) < 3:
            ui._console.print("[dim yellow][sys] Usage: /mem save <title>[: <content>]  (e.g. /mem save db: Use SQLite WAL mode)[/dim yellow]\n")
            return True
        raw_payload = sub_parts[2]
        m_title, m_content = raw_payload.split(":", 1) if ":" in raw_payload else (raw_payload.split("|", 1) if "|" in raw_payload else (raw_payload, raw_payload))
        ok, res_path = memories.save_memory_file(ctx.workspace_path, m_title.strip(), m_content.strip())
        if ok:
            ui._console.print(f"[green][sys] Saved memory: [bold]{os.path.basename(res_path)}[/bold][/green]\n")
        else:
            ui._console.print(f"[red][sys] {res_path}[/red]\n")
        return True

    if sub_action in ("list", "ls", "show"):
        items = memories.list_memories(ctx.workspace_path)
        if not items:
            ui._console.print("[dim yellow][sys] No memory files found in .agent/memory/[/dim yellow]\n")
        else:
            ui._console.print(f"[cyan]### Active Memory Files ({len(items)}):[/cyan]")
            for it in items:
                ui._console.print(f"  • [bold green]{it['filename']}[/bold green] [{it['type']}]: {it['title']} [dim]({it['content'][:60]}...)[/dim]")
            ui._console.print()
        return True

    ctx.memory_active = not ctx.memory_active
    core.save_state("memory_active", ctx.memory_active)
    update_workspace_config(ctx.cfg_file, {"memory": ctx.memory_active})
    ctx.flash_status(f"mem: {'on' if ctx.memory_active else 'off'}")
    return True


def handle_grounding_cmd(ctx: SessionContext, parts: list[str]) -> bool:
    if len(parts) > 1:
        sub = parts[1].lower()
        if sub in ("off", "disable", "false", "0"):
            core.save_state("grounding_active", False)
            gnd_active, g_bud = False, 0
        elif sub in ("on", "enable", "true"):
            core.save_state("grounding_active", True)
            g_bud = core.get_state("grounding_budget", 700)
            gnd_active = True
        elif sub.isdigit():
            g_bud = max(0, int(sub))
            gnd_active = g_bud > 0
            core.save_state("grounding_active", gnd_active)
            core.save_state("grounding_budget", g_bud)
        else:
            gnd_active = not core.get_state("grounding_active", False)
            g_bud = core.get_state("grounding_budget", 700)
            core.save_state("grounding_active", gnd_active)
    else:
        gnd_active = not core.get_state("grounding_active", False)
        g_bud = core.get_state("grounding_budget", 700)
        core.save_state("grounding_active", gnd_active)

    ctx.flash_status(f"gnd: {g_bud if gnd_active else 'off'}")
    return True


def handle_tts_cmd(ctx: SessionContext, parts: list[str]) -> bool:
    if len(parts) > 1:
        raw_arg = parts[1].lower()
        arg = re.sub(r"(?<=\d)x$", "", raw_arg)
        if arg in ("def", "default", "reset"):
            sp = tts.set_tts_speed(1.15)
            ctx.flash_status(f"tts: reset {sp}x")
        else:
            try:
                val = float(arg)
                sp = tts.set_tts_speed(val)
                if not tts.is_tts_enabled():
                    tts.toggle_tts(True)
                ctx.flash_status(f"tts: {sp}x")
            except ValueError:
                ui._console.print("[dim yellow][sys] Usage: /tts <speed> (e.g. /tts 1.4) or /tts reset[/dim yellow]\n")
    else:
        active = tts.toggle_tts()
        cur_speed = tts.get_tts_speed() if hasattr(tts, "get_tts_speed") else 1.15
        ctx.flash_status(f"tts: {cur_speed if active else 'off'}")
    return True


def handle_file_command(ctx: SessionContext, query: str, parts: list[str]) -> bool:
    if len(parts) < 2:
        ui._console.print("[dim yellow][sys] Usage: file <path> (e.g. file src/main.py)[/dim yellow]\n")
        return True

    raw_f = query.split(maxsplit=1)[1].strip().strip('\'"')
    ws_real = os.path.realpath(ctx.workspace_path)
    cand_p = os.path.expanduser(raw_f) if os.path.isabs(os.path.expanduser(raw_f)) else os.path.join(ctx.workspace_path, raw_f)
    full_p = os.path.realpath(cand_p)

    # 1. Strict boundary containment: must remain within the active workspace root
    if not (full_p == ws_real or full_p.startswith(ws_real + os.sep)):
        ui._console.print(f"[red][sys] Access denied: '{raw_f}' is outside the workspace.[/red]\n")
        return True

    if not os.path.isfile(full_p):
        ui._console.print(f"[red][sys] File not found: {raw_f}[/red]\n")
        return True

    # 2. Comprehensive credential and secrets pattern protection
    base_f = os.path.basename(full_p).lower()
    sens_ext = (".pem", ".key", ".p12", ".pfx", ".kdbx", "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519")
    if (
        base_f.startswith(".env")
        or base_f in (".git-credentials", ".netrc", ".npmrc", ".pypirc", ".last_cloud_key.txt")
        or any(full_p.endswith(ext) for ext in sens_ext)
        or re.search(r"(secret|credential|token|password|apikey|api_key)", base_f)
    ):
        ui._console.print(f"[red][sys] Access denied: Sensitive credential file '{base_f}'.[/red]\n")
        return True

    # 3. Binary file protection
    if any(full_p.endswith(ext) for ext in (".db", ".sqlite", ".bin", ".png", ".jpg", ".jpeg", ".zip", ".tar", ".gz", ".pyc", ".so", ".dylib")):
        ui._console.print(f"[red][sys] Cannot load binary file: {raw_f}[/red]\n")
        return True

    # 4. Size protection cap (max 250 KB to prevent context blowup)
    try:
        f_size = os.path.getsize(full_p)
        if f_size > 250 * 1024:
            ui._console.print(f"[red][sys] File too large ({f_size // 1024} KB > 250 KB limit). Use read_file slices.[/red]\n")
            return True
        with open(full_p, "r", encoding="utf-8", errors="replace") as f:
            f_content = f.read()
        rel_name = os.path.relpath(full_p, ctx.workspace_path)
        lines_cnt = len(f_content.splitlines())
        file_entry = f"### File Context: {rel_name} ({lines_cnt} lines)\n```\n{f_content}\n```"
        ctx.chat_history.append({"role": "user", "content": f"[System Context]: User manually loaded file '{rel_name}' into context.\n\n{file_entry}"})
        ctx.chat_history.append({"role": "assistant", "content": f"Loaded '{rel_name}' ({lines_cnt} lines) into active context."})
        ctx.flash_status(f"file: {rel_name} ({lines_cnt} lines)")
    except OSError as e:
        ui._console.print(f"[red][sys] Failed to read file: {e}[/red]\n")

    return True


def handle_hindsight_cmd(ctx: SessionContext) -> bool:
    user_turns = [m for m in ctx.chat_history if m.get("role") == "user" and not m.get("content", "").startswith("[System Directive - Hindsight")]
    if not user_turns:
        ui._console.print("[dim yellow][sys] No conversation turns to audit yet.[/dim yellow]\n")
        return True

    ui._console.print("[cyan][sys] Running Hindsight retrospective audit...[/cyan]\n")
    hs_skill = skills.load_skill_content("hindsight", SKILLS_DIR, CFG_DIR)
    audit_prompt = (
        "[System Directive - Hindsight Retrospective]: Review the conversation history above. "
        "Identify any durable technical rules, tool quirks, command fixes, or project decisions settled in this session. "
        "For each durable lesson, call save_memory(title='<short-slug>', content='<actionable rule>') immediately. "
        "If no new durable lessons occurred, reply with: '✓ Hindsight: No durable lessons required; session was nominal.'"
    )
    temp_history = list(ctx.chat_history)
    if hs_skill:
        temp_history[0] = {"role": "system", "content": temp_history[0]["content"] + "\n\n" + hs_skill}
    temp_history.append({"role": "user", "content": audit_prompt})

    ans = core.stream_response(temp_history, prefix="Agent:", show_stats=ctx.show_stats, thinking_budget=ctx.reasoning_budget if ctx.reasoning_active else 0, is_agent=ctx.is_agent)
    if ans:
        clean_ans = re.sub(r"<think>[\s\S]*?</think>", "", ans).strip()
        ctx.chat_history.append({"role": "assistant", "content": clean_ans or ans})
        m_cnt = memories.get_memory_count(ctx.workspace_path)
        ui._console.print(f"\n[green][sys] Hindsight complete. Active memories: {m_cnt} files.[/green]\n")
    return True


def dispatch_command(query: str, ctx: SessionContext) -> tuple[bool, str | None]:
    """
    Evaluates input queries against interactive slash commands, tools, and shortcuts.
    Returns:
        (True, None): Command handled internally; caller should skip turn execution.
        (False, None): Not a command; caller should proceed with normal turn execution.
        (False, new_query): Rewritten query (e.g. inline /py code); proceed with new_query.
    """
    q_strip = query.strip()
    q_lower = q_strip.lower()

    if not q_strip:
        return True, None

    # Global Stop Voice/Speech Commands
    if q_lower.rstrip(".") in ("stop speech", "stop talking", "kill tts"):
        try:
            tts.stop_tts()
        except Exception:
            pass
        subprocess.run("killall -9 pw-play koko 2>/dev/null || true", shell=True)
        return True, None

    # Global Session Exit
    if q_lower in ("exit", "quit", "q"):
        ctx.clean_exit_fn(ctx.safe_name if ctx.is_agent else None)
        return True, None

    # Match Interactive Commands
    parts = q_strip.split()
    cmd = parts[0].lower() if parts else ""

    if cmd in ("/m", "/map", "/graph"):
        return handle_map_toggle(ctx, parts), None

    if cmd in ("/mem", "/memory"):
        return handle_memory_cmd(ctx, q_strip, parts), None

    if cmd in ("/gnd", "/ground"):
        return handle_grounding_cmd(ctx, parts), None

    if cmd in ("/v", "/voice"):
        is_auto = len(parts) > 1 and parts[1].lower() == "auto"
        active, auto_mode = voice.toggle_voice_bridge(auto_toggle=is_auto)
        ctx.flash_status(f"voice: {'auto' if auto_mode else ('on' if active else 'off')}")
        return True, None

    if cmd in ("/tts", "/talk", "/tol"):
        return handle_tts_cmd(ctx, parts), None

    if cmd in ("/adp", "/adapter", "/adapters"):
        cur_adp = core.get_state("adapters_active", False)
        new_adp = not cur_adp
        core.save_state("adapters_active", new_adp)
        update_workspace_config(ctx.cfg_file, {"adapters": new_adp})
        ctx.flash_status(f"adp: {'on' if new_adp else 'off'}")
        return True, None

    if cmd in ("/py", "/ipython"):
        if len(parts) > 1:
            if not ipython.is_ipython_enabled():
                ipython.toggle_ipython_mode(True)
            os.environ["AI_IPYTHON_MODE"] = "1"
            core.save_state("ipython_mode", True)
            update_workspace_config(ctx.cfg_file, {"py": True})
            return False, q_strip.split(maxsplit=1)[1]
        else:
            active = ipython.toggle_ipython_mode()
            os.environ["AI_IPYTHON_MODE"] = "1" if active else "0"
            core.save_state("ipython_mode", active)
            update_workspace_config(ctx.cfg_file, {"py": active})
            ctx.flash_status(f"py: {'on' if active else 'off'}")
            return True, None

    if cmd in ("/task", "/loop", "/ralph"):
        task_text = q_strip.split(maxsplit=1)[1] if len(parts) > 1 else ""
        loop_script = os.path.join(CFG_DIR, "tools", "loop", "loop.py")
        if not os.path.exists(loop_script):
            loop_script = os.path.join(CFG_DIR, "tools", "loop", "ralph.py")
        subprocess.run([sys.executable, loop_script, task_text], cwd=ctx.workspace_path, env={**os.environ, "AI_WORKSPACE_PATH": ctx.workspace_path})
        return True, None

    if cmd in ("/hindsight", "/hs"):
        return handle_hindsight_cmd(ctx), None

    if cmd in ("/help", "/h"):
        ui.show_help()
        return True, None

    if cmd == "/tui":
        ui._console.print("[dim yellow][sys] Suspending chat. Launching TUI...[/dim yellow]")
        ctx.launch_surface_fn(f"{CFG_DIR}/modules/agent_tui.py", ctx.is_agent, ctx.workspace_path, ctx.clean_name or "chat", ctx.chat_history)
        return True, None

    if cmd in ("/webui", "/web"):
        ui._console.print("[dim yellow][sys] Suspending CLI. Launching Py-Agent WebUI...[/dim yellow]")
        ctx.launch_surface_fn(os.path.join(CFG_DIR, "plugins", "webui", "launch.sh"), ctx.is_agent, ctx.workspace_path, ctx.clean_name or "chat", ctx.chat_history)
        return True, None

    if cmd in ("/pycode", "/pyc"):
        is_web = len(parts) > 1 and parts[1].lower() in ("web", "--web", "browser")
        ui._console.print(f"[dim yellow][sys] Suspending CLI. Launching PyCode {'Browser WebUI' if is_web else 'Desktop App'}...[/dim yellow]")
        ctx.launch_surface_fn(os.path.join(CFG_DIR, "plugins", "pycode", "launch.sh"), ctx.is_agent, ctx.workspace_path, ctx.clean_name or "chat", ctx.chat_history, args=["web"] if is_web else [])
        return True, None

    if cmd in ("/box", "/box-style", "/boxstyle"):
        cur_box = core.get_state("box_style", 2)
        val = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() and 1 <= int(parts[1]) <= 8 else (cur_box % 8) + 1
        core.save_state("box_style", val)
        ctx.flash_status(f"box: #{val}")
        return True, None

    if cmd in ("/calm", "/zen"):
        cur_calm = core.get_state("calm_mode", False)
        new_calm = not cur_calm
        core.save_state("calm_mode", new_calm)
        update_workspace_config(ctx.cfg_file, {"calm": new_calm})
        ctx.flash_status(f"calm: {'on' if new_calm else 'off'}")
        return True, None

    if cmd == "/md":
        new_md = not (os.environ.get("AI_RENDER_MARKDOWN", "1") == "1")
        os.environ["AI_RENDER_MARKDOWN"] = "1" if new_md else "0"
        core.save_state("render_markdown", new_md)
        ctx.flash_status(f"md: {'on' if new_md else 'off'}")
        return True, None

    if cmd in ("/g", "/yolo"):
        if ctx.is_agent:
            new_yolo = not (os.environ.get("AI_CONFIRM_GATES", "1") == "0")
            os.environ["AI_CONFIRM_GATES"] = "0" if new_yolo else "1"
            core.save_state("yolo_mode", new_yolo)
            update_workspace_config(ctx.cfg_file, {"yolo": new_yolo})
            ctx.flash_status(f"yolo: {'on' if new_yolo else 'off'}")
        else:
            ctx.flash_status("yolo: disabled in chat")
        return True, None

    if cmd in ("/t", "/thinking"):
        if len(parts) > 1:
            sub = parts[1].lower()
            if sub in ("hide", "off", "mute", "quiet"):
                os.environ["AI_SHOW_THINKING"] = "0"
                core.save_state("show_thinking", False)
                ctx.flash_status("thinking: hidden")
            elif sub in ("show", "on", "visible"):
                os.environ["AI_SHOW_THINKING"] = "1"
                core.save_state("show_thinking", True)
                ctx.flash_status("thinking: visible")
            elif sub.isdigit():
                ctx.reasoning_budget = max(0, int(sub))
                ctx.reasoning_active = ctx.reasoning_budget > 0
                core.save_state("reasoning_active", ctx.reasoning_active)
                core.save_state("reasoning_budget", ctx.reasoning_budget)
                ctx.flash_status(f"thinking: {ctx.reasoning_budget if ctx.reasoning_active else 'off'}")
        else:
            ctx.reasoning_active = not ctx.reasoning_active
            core.save_state("reasoning_active", ctx.reasoning_active)
            ctx.flash_status(f"thinking: {ctx.reasoning_budget if ctx.reasoning_active else 'off'}")

        update_workspace_config(ctx.cfg_file, {"reasoning": ctx.reasoning_active, "reasoning_budget": ctx.reasoning_budget})
        return True, None

    if cmd == "/stats":
        ctx.show_stats = not ctx.show_stats
        core.save_state("show_stats", ctx.show_stats)
        ctx.flash_status(f"stats: {'on' if ctx.show_stats else 'off'}")
        return True, None

    if cmd in ("/sync", "/re"):
        sys.stdout.write("\033[2m[sys] Syncing index-map...\033[0m\r")
        sys.stdout.flush()
        imap_bin = os.path.join(CFG_DIR, "tools", "index-map", "index-map")
        if os.path.isfile(imap_bin):
            res_sync = subprocess.run([sys.executable, imap_bin, "--agent", ctx.workspace_path], capture_output=True, text=True)
            if res_sync.returncode != 0:
                ui._console.print(f"\r\x1b[2K[red][sys] Sync failed: {res_sync.stderr.strip()[:100]}[/red]\n")
                return True
        else:
            ui._console.print(f"\r\x1b[2K[red][sys] index-map tool not found: {imap_bin}[/red]\n")
            return True

        agent_dir = os.path.join(ctx.workspace_path, ".agent")
        ws_name = os.path.basename(ctx.workspace_path)
        txt_p = next((p for p in (os.path.join(agent_dir, f"index-map-{ws_name}.txt"), os.path.join(ctx.workspace_path, f"index-map-{ws_name}.txt")) if os.path.exists(p)), None)
        if txt_p:
            try:
                with open(txt_p, "r", encoding="utf-8") as mf:
                    new_map = mf.read().strip()
                has_map = False
                for msg in ctx.chat_history:
                    if "### CODESPACE MAP:" in msg["content"]:
                        msg["content"] = msg["content"].split("### CODESPACE MAP:")[0] + f"### CODESPACE MAP:\n{new_map}"
                        has_map = True
                if not has_map:
                    ctx.chat_history[0]["content"] += f"\n\n### CODESPACE MAP:\n{new_map}"
                ctx.flash_status("map: synced")
            except Exception as e:
                ui._console.print(f"\r\x1b[2K[red][sys] Sync parse failed: {e}[/red]\n")
        return True

    if q_lower in ("/clear", "/c"):
        ctx.chat_history.clear()
        ctx.chat_history.append({"role": "system", "content": ctx.active_system_prompt})
        if ctx.is_agent:
            ctx.chat_history.append({"role": "assistant", "content": "Agent: Workspace loaded. Awaiting instructions."})
        ctx.flash_status("chat: cleared")
        return True, None

    if q_lower in ("/reset", "/r"):
        ctx.chat_history.clear()
        ctx.chat_history.append({"role": "system", "content": ctx.active_system_prompt})
        if ctx.is_agent:
            ctx.chat_history.append({"role": "assistant", "content": "Agent: Workspace loaded. Awaiting instructions."})
        agent_dir, db_p = os.path.join(ctx.workspace_path, ".agent"), os.path.join(SESSIONS_DIR, f"{ctx.safe_name}.db")
        if os.path.exists(agent_dir):
            shutil.rmtree(agent_dir, ignore_errors=True)
        if os.path.exists(db_p):
            try:
                os.remove(db_p)
            except OSError:
                pass
        sessions.clear_turns(ctx.safe_name)
        memories.clear_memories(ctx.workspace_path)
        ctx.flash_status("workspace: reset")
        return True, None

    if cmd in ("/compact", "/com", "/cpt"):
        before_toks = sum(core.get_accurate_token_count(m.get("content") or "") for m in ctx.chat_history)
        ctx.chat_history[:] = core.prune_history(ctx.chat_history)
        after_toks = sum(core.get_accurate_token_count(m.get("content") or "") for m in ctx.chat_history)
        saved = max(0, before_toks - after_toks)
        pct = (saved / before_toks * 100) if before_toks > 0 else 0
        ui._console.print(f"[green][sys] Context compacted: {before_toks} → {after_toks} tokens (saved {saved}t / -{pct:.1f}%).[/green]\n")
        return True, None

    if cmd == "/tok":
        core.show_memory_status(ctx.chat_history, max_context=int(os.environ.get("AI_MAX_TOKENS", 8192)), server_url="http://localhost:8080")
        return True, None

    if cmd in ("file", "/file"):
        return handle_file_command(ctx, q_strip, parts), None

    if q_strip.startswith(("/", "-")) and q_strip.split()[0] in ("/skill", "/s"):
        parts = q_strip.split(maxsplit=1)
        sub_cmd = parts[1].strip().lower() if len(parts) > 1 else ""
        if sub_cmd in ("off", "clear", "reset", "none", "remove"):
            ctx.chat_history[0]["content"] = ctx.active_system_prompt
            os.environ["AI_ACTIVE_SKILL"] = ctx.clean_name or "chat"
            ctx.flash_status(f"skill: {ctx.clean_name or 'chat'}")
            return True, None

        ctx.chat_history[:], loaded_name = skills.run_skill_selector(ctx.safe_name, q_strip, SKILLS_DIR, STOP_WORDS, ctx.chat_history)
        if loaded_name:
            os.environ["AI_ACTIVE_SKILL"] = f"{ctx.clean_name} {loaded_name}"
        return True, None

    if q_strip.startswith("-save"):
        tag = q_strip.replace("-save", "").strip() or "checkpoint"
        sessions.save_checkpoint(ctx.safe_name, tag, ctx.chat_history)
        ctx.flash_status(f"checkpoint: {tag}")
        return True, None

    if q_strip in ("-load", "-timeline"):
        try:
            if restored_hist := sessions.rollback_checkpoint(ctx.safe_name):
                ctx.chat_history[:] = restored_hist
                ui._console.print(f"[green][session-mgr] Restored session ({len(ctx.chat_history) - 1} turns loaded).[/green]\n")
        except Exception as e:
            ui._console.print(f"[red]Error loading session: {e}[/red]")
        return True, None

    return False, None
