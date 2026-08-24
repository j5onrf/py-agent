#!/usr/bin/env python3
"""Unified library & executable for static, dynamic, universal YAML, and on-demand skills [In-Memory Edition]"""

import json
import os
import re
import shutil
import subprocess
import sys
from typing import Any, Optional

import agent_context as context
import agent_ui as ui

PAGER_STRIP_RE: re.Pattern = re.compile(r'\|\s*(leaf|mdcat|cat|glow|view)\b.*$', re.IGNORECASE)
RE_FRONTMATTER_JSON: re.Pattern = re.compile(r'^\s*(\{[\s\S]*?\})\s*')
RE_METADATA_LINE: re.Pattern = re.compile(r'^\w+:\s')
RE_SKILL_SPLIT: re.Pattern = re.compile(r"[-_/]")
RE_SKILL_BLOCK: re.Pattern = re.compile(r"### Loaded On-Demand Skill:\s*([^\n]+)\n([\s\S]*?)(?=\n\n### Loaded On-Demand Skill:|\Z)")


def ensure_mysys_exists(skills_dir: str, cfg_dir: str) -> None:
    if not os.path.exists(os.path.join(skills_dir, "system", "mysys.md")):
        try: subprocess.run([sys.executable, os.path.join(cfg_dir, "tools", "generate-profile")], check=False)
        except Exception: pass


def parse_frontmatter(raw_text: str) -> tuple[dict[str, Any], str]:
    """Universal parser for YAML (---), JSON ({}), and plain Markdown headers."""
    if not raw_text:
        return {}, ""
    raw = raw_text.strip()
    
    # 1. Standard YAML / Markdown Frontmatter (--- ... ---)
    if raw.startswith("---"):
        parts = raw.split("---", 2)
        if len(parts) >= 3:
            fm_str, body = parts[1].strip(), parts[2].strip()
            meta = {}
            cur_key = None
            cur_val_lines = []
            
            for line in fm_str.splitlines():
                l_strip = line.strip()
                if not l_strip or l_strip.startswith("#"):
                    continue
                
                if ":" in line and not line.startswith((" ", "\t", "-")):
                    if cur_key:
                        meta[cur_key] = " ".join(cur_val_lines).strip()
                    k, v = line.split(":", 1)
                    cur_key = k.strip().lower()
                    v_clean = v.strip().strip("\"'")
                    cur_val_lines = [] if v_clean in (">", "|", "") else [v_clean]
                elif cur_key:
                    cur_val_lines.append(l_strip.strip("\"'"))
                    
            if cur_key:
                meta[cur_key] = " ".join(cur_val_lines).strip()
            return meta, body

    # 2. JSON Frontmatter
    elif raw.startswith("{"):
        if m := RE_FRONTMATTER_JSON.match(raw):
            try:
                meta = json.loads(m.group(1))
                return meta, raw[m.end():].strip()
            except (json.JSONDecodeError, TypeError): pass

    return {}, raw


def find_skill_file(base_dir: str, skill_name: str) -> str | None:
    """Locates target skill across standard flat files and nested directory SKILL.md structures."""
    clean = skill_name.lstrip("-").lower()
    
    candidates = [
        os.path.join(base_dir, "profiles", f"{clean}.md"),
        os.path.join(base_dir, f"{clean}.md"),
        os.path.join(base_dir, "system", f"{clean}.md"),
        os.path.join(base_dir, clean, "SKILL.md"),
        os.path.join(base_dir, clean, "skill.md")
    ]
    for cand in candidates:
        if os.path.isfile(cand): return cand

    target_fnames = {f"{os.path.basename(clean)}.md", "skill.md", "skill.md".upper()}
    clean_target = os.path.basename(clean)

    for root, _, files in os.walk(base_dir):
        if root[len(base_dir):].count(os.sep) <= 5:
            if os.path.basename(root).lower() == clean_target:
                for f in files:
                    if f.lower() in ("skill.md", f"{clean_target}.md"):
                        return os.path.join(root, f)
            for f in files:
                if f.lower() in target_fnames:
                    return os.path.join(root, f)
    return None


def load_skill_content(skills_str: str, skills_dir: str, cfg_dir: str) -> str:
    """Concatenates the instruction contents of all matched skills, stripping frontmatter."""
    if not skills_str: return ""
    contents: list[str] = []
    for skill in [s.lstrip("-").lower() for s in skills_str.split()]:
        if sf := find_skill_file(skills_dir, skill):
            if "system" in skill: ensure_mysys_exists(skills_dir, cfg_dir)
            try:
                with open(sf, "r", encoding="utf-8") as f:
                    raw = f.read().strip()
                meta, body = parse_frontmatter(raw)
                
                if meta:
                    try:
                        import agent_core
                        for k, v in meta.items():
                            if k == "yolo": agent_core.save_state("yolo_mode", True if str(v).lower() in ("true", "1") else False)
                            elif k in ("reasoning", "reasoning_active"): agent_core.save_state("reasoning_active", True)
                    except Exception: pass
                    
                contents.append(body or raw)
            except (OSError, UnicodeDecodeError) as e:
                sys.stderr.write(f"\033[1;31mError loading skill '{skill}': {e}\033[0m\n")
    return "\n\n".join(contents)


def _exec_tool_cmd(cmd: str, interactive: bool = False) -> str:
    try:
        sanitized = PAGER_STRIP_RE.sub('', cmd.strip()).strip()
        workspace = os.environ.get("AI_WORKSPACE_PATH") or os.getcwd()
        env = {**os.environ, "AI_CONTEXT_RUN": "1"}
        if interactive:
            subprocess.run(sanitized, shell=True, cwd=workspace, env=env)
            return "__ABORT_TURN__"
        out = subprocess.check_output(sanitized, shell=True, text=True, timeout=15, cwd=workspace, env=env).strip()
        return f"{out}\n" if out else "Action executed successfully.\n"
    except subprocess.CalledProcessError:
        sys.stderr.write("\033[1;31m[sys] Tool execution failed or was cancelled.\033[0m\n")
        sys.stderr.flush()
        return "__ABORT_TURN__"
    except (OSError, subprocess.SubprocessError, TimeoutError) as e:
        sys.stderr.write(f"\033[1;31m[sys] Error running tool: {e}\033[0m\n")
        sys.stderr.flush()
        return "__ABORT_TURN__"


def run_local_tool(cmd: str) -> str: return _exec_tool_cmd(cmd, interactive=False)
def run_interactive_tool(cmd: str) -> str: return _exec_tool_cmd(cmd, interactive=True)


def get_system_context(query: str, context_file: str, stop_words: set[str], skills_dir: str, cfg_dir: str) -> str:
    if not (q_tokens := context.tokenize(query, stop_words)) or "\n" in query.strip(): return ""
    for entry in context.load_context_entries(context_file, stop_words):
        ent_tokens = entry.get("tokens", [])
        if any(q_tokens[i:i + len(ent_tokens)] == ent_tokens for i in range(len(q_tokens) - len(ent_tokens) + 1)):
            tool = entry.get("cmd", "").replace("[TOOL]", "").strip()
            if any(k in tool for k in ("read -p", "less", "fzf")): return run_interactive_tool(tool)
            if " --s" not in tool and not ui.confirm_tool(tool): return ""

            if "system" in tool.lower(): ensure_mysys_exists(skills_dir, cfg_dir)
            tool = tool.replace(" --s", "").strip()
            for flag in (" --leaf", " --glow", " --cat", " --mdcat", " --view"):
                tool = tool.replace(flag, "")
            intent_tokens = set(context.tokenize(entry.get("intent", ""), stop_words))

            args = " ".join(w for w in query.split() if any(c in w for c in ("/", "~", ".")) or (context.tokenize(w, stop_words) and context.tokenize(w, stop_words)[0] not in intent_tokens))
            if "$1" in tool or "{}" in tool: tool = tool.replace("$1", args).replace("{}", args).strip()

            sys.stderr.write(f"\033[2m[sys] Executing: {tool}\033[0m\n")
            sys.stderr.flush()
            return run_local_tool(tool)
    return ""


def load_skill_blueprints(base_skills_dir: str, stop_words: set[str]) -> list[dict[str, Any]]:
    """Universal indexer: walks entire skills directory and parses all markdown and YAML frontmatter skills."""
    blueprints: list[dict[str, Any]] = []
    seen_names = set()

    if os.path.exists(base_skills_dir):
        for root, _, files in os.walk(base_skills_dir):
            for f in files:
                if f.lower().endswith(".md"):
                    path = os.path.join(root, f)
                    try:
                        with open(path, "r", encoding="utf-8") as sf:
                            content = sf.read().strip()
                        if not content: continue

                        meta, body = parse_frontmatter(content)
                        lines = [l.strip() for l in (body or content).splitlines() if l.strip()]

                        folder_name = os.path.basename(root)

                        # 1. Universal YAML Frontmatter Standard (name, description, triggers)
                        if meta and ("name" in meta or "description" in meta):
                            skill_name = meta.get("name") or (folder_name if f.lower() == "skill.md" else os.path.splitext(f)[0])
                            desc = meta.get("description", "")
                            
                            intents = list(set(
                                RE_SKILL_SPLIT.split(skill_name.lower()) +
                                RE_SKILL_SPLIT.split(folder_name.lower()) +
                                context.tokenize(desc, stop_words) +
                                context.tokenize(skill_name, stop_words)
                            ))

                        # 2. Legacy Header: # [SKILL] name ---> intent1, intent2
                        elif lines and lines[0].startswith("# [SKILL]") and "--->" in lines[0]:
                            header, intents_raw = lines[0].split("--->", 1)
                            skill_name = header.replace("# [SKILL]", "").replace("#", "").strip()
                            intents = [i.strip().lower() for i in intents_raw.split(",") if i.strip()]
                            desc = next((l for l in lines[1:] if not l.startswith(("#", "---", ">", "*", "-", "import ")) and not RE_METADATA_LINE.match(l)), "")

                        # 3. Standard Markdown Title / Filename fallback
                        else:
                            base_name = folder_name if f.lower() == "skill.md" else os.path.splitext(f)[0]
                            skill_name = next((l.replace("#", "").strip() for l in lines if l.startswith("#")), base_name.replace("-", " ").replace("_", " ").title())
                            intents = list(set(RE_SKILL_SPLIT.split(base_name.lower()) + context.tokenize(skill_name, stop_words)))
                            desc = next((l for l in lines if not l.startswith(("#", "---", ">", "*", "-", "import ")) and not RE_METADATA_LINE.match(l)), "")

                        clean_name = skill_name.lower().strip()
                        if clean_name in seen_names:
                            continue
                        seen_names.add(clean_name)

                        clean_desc = desc.replace("\n", " ").strip() if desc else "No description provided."

                        blueprints.append({
                            "name": clean_name,
                            "path": path,
                            "rel_path": os.path.relpath(path, base_skills_dir),
                            "desc": clean_desc,
                            "intents": intents,
                            "tokens": context.tokenize(" ".join(intents), stop_words)
                        })
                    except Exception: pass
    return blueprints


def run_skill_selector(workspace: str, raw_cmd: str, base_skills_dir: str, stop_words: set[str], chat_history: Optional[list[dict[str, Any]]] = None) -> tuple[list[dict[str, Any]], Optional[str]]:
    """Interactive arrow-key skill loading overlay across all skill subdirectories."""
    if chat_history is None:
        try: chat_history = json.loads(sys.stdin.read().strip())
        except Exception: chat_history = [{"role": "system", "content": ""}]

    parts = raw_cmd.strip().split(maxsplit=1)
    search_query = parts[1].strip() if len(parts) > 1 else ""
    skill_list = load_skill_blueprints(base_skills_dir, stop_words)
    current_idx = 0
    sys.stderr.write("\033[?25l")
    sys.stderr.flush()

    try:
        while True:
            q_tokens = set(context.tokenize(search_query, stop_words)) if search_query else set()
            sq_lower = search_query.lower()
            candidates = []
            for s in skill_list:
                if not search_query:
                    candidates.append((1.0, s))
                else:
                    s_tokens = set(s["tokens"])
                    score = len(q_tokens & s_tokens) / len(q_tokens | s_tokens) if (q_tokens & s_tokens) else 0.0
                    if sq_lower in s["name"] or sq_lower in os.path.basename(s["path"]).lower() or any(sq_lower in i for i in s["intents"]):
                        score = max(score, 0.8)
                    if score > 0.0:
                        candidates.append((score, s))

            candidates.sort(key=lambda x: -x[0])
            num_opts = len(candidates)
            if num_opts > 0 and current_idx >= num_opts: current_idx = 0

            cols = shutil.get_terminal_size((80, 24)).columns or 80
            max_desc_len = max(10, cols - 42)

            if num_opts == 0:
                sys.stderr.write(f"\r\x1b[2K\033[1;30m[00/00]\033[0m ❯ \x1b[1;31m[No matches]\x1b[0m for: \033[1;33m{search_query}\033[0m\n\r\x1b[2K\033[3m   \"Backspace to delete\"\033[0m [Esc to exit]: ")
            else:
                _, sel = candidates[current_idx]
                clean_desc = sel['desc'].replace('\n', ' ').strip()
                desc = clean_desc if len(clean_desc) <= max_desc_len else clean_desc[:max_desc_len - 3] + "..."
                filter_ind = f" \033[90m| Filter: \033[1;33m{search_query}\033[0m" if search_query else ""
                sys.stderr.write(f"\r\x1b[2K\033[1;30m[\033[1;32m{current_idx + 1:02d}/{num_opts:02d}\033[1;30m]\033[0m ❯ \x1b[1;36m[skill]\x1b[0m \033[1;32m{sel['name']}\033[0m \033[90m({sel['rel_path']}){filter_ind}\033[0m\n\r\x1b[2K\033[3m   \"{desc}\"\033[0m [↵ load  Type to filter  Esc]: ")
            sys.stderr.flush()

            key = ui.get_key()
            clear_2_lines = "\r\x1b[2K\x1b[1A\r\x1b[2K"
            if key in ('\x03', '\x1b'):
                sys.stderr.write(f"{clear_2_lines}Cancelled.\n")
                return chat_history, None
            elif key in ('\r', '\n', ''):
                if num_opts > 0:
                    _, sel = candidates[current_idx]
                    try:
                        with open(sel["path"], "r", encoding="utf-8") as sf:
                            raw_file = sf.read().strip()
                        _, body = parse_frontmatter(raw_file)
                        body = body or raw_file

                        sys_c = chat_history[0]["content"] if chat_history else ""
                        raw_blocks = RE_SKILL_BLOCK.findall(sys_c)
                        cat = "personality" if "personality" in sel["path"] else ("code" if "code" in sel["path"] else "system")
                        
                        active_skills = []
                        for s_n, s_b in raw_blocks:
                            s_cat = "personality" if any(p in s_n for p in ("caveman", "pirate", "personality")) else "other"
                            if s_cat != cat and s_n != sel["name"]:
                                active_skills.append((s_n, s_b))
                        
                        active_skills.append((sel["name"], body))
                        if len(active_skills) > 3: active_skills = active_skills[-3:]
                        
                        base_p = sys_c.split("### Loaded On-Demand Skill:")[0].strip()
                        new_blocks = "\n\n".join(f"### Loaded On-Demand Skill: {n}\n{b}" for n, b in active_skills)
                        chat_history[0]["content"] = f"{base_p}\n\n{new_blocks}\n"

                        s_name = sel["name"].replace(" ", "-")
                        sys.stderr.write(f"{clear_2_lines}\033[1;32m✓ Skill '{sel['name']}' successfully loaded.\033[0m\n\n")
                        return chat_history, s_name
                    except Exception as e:
                        sys.stderr.write(f"{clear_2_lines}\033[1;31m[sys] Failed to load skill: {e}\033[0m\n")
                else:
                    sys.stderr.write(f"{clear_2_lines}No skill selected.\n")
                return chat_history, None
            elif key == '\x1b[A':
                if num_opts > 0: current_idx = max(0, current_idx - 1)
                sys.stderr.write(clear_2_lines)
            elif key == '\x1b[B':
                if num_opts > 0: current_idx = min(num_opts - 1, current_idx + 1)
                sys.stderr.write(clear_2_lines)
            elif key in ('\x7f', '\x08'):
                if search_query: search_query, current_idx = search_query[:-1], 0
                sys.stderr.write(clear_2_lines)
            elif len(key) == 1 and key.isprintable():
                search_query, current_idx = search_query + key, 0
                sys.stderr.write(clear_2_lines)
            else:
                sys.stderr.write(clear_2_lines)
    finally:
        sys.stderr.write("\033[?25h")
        sys.stderr.flush()


if __name__ == "__main__":
    CFG_DIR = os.path.expanduser("~/.config/py-agent")
    stop_words = getattr(context, "STOP_WORDS", {"is", "what", "it", "do", "any", "i", "have", "the", "a", "an", "on", "to", "for", "me", "you", "my", "your", "we", "us", "are", "about", "in", "how"})
    if len(sys.argv) < 3: sys.argv.extend(["", ""])
    hist, name = run_skill_selector(sys.argv[1], sys.argv[2], os.path.join(CFG_DIR, "skills"), stop_words)
    if hist: print(json.dumps(hist))
