#!/usr/bin/env python3
"""Autonomous Task Loop Engine [Production Edition]"""

import argparse
import json
import os
import re
import sys
import time
from typing import Any

CFG_DIR = os.path.expanduser("~/.config/py-agent")
sys.path.append(os.path.join(CFG_DIR, "modules"))

try:
    import agent_core as core
    import agent_skills as skills
    import agent_tools as tools
    import agent_ui as ui
except ImportError as e:
    sys.stderr.write(f"\033[1;31m[Loop Engine] Module import error: {e}\033[0m\n")
    sys.exit(1)

COMPLETION_PATTERNS = [
    re.compile(r"\bTASK COMPLETE\b", re.IGNORECASE),
    re.compile(r"\bGOAL COMPLETE\b", re.IGNORECASE),
    re.compile(r"\bTASK FINISHED\b", re.IGNORECASE),
    re.compile(r"### Task Report\s*\n.*?(?:passed|verified|completed)", re.IGNORECASE | re.DOTALL),
]


def _read_spec_file(workspace: str, file_name: str = "TASK.md") -> str:
    target = os.path.join(workspace, file_name)
    if os.path.isfile(target):
        try:
            with open(target, "r", encoding="utf-8") as f:
                return f.read().strip()
        except OSError:
            pass
    return ""


def _log_task_turn(workspace: str, turn_idx: int, user_prompt: str, response: str, status: str = "IN_PROGRESS") -> None:
    agent_dir = os.path.join(workspace, ".agent")
    os.makedirs(agent_dir, exist_ok=True)
    log_file = os.path.join(agent_dir, "task_log.md")
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

    entry = (
        f"\n## [Turn {turn_idx}] - {timestamp} - Status: {status}\n\n"
        f"### Directive / Prompt:\n{user_prompt}\n\n"
        f"### Agent Response & Tool Execution:\n{response}\n\n"
        f"---\n"
    )
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(entry)
    except OSError:
        pass


def is_task_complete(response_text: str) -> bool:
    if not response_text:
        return False
    return any(p.search(response_text) for p in COMPLETION_PATTERNS)


def run_task_loop(
    goal: str,
    workspace: str,
    max_turns: int = 15,
    spec_file: str | None = None,
    no_log: bool = False,
) -> bool:
    """Executes the autonomous loop with failure decomposition and completion verification."""
    os.environ["AI_CONFIRM_GATES"] = "0"

    spec_content = _read_spec_file(workspace, spec_file) if spec_file else _read_spec_file(workspace, "TASK.md")
    effective_goal = goal.strip()
    if not effective_goal and spec_content:
        effective_goal = f"Execute all unfinished tasks in TASK.md:\n\n{spec_content}"
    elif not effective_goal:
        ui._console.print("[red][Loop Error] No goal provided and TASK.md not found.[/red]")
        return False

    ui._console.print(f"\n[bold green]✦ [Loop Engine][/bold green] Starting autonomous loop for workspace: [cyan]{workspace}[/cyan]")
    ui._console.print(f"[dim]Goal: {effective_goal[:120]}... (Max turns: {max_turns})[/dim]\n")

    sys_prompt = (
        "You are an autonomous senior developer agent running inside a verified feedback loop.\n"
        f"Active Workspace Root: {workspace}\n"
        "Your mission is to autonomously complete the user goal using your available tools.\n\n"
        "### Workflow Rules:\n"
        "1. Inspect files with read_file or search_code before making edits.\n"
        "2. Apply targeted edits with edit_file. Verify syntax and tests after editing.\n"
        "3. Run automated test commands using run_command to prove correctness.\n"
        "4. When 100% of the goal is complete and all tests pass, output 'TASK COMPLETE' with a summary."
    )

    history = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": f"### Target Goal:\n{effective_goal}\n\nExecute all necessary steps to complete this goal."}
    ]

    consecutive_failures = 0

    for turn in range(1, max_turns + 1):
        ui._console.print(f"[bold bright_blue]─── Task Turn {turn}/{max_turns} ─────────────────────────────[/bold bright_blue]")

        if consecutive_failures >= 2:
            decomp_directive = (
                "[Harness Directive - Failure Decomposition]: Your previous action failed repeatedly. "
                "Stop retrying the full file. Decompose your immediate next step:\n"
                "1. Inspect exact 15-20 lines via read_file(path, line_start, line_end) or search_code.\n"
                "2. Apply a targeted edit_file to only that section.\n"
                "3. Execute run_command to verify."
            )
            history.append({"role": "system", "content": decomp_directive})
            consecutive_failures = 0

        ans = core.stream_response(history, prefix="Agent:", show_stats=True, thinking_budget=0, is_agent=True)

        if not ans:
            ui._console.print("[yellow][Loop Engine] Turn yielded empty response. Retrying with state reminder...[/yellow]")
            consecutive_failures += 1
            history.append({"role": "user", "content": "Continue executing the goal. Report current progress or next tool step."})
            continue

        history.append({"role": "assistant", "content": ans})

        if any(err_tag in ans for err_tag in ("[error]", "[tool error]", "SyntaxError", "FAILED")):
            consecutive_failures += 1
        else:
            consecutive_failures = 0

        if not no_log:
            _log_task_turn(workspace, turn, history[-2].get("content", ""), ans)

        if is_task_complete(ans):
            ui._console.print(f"\n[bold green]✔ [Loop Engine] Task completed successfully in {turn} turns![/bold green]\n")
            if not no_log:
                _log_task_turn(workspace, turn, "Final Verification", ans, status="COMPLETED")
            return True

        history.append({"role": "user", "content": "Continue with the next step. If completely finished and verified, output 'TASK COMPLETE'."})

    ui._console.print(f"\n[bold yellow]▲ [Loop Engine] Reached max turn limit ({max_turns}) without explicit completion marker.[/bold yellow]\n")
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Autonomous Task Loop Engine")
    parser.add_argument("goal", nargs="*", help="Goal string or task instruction")
    parser.add_argument("-n", "--turns", type=int, default=15, help="Maximum loop turns (default: 15)")
    parser.add_argument("-f", "--file", type=str, default=None, help="Optional task specification file (e.g. TASK.md)")
    parser.add_argument("--no-log", action="store_true", help="Disable .agent/task_log.md logging")

    args = parser.parse_args()
    workspace = os.environ.get("AI_WORKSPACE_PATH", os.getcwd())
    goal_str = " ".join(args.goal).strip()

    try:
        success = run_task_loop(
            goal=goal_str,
            workspace=workspace,
            max_turns=args.turns,
            spec_file=args.file,
            no_log=args.no_log,
        )
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        ui._console.print("\n[yellow][Loop Engine] Loop cancelled by user.[/yellow]")
        sys.exit(130)


if __name__ == "__main__":
    main()
