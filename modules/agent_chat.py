#!/usr/bin/env python3
"""Unified Agentic Brainstorm, Thinking & Follow-up Recommendation Engine [Production Ready]"""

import json
import os
import re
import sys
import urllib.request as urlreq

CFG_DIR = os.path.expanduser("~/.config/py-agent")
if (mod_dir := os.path.join(CFG_DIR, "modules")) not in sys.path:
    sys.path.append(mod_dir)

try:
    import agent_cloud
except ImportError:
    agent_cloud = None

try:
    import agent_ui as ui
except ImportError:
    ui = None

RE_QUESTION_SPLIT = re.compile(r"(?<=\?)\s+")
RE_THINK_BLOCK = re.compile(r"<think(?:ing)?>[\s\S]*?(?:</think(?:ing)?>|$)|<thought>[\s\S]*?(?:</thought>|$)", re.DOTALL | re.IGNORECASE)
RE_CLEAN_BULLETS = re.compile(r"^(?:\d+[\.\)]|\*|-|\+|\[\d+\])\s*")
RE_CONTROL_CHARS = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b\][^\x07]*(?:\x07|\x1b\\)|[\x00-\x08\x0b-\x1f\x7f]")

# 1. Validate Input Payload Shape
try:
    raw_stdin = sys.stdin.read()
    history = json.loads(raw_stdin)
    if not isinstance(history, list) or not all(isinstance(m, dict) for m in history):
        sys.stderr.write("Error: Chat history must be a JSON array of message objects.\n")
        sys.exit(1)
except (OSError, json.JSONDecodeError, ValueError) as e:
    sys.stderr.write(f"Error: No valid chat history passed to recommendation engine: {e}\n")
    sys.exit(1)

# 2. Parse Subcommand & Option Count
q_str = " ".join(sys.argv[1:]).lower().strip()
m = re.match(r"^/?([ftba])(?:\s+(\d+))?$", q_str)
cmd, count = (
    m.group(1) if m else "f",
    int(m.group(2)) if (m and m.group(2) and 1 <= int(m.group(2)) <= 10) else 3,
)

META_MAP = {
    "b": ("brainstorm.md", "Brainstorm"),
    "t": ("thinking.md", "Thinking"),
    "a": ("all", "All"),
    "f": ("follow-up.md", "Follow-up"),
}
file_name, output_hdr = META_MAP.get(cmd, META_MAP["f"])


def _build_option_placeholders(n: int) -> str:
    return "\n".join(f"[Option {i}]" for i in range(1, n + 1))


# 3. Load Template Files (Fail Cleanly If Missing)
if cmd == "a":
    meta_skills = [
        ("follow-up.md", "Follow-up"),
        ("thinking.md", "Thinking"),
        ("brainstorm.md", "Brainstorm"),
    ]
    prompts = {}
    for fn, hdr in meta_skills:
        p = os.path.join(CFG_DIR, "skills", "meta", fn)
        if not os.path.isfile(p):
            sys.stderr.write(f"Error: Required meta skill missing: {p}\n")
            sys.exit(1)
        try:
            with open(p, "r", encoding="utf-8") as f:
                txt = f.read().strip()
            prompts[hdr] = txt.split("Template:")[0].strip() if "Template:" in txt else txt
        except (OSError, UnicodeDecodeError) as e:
            sys.stderr.write(f"Error reading {p}: {e}\n")
            sys.exit(1)

    opts = _build_option_placeholders(count)
    prompt = (
        f"Analyze the preceding conversation history and output exactly three sections: Follow-up, Thinking, and Brainstorm.\n"
        f"Each section must contain exactly {count} numbered options, strictly 6 to 10 words long.\n"
        "Output ONLY these three sections, with no conversational introductions or explanations.\n\n"
        f"Template (Ensure headers are exact, flush left, with no empty lines between options):\n"
        f"Follow-up\n{opts}\nThinking\n{opts}\nBrainstorm\n{opts}\n\n"
        f"<FOLLOW_UP_RULES>\n{prompts.get('Follow-up', '')}\n</FOLLOW_UP_RULES>\n\n"
        f"<THINKING_RULES>\n{prompts.get('Thinking', '')}\n</THINKING_RULES>\n\n"
        f"<BRAINSTORM_RULES>\n{prompts.get('Brainstorm', '')}\n</BRAINSTORM_RULES>"
    )
else:
    meta_path = os.path.join(CFG_DIR, "skills", "meta", file_name)
    if not os.path.isfile(meta_path):
        sys.stderr.write(f"Error: Required meta skill missing: {meta_path}\n")
        sys.exit(1)
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            template_raw = f.read().strip()
    except (OSError, UnicodeDecodeError) as e:
        sys.stderr.write(f"Error reading {meta_path}: {e}\n")
        sys.exit(1)

    opts = _build_option_placeholders(count)
    prompt = re.sub(r"\[Option 1\][\s\S]*?\[Option 3\]", opts, template_raw)
    prompt = prompt.replace("exactly 3", f"exactly {count}")

history.append({
    "role": "user",
    "content": f"[COMMAND: Do not continue the conversation. Do not reply to the last message. Execute this analytical directive immediately without preambles.]\n\n{prompt}",
})

# 4. Resolve Active Cloud Configurations from .env
configs = []
if agent_cloud:
    for url, headers, body, timeout in agent_cloud.get_active_configs(history):
        c_body = {**body, "max_tokens": 500, "chat_template_kwargs": {"enable_thinking": False}}
        configs.append((url, headers, c_body, min(timeout, 30)))

# Local server fallback if no cloud providers are active
if not configs:
    configs.append((
        "http://localhost:8080/v1/chat/completions",
        {},
        {"model": "local-model", "messages": history, "max_tokens": 500, "stream": True, "chat_template_kwargs": {"enable_thinking": False}},
        180,
    ))

# 5. Query Active Engine with Streaming & Structural Output Validation
for url, headers, body, timeout in configs:
    req = urlreq.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    spinner = ui.InlineSpinner() if (ui and sys.stdout.isatty()) else None
    if spinner:
        spinner.start("Analyzing context...")

    try:
        with urlreq.urlopen(req, timeout=timeout) as resp:
            first, chunks = True, []
            for line in resp:
                if (dec := line.decode("utf-8", errors="ignore").strip()) and dec != "[DONE]":
                    if dec.startswith("data:"):
                        dec = dec[5:].strip()
                    try:
                        data = json.loads(dec)
                        content = (
                            data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                            if "choices" in data
                            else data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                        )
                        if content:
                            if first:
                                if spinner:
                                    spinner.stop()
                                    spinner = None
                                if not (content := content.lstrip()):
                                    continue
                                first = False
                            chunks.append(content)
                    except (json.JSONDecodeError, KeyError, IndexError, TypeError, ValueError) as exc:
                        if os.environ.get("AI_DEBUG") == "1":
                            sys.stderr.write(f"\r\n[debug] Skipped stream frame: {exc}\r\n")

            if spinner:
                spinner.stop()
                spinner = None

            raw_text = RE_THINK_BLOCK.sub("", "".join(chunks)).strip()
            lines = [l.strip() for l in raw_text.splitlines() if l.strip()]

            if lines:
                hdr_map = {
                    k: v
                    for keys, v in [
                        (("follow-up", "follow-ups", "followup", "followups"), "Follow-up"),
                        (("thinking", "think", "thought", "thoughts"), "Thinking"),
                        (("brainstorm", "brainstorming", "brainstorms"), "Brainstorm"),
                    ]
                    for k in keys
                }

                formatted_output = []
                emitted_options = 0

                first_clean = lines[0].strip("*#: \t").lower().rstrip("s:")
                start_idx = 0
                if first_clean not in hdr_map:
                    start_idx = next((i for i, l in enumerate(lines) if l.strip("*#: \t").lower().rstrip("s:") in hdr_map), 0)
                    if start_idx == 0 and first_clean not in hdr_map:
                        formatted_output.append(f"\033[1;32mAI:\033[0m {output_hdr}")

                for l in lines[start_idx:]:
                    clean = l.strip("*#: \t").lower().rstrip("s:")
                    if clean in hdr_map:
                        formatted_output.append(f"\033[1;32mAI:\033[0m {hdr_map[clean]}")
                    else:
                        for q in [x.strip() for x in RE_QUESTION_SPLIT.split(l) if x.strip()]:
                            clean_q = RE_CLEAN_BULLETS.sub("", q).strip()
                            # Neutralize ANSI and control escape characters
                            clean_q = RE_CONTROL_CHARS.sub("", clean_q).strip()
                            if clean_q:
                                formatted_output.append(clean_q)
                                emitted_options += 1

                # Only write to terminal if valid options were produced
                if emitted_options > 0:
                    sys.stdout.write("\n" + "\n".join(formatted_output) + "\n")
                    sys.stdout.flush()
                    sys.exit(0)

    except KeyboardInterrupt:
        if spinner:
            spinner.stop()
        sys.stderr.write("\n\033[90m[sys] Interrupted.\033[0m\n")
        sys.exit(130)
    except (urlreq.URLError, TimeoutError, OSError) as e:
        if spinner:
            spinner.stop()
        if os.environ.get("AI_DEBUG") == "1":
            sys.stderr.write(f"\r\n[debug] Provider failed: {e}\r\n")

sys.stderr.write("Error: All recommendation service endpoints are offline.\n")
sys.exit(1)
