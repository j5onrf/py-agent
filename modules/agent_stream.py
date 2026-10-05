#!/usr/bin/env python3
"""Streaming SSE, ANSI Geometry & Terminal Rendering Engine [Hardened Production Ready]"""

import os
import re
import sys
import threading
from typing import Any

from agent_state import get_state

RE_THINKING_TITLE = re.compile(r"^\s*Thinking Process:\s*", re.IGNORECASE)
RE_FINAL_ANSWER = re.compile(r"^\s*Final Answer:\s*", re.IGNORECASE)
RE_MULTIPLE_NEWLINES = re.compile(r"\n{2,}")
RE_TOOL_CALL_BLOCK = re.compile(
    r"<\|tool_call_start\|>.*?<\|tool_call_end\|>|<tool_call>[\s\S]*?</tool_call>|<arg_key>[\s\S]*?</arg_value>",
    re.DOTALL
)

_markdown_initialized: bool = False
_console_lock = threading.Lock()


def _init_rich_markdown() -> None:
    global _markdown_initialized
    with _console_lock:
        if _markdown_initialized:
            return
        from rich.markdown import CodeBlock, Markdown as _RM
        from rich.segment import Segment
        from rich.syntax import Syntax

        class CleanCodeBlock(CodeBlock):
            def __rich_console__(self, console: Any, options: Any) -> Any:
                code = str(self.text).rstrip()
                lexer = getattr(self, "lexer_name", "text") or "text"
                theme = getattr(self, "theme", "") or str(get_state("code_theme", "monokai"))
                syntax = Syntax(
                    code,
                    lexer,
                    theme=theme,
                    word_wrap=False,
                    padding=0,
                    background_color="default",
                )
                lines = console.render_lines(syntax, options)
                for line in lines:
                    while line and line[-1].text.isspace():
                        line.pop()
                    if line and line[-1].text != line[-1].text.rstrip(" "):
                        line[-1] = Segment(line[-1].text.rstrip(" "), line[-1].style)
                    yield from line
                    yield Segment.line()

        _RM.elements["fence"] = CleanCodeBlock
        _RM.elements["code_block"] = CleanCodeBlock
        _markdown_initialized = True


def Markdown(*args: Any, **kwargs: Any) -> Any:
    _init_rich_markdown()
    from rich.markdown import Markdown as _RM
    return _RM(*args, **kwargs)


def prepare_markdown(text: str) -> str:
    """Repairs unclosed fences and wraps bare code emitted by small SLMs."""
    if not text:
        return ""
    if text.count("```") % 2 != 0:
        text = text.rstrip() + "\n```"
    elif "```" not in text:
        code_kw = ("import ", "from ", "def ", "class ", "return ", "print(")
        if any(l.lstrip().startswith(code_kw) for l in text.splitlines()):
            text = f"```python\n{text.strip()}\n```"
    return text


def get_cursor_up_count(text: str, width: int) -> int:
    if not text:
        return 0
    w = max(1, width)
    clean = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", text)
    raw_lines = clean.split("\n")
    up = 0
    for line in raw_lines[:-1]:
        up += max(1, (len(line) + w - 1) // w)
    last = raw_lines[-1]
    if last:
        last_visual = max(1, (len(last) + w - 1) // w)
        up += last_visual - 1
    return up


_console_inst: Any = None
_console_err_inst: Any = None


def _get_console(stderr: bool = False) -> Any:
    global _console_inst, _console_err_inst
    with _console_lock:
        if stderr:
            if _console_err_inst is None:
                from rich.console import Console
                _console_err_inst = Console(stderr=True)
            return _console_err_inst
        if _console_inst is None:
            from rich.console import Console
            _console_inst = Console(stderr=False)
        return _console_inst


class _LazyConsole:
    def __init__(self, stderr: bool = False) -> None:
        self._stderr = stderr

    def __getattr__(self, name: str) -> Any:
        return getattr(_get_console(self._stderr), name)


_console, _console_err = _LazyConsole(False), _LazyConsole(True)


def _escape_markup(text: str) -> str:
    return str(text).replace("[", "\\[")


class RichStreamer:
    def __init__(self, prefix: str = "", active: bool = True, spinner: Any = None, round_idx: int = 0) -> None:
        self.prefix, self.active, self.spinner = prefix, active and sys.stdout.isatty(), spinner
        self.acc_think, self.acc_ans, self.phase, self.think_hdr_printed, self.ans_started = "", "", "INIT", False, False
        self.in_post_think = False
        self.round_idx = round_idx
        is_sq = get_state("box_style", 1) not in (1, 6, 7)
        self.c_top, self.c_bot = ("┌", "└") if is_sq else ("╭", "╰")

    def _stop_spinner(self, done_msg: str | None = None) -> None:
        if self.spinner:
            try:
                self.spinner.stop(done_msg=done_msg)
            except Exception:
                pass

    def start(self) -> None:
        if self.active:
            try:
                sys.stdout.write("\033[?25h")
                sys.stdout.flush()
            except OSError:
                pass

    def update(self, token: str) -> None:
        if not self.active:
            if "<think>" in token and self.phase != "THINKING":
                self.phase, token = "THINKING", token.replace("<think>", "")
            if "</think>" in token:
                parts = token.split("</think>", 1)
                self.phase, token = "ANSWER", parts[1]
            if self.phase != "THINKING" and token:
                self._stop_spinner()
                try:
                    sys.stdout.write(token.replace("\r\n", "\n").replace("\n", "\r\n"))
                    sys.stdout.flush()
                except OSError:
                    pass
            return

        if "<think>" in token:
            if self.ans_started:
                self.in_post_think = True
            else:
                self.phase = "THINKING"
            token = token.replace("<think>", "")

        show_think = os.environ.get("AI_SHOW_THINKING", "1") == "1"

        if "</think>" in token:
            parts = token.split("</think>", 1)
            if self.in_post_think:
                self.in_post_think = False
                if len(parts) > 1 and parts[1]:
                    self.update(parts[1])
                return
            if parts[0]:
                self.update(parts[0])
            if show_think and self.think_hdr_printed and not self.ans_started:
                sep = "" if self.acc_think.endswith("\n") else "\r\n"
                _console_err.print(f"{sep}[dim]{self.c_bot}────────────────────────────────────────────────────────[/dim]\n")
                sys.stderr.flush()
            self.phase = "ANSWER"
            self._stop_spinner()
            if len(parts) > 1 and parts[1]:
                self.update(parts[1])
            return

        if self.in_post_think:
            self.acc_think += token
            return

        if self.phase == "INIT":
            self.phase = "ANSWER"

        if self.phase == "THINKING":
            tok = RE_MULTIPLE_NEWLINES.sub("\n", RE_THINKING_TITLE.sub("", token))
            if self.acc_think.endswith("\n") and tok.startswith("\n"):
                tok = tok.lstrip("\r\n")
            self.acc_think += tok
            if show_think and tok:
                if not self.think_hdr_printed and tok.strip():
                    self.think_hdr_printed = True
                    self._stop_spinner()
                    _console_err.print(f"[dim]{self.c_top}─ ∿ ────────────────────────────────────────────────────[/dim]")
                    tok = tok.lstrip("\r\n")
                if tok:
                    try:
                        sys.stderr.write(tok.replace("\r\n", "\n").replace("\n", "\r\n"))
                        sys.stderr.flush()
                    except OSError:
                        pass
        else:
            tok = RE_FINAL_ANSWER.sub("", token)
            if not self.ans_started:
                tok = tok.lstrip("\r\n\t ")
                if not tok:
                    return
                self._stop_spinner()
                self.ans_started, p_clean = True, self.prefix.strip()
                p_str = f"{p_clean}\n\n" if (p_clean and tok.startswith(("```", "#", "---"))) else (f"{p_clean} " if p_clean else "")
                p_style = "\033[1;32m" if "Agent" in p_clean else "\033[1;36m"
                if p_str:
                    try:
                        sys.stdout.write(f"{p_style}{p_str}\033[0m")
                        sys.stdout.flush()
                    except OSError:
                        pass
                self.acc_ans += p_str

            self.acc_ans += tok
            if tok:
                try:
                    sys.stdout.write(tok.replace("\r\n", "\n").replace("\n", "\r\n"))
                    sys.stdout.flush()
                except OSError:
                    pass

    def stop(self, interrupted: bool = False) -> None:
        self._stop_spinner()
        if interrupted:
            try:
                sys.stdout.write("\033[?25h\r\n")
                sys.stdout.flush()
            except OSError:
                pass
            return

        show_think = os.environ.get("AI_SHOW_THINKING", "1") == "1"
        if self.phase == "THINKING" and show_think and self.think_hdr_printed and not self.ans_started:
            sep = "" if self.acc_think.endswith("\n") else "\r\n"
            _console_err.print(f"{sep}[dim]{self.c_bot}────────────────────────────────────────────────────────[/dim]\n")
            self.phase = "ANSWER"

        render_md = bool(get_state("render_markdown", False))
        if self.ans_started and not render_md:
            try:
                sys.stdout.write("\r\n")
                sys.stdout.flush()
            except OSError:
                pass


def _process_stream_chunk(content: str, reasoning: str, in_think_block: bool) -> tuple[str, bool, bool]:
    if content:
        if "Final Answer:" in content:
            content = RE_FINAL_ANSWER.sub("", content).lstrip()
        if "<|tool_call" in content:
            content = RE_TOOL_CALL_BLOCK.sub("", content).replace("<|tool_call_start|>", "").replace("<|tool_call_end|>", "")

    if reasoning:
        think_part = f"<think>{reasoning}" if not in_think_block else reasoning
        if content:
            has_closer = "</think>" in content
            closer = "" if has_closer else "</think>"
            new_in_think = ("<think>" in content and content.rindex("<think>") > content.rindex("</think>")) if has_closer else False
            return f"{think_part}{closer}{content}", False, new_in_think
        return think_part, True, True

    if content:
        if in_think_block and "</think>" not in content:
            return f"</think>{content}", False, False

        if "<think>" in content and "</think>" in content:
            in_think = content.rindex("<think>") > content.rindex("</think>")
        elif "<think>" in content:
            in_think = True
        elif "</think>" in content:
            in_think = False
        else:
            in_think = in_think_block

        return content, in_think, in_think

    return "", False, in_think_block
