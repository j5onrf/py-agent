#!/usr/bin/env python3
"""Streaming SSE, ANSI Geometry & Terminal Rendering Engine [Hardened Production Ready]"""

import os
import re
import shutil
import sys
import threading
import time
from typing import Any

from rich.cells import cell_len
from rich.markup import escape as rich_escape

from agent_state import get_state

RE_THINKING_TITLE = re.compile(r"^\s*Thinking Process:\s*", re.IGNORECASE)
RE_FINAL_ANSWER = re.compile(r"^\s*Final Answer:\s*", re.IGNORECASE)
RE_MULTIPLE_NEWLINES = re.compile(r"\n{2,}")
RE_TOOL_CALL_BLOCK = re.compile(
    r"<\|tool_call_start\|>[\s\S]*?<\|tool_call_end\|>|<tool_call>[\s\S]*?</tool_call>|<arg_key>[\s\S]*?</arg_key>|<arg_value>[\s\S]*?</arg_value>",
    re.DOTALL,
)

TOOL_MARKERS = ("<|tool_call", "<tool_call", "<arg_key", "<arg_value")

_markdown_class: type | None = None
_console_lock = threading.Lock()
_cached_code_theme: str = ""
_cached_code_theme_time: float = 0.0


def _get_code_theme(max_age: float = 10.0) -> str:
    """Caches resolved code theme for 10s to avoid threading lock and disk stat per code block."""
    global _cached_code_theme, _cached_code_theme_time
    now = time.monotonic()
    if _cached_code_theme and (now - _cached_code_theme_time < max_age):
        return _cached_code_theme
    _cached_code_theme = str(get_state("code_theme", "monokai"))
    _cached_code_theme_time = now
    return _cached_code_theme


def _get_markdown_class() -> type:
    global _markdown_class
    if _markdown_class is not None:
        return _markdown_class

    with _console_lock:
        if _markdown_class is not None:
            return _markdown_class

        from rich.markdown import CodeBlock, Markdown as _RM
        from rich.segment import Segment
        from rich.syntax import Syntax

        class CleanCodeBlock(CodeBlock):
            def __rich_console__(self, console: Any, options: Any) -> Any:
                code = str(self.text).rstrip()
                lexer = getattr(self, "lexer_name", "text") or "text"
                theme = getattr(self, "theme", "") or _get_code_theme()
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

        class AgentMarkdown(_RM):
            elements = {
                **_RM.elements,
                "fence": CleanCodeBlock,
                "code_block": CleanCodeBlock,
            }

        _markdown_class = AgentMarkdown
        return _markdown_class


def Markdown(*args: Any, **kwargs: Any) -> Any:
    md_cls = _get_markdown_class()
    return md_cls(*args, **kwargs)


def prepare_markdown(text: str) -> str:
    """Repairs unclosed fences and wraps bare code blocks without false-positive triggers."""
    if not text:
        return ""
    if text.count("```") % 2 != 0:
        text = text.rstrip() + "\n```"
    elif "```" not in text:
        code_kw = ("import ", "from ", "def ", "class ", "return ", "print(")
        code_lines = sum(1 for line in text.splitlines() if line.lstrip().startswith(code_kw))
        has_def_or_class = any(line.lstrip().startswith(("def ", "class ")) for line in text.splitlines())
        if code_lines >= 2 or has_def_or_class:
            text = f"```python\n{text.strip()}\n```"
    return text


def get_cursor_up_count(text: str, width: int) -> int:
    """Calculates visual terminal row height based on cell width and clamps to visible viewport."""
    if not text:
        return 0
    w = max(1, width)
    clean = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", text).replace("\r", "")
    raw_lines = clean.split("\n")
    up = 0
    for line in raw_lines[:-1]:
        v_width = cell_len(line)
        up += max(1, (v_width + w - 1) // w)
    last = raw_lines[-1]
    if last:
        last_width = cell_len(last)
        last_visual = max(1, (last_width + w - 1) // w)
        up += last_visual - 1

    term_rows = shutil.get_terminal_size((80, 24)).lines
    return min(up, max(0, term_rows - 1))


_console_inst: Any = None
_console_err_inst: Any = None


def _get_console(stderr: bool = False) -> Any:
    global _console_inst, _console_err_inst
    if stderr and _console_err_inst is not None:
        return _console_err_inst
    if not stderr and _console_inst is not None:
        return _console_inst

    with _console_lock:
        from rich.console import Console
        if stderr:
            if _console_err_inst is None:
                _console_err_inst = Console(stderr=True)
            return _console_err_inst
        if _console_inst is None:
            _console_inst = Console(stderr=False)
        return _console_inst


class _LazyConsole:
    def __init__(self, stderr: bool = False) -> None:
        self._stderr = stderr

    def __getattr__(self, name: str) -> Any:
        return getattr(_get_console(self._stderr), name)


_console, _console_err = _LazyConsole(False), _LazyConsole(True)


def _escape_markup(text: str) -> str:
    return rich_escape(str(text))


class RichStreamer:
    def __init__(self, prefix: str = "", active: bool = True, spinner: Any = None, round_idx: int = 0) -> None:
        self.prefix = prefix
        self.active = active and sys.stdout.isatty()
        self.spinner = spinner
        self.round_idx = round_idx
        self._acc_think_parts: list[str] = []
        self._acc_ans_parts: list[str] = []
        self.phase = "INIT"
        self.think_hdr_printed = False
        self.ans_started = False
        self.in_post_think = False
        self.box_style = get_state("box_style", 1)
        self.show_thinking = os.environ.get("AI_SHOW_THINKING", "1") == "1"

    @property
    def acc_think(self) -> str:
        return "".join(self._acc_think_parts)

    @property
    def acc_ans(self) -> str:
        return "".join(self._acc_ans_parts)

    def _get_think_borders(self) -> tuple[str, str]:
        term_width = shutil.get_terminal_size((80, 24)).columns
        if self.box_style == 9:
            top_dashes = max(10, term_width - 6)
            bot_dashes = max(10, term_width - 2)
            return f"╭─ ∿ {'─' * top_dashes}╮", f"╰{'─' * bot_dashes}╯"

        top_len = min(52, max(10, term_width - 6))
        bot_len = min(56, max(10, term_width - 2))
        if self.box_style in (2, 4):
            return f"┌─ ∿ {'─' * top_len}", f"└{'─' * bot_len}"
        return f"╭─ ∿ {'─' * top_len}", f"╰{'─' * bot_len}"

    def _stop_spinner(self, done_msg: str | None = None) -> None:
        if self.spinner:
            try:
                self.spinner.stop(done_msg=done_msg)
            except (AttributeError, OSError, RuntimeError):
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
            if "<think>" in token:
                if self.ans_started:
                    self.in_post_think = True
                else:
                    self.phase = "THINKING"
                token = token.replace("<think>", "")

            if "</think>" in token:
                parts = token.split("</think>", 1)
                if self.in_post_think:
                    self.in_post_think = False
                    if parts[0]:
                        self._acc_think_parts.append(parts[0])
                    if len(parts) > 1 and parts[1]:
                        self.update(parts[1])
                    return
                self.phase = "ANSWER"
                token = parts[1] if len(parts) > 1 else ""

            if self.phase == "ANSWER" and token and not self.in_post_think:
                self.ans_started = True
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

        if "</think>" in token:
            parts = token.split("</think>", 1)
            if self.in_post_think:
                self.in_post_think = False
                if parts[0]:
                    self._acc_think_parts.append(parts[0])
                if len(parts) > 1 and parts[1]:
                    self.update(parts[1])
                return
            if parts[0]:
                self.update(parts[0])
            if self.show_thinking and self.think_hdr_printed and not self.ans_started:
                sep = "" if (self.acc_think.endswith("\n")) else "\r\n"
                _, bot_border = self._get_think_borders()
                _console_err.print(f"{sep}[dim]{bot_border}[/dim]\n")
                sys.stderr.flush()
            self.phase = "ANSWER"
            self._stop_spinner()
            if len(parts) > 1 and parts[1]:
                self.update(parts[1])
            return

        if self.in_post_think:
            self._acc_think_parts.append(token)
            return

        if self.phase == "INIT":
            self.phase = "ANSWER"

        if self.phase == "THINKING":
            tok = RE_MULTIPLE_NEWLINES.sub("\n", RE_THINKING_TITLE.sub("", token))
            if self.acc_think.endswith("\n") and tok.startswith("\n"):
                tok = tok.lstrip("\r\n")
            self._acc_think_parts.append(tok)
            if self.show_thinking and tok:
                if not self.think_hdr_printed and tok.strip():
                    self.think_hdr_printed = True
                    self._stop_spinner()
                    top_border, _ = self._get_think_borders()
                    _console_err.print(f"[dim]{top_border}[/dim]")
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
                self.ans_started = True
                p_clean = self.prefix.strip()
                p_str = (
                    f"{p_clean}\n\n"
                    if (p_clean and tok.startswith(("```", "#", "---")))
                    else (f"{p_clean} " if p_clean else "")
                )
                p_style = "\033[1;32m" if "Agent" in p_clean else "\033[1;36m"
                if p_str:
                    try:
                        sys.stdout.write(f"{p_style}{p_str}\033[0m")
                        sys.stdout.flush()
                    except OSError:
                        pass
                self._acc_ans_parts.append(p_str)

            self._acc_ans_parts.append(tok)
            if tok:
                try:
                    sys.stdout.write(tok.replace("\r\n", "\n").replace("\n", "\r\n"))
                    sys.stdout.flush()
                except OSError:
                    pass

    def stop(self, interrupted: bool = False) -> None:
        self._stop_spinner()
        if interrupted:
            if self.phase == "THINKING" and self.show_thinking and self.think_hdr_printed and not self.ans_started:
                sep = "" if (self.acc_think.endswith("\n")) else "\r\n"
                _, bot_border = self._get_think_borders()
                _console_err.print(f"{sep}[dim]{bot_border}[/dim]\n")
                self.phase = "ANSWER"
            try:
                sys.stdout.write("\033[?25h\r\n")
                sys.stdout.flush()
            except OSError:
                pass
            return

        if self.phase == "THINKING" and self.show_thinking and self.think_hdr_printed and not self.ans_started:
            sep = "" if (self.acc_think.endswith("\n")) else "\r\n"
            _, bot_border = self._get_think_borders()
            _console_err.print(f"{sep}[dim]{bot_border}[/dim]\n")
            self.phase = "ANSWER"

        # Note: When render_markdown is active, agent_core performs a cursor rewind
        # and re-prints Markdown cleanly; trailing newline is omitted here to prevent blank gaps.
        render_md = bool(get_state("render_markdown", False))
        if self.ans_started and not render_md:
            try:
                sys.stdout.write("\r\n")
                sys.stdout.flush()
            except OSError:
                pass


def _process_stream_chunk(content: str, reasoning: str, in_think_block: Any = False) -> tuple[str, bool, Any]:
    if content:
        if "Final Answer:" in content:
            content = RE_FINAL_ANSWER.sub("", content)
        if any(marker in content for marker in TOOL_MARKERS):
            content = RE_TOOL_CALL_BLOCK.sub("", content)
            if "<|tool_call_start|>" in content:
                content = content.replace("<|tool_call_start|>", "")
            if "<|tool_call_end|>" in content:
                content = content.replace("<|tool_call_end|>", "")

    # Normalize incoming think state:
    # "reasoning" -> started by server reasoning delta
    # "content"   -> started by literal <think> tag in content stream
    # "" / False  -> not currently in a think block
    think_mode = in_think_block if isinstance(in_think_block, str) else ("reasoning" if in_think_block else "")

    # 1. Server emits explicit reasoning delta
    if reasoning:
        prefix = "<think>" if not think_mode else ""
        if content:
            return f"{prefix}{reasoning}</think>{content}", False, ""
        return f"{prefix}{reasoning}", True, "reasoning"

    # 2. Server emits content delta
    if content:
        if think_mode == "reasoning":
            if "</think>" in content:
                parts = content.split("</think>", 1)
                rem = parts[1]
                in_rem = "<think>" in rem
                return content, in_rem, ("content" if in_rem else "")
            return f"</think>{content}", False, ""

        if "<think>" in content and "</think>" in content:
            is_in = content.rindex("<think>") > content.rindex("</think>")
            return content, is_in, ("content" if is_in else "")
        elif "<think>" in content:
            return content, True, "content"
        elif "</think>" in content:
            return content, False, ""
        else:
            is_in = bool(think_mode)
            return content, is_in, think_mode

    return "", False, think_mode
