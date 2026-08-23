#!/usr/bin/env python3
"""
Ralph Wiggum Autonomous Task Loop Engine [Production Grade]
Handles multi-turn autonomous goal execution, completion detection, 
stagnation recovery, and execution logging.
"""

import argparse
import os
import sys
import time
from typing import Any

CFG_DIR = os.path.expanduser("~/.config/py-agent")
sys.path.append(os.path.join(CFG_DIR, "modules"))

try:
    import agent_core as core
except ImportError:
    sys.stderr.write("[error] Core module (agent_core.py) not found in ~/.config/py-agent/modules\n")
    sys.exit(1)

COMPLETION_KEYWORDS = frozenset({
    "TASK COMPLETE", "TASK COMPLETED", "ALL TASKS COMPLETED", 
    "TASK FINISHED", "ALL TASKS HAVE BEEN COMPLETED", "[TASK COMPLETE]"
})


def is_task_complete(ans: str | None, history: list[dict[str, Any]]) -> bool:
    """Checks both assistant answer and recent tool outputs for completion keywords."""
    if ans:
        ans_upper = ans.upper()
        if any(k in ans_upper for k in COMPLETION_KEYWORDS):
            return True

    # Scan the last 6 messages in history for tool output completions
    for msg in reversed(history[-6:]):
        if msg.get("role") == "tool" and msg.get("content"):
            content_upper = str(msg["content"]).upper()
            if any(k in content_upper for k in COMPLETION_KEYWORDS):
                return True

    return False


def log_turn_to_file(workspace: str, task: str, turn: int, ans: str, status: str = "IN_PROGRESS") -> None:
    """Appends an execution log entry to .agent/task_log.md for workspace auditing."""
    try:
        agent_dir = os.path.join(workspace, ".agent")
        os.makedirs(agent_dir, exist_ok=True)
        log_file = os.path.join(agent_dir, "task_log.md")
        
        mode = "a" if os.path.exists(log_file) else "w"
        with open(log_file, mode, encoding="utf-8") as f:
            if mode == "w":
                f.write(f"# Autonomous Task Execution Log\n**Task:** {task}\n**Started:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n---\n\n")
            f.write(f"### [Turn {turn} - {time.strftime('%H:%M:%S')}] Status: `{status}`\n")
            if ans and ans.strip():
                f.write(f"**Agent Response:**\n{ans.strip()}\n\n")
            f.write("---\n\n")
    except OSError:
        pass


def run_loop(task: str, max_turns: int = 10, task_file: str | None = None, enable_logging: bool = True) -> bool:
    workspace = os.environ.get("AI_WORKSPACE_PATH", os.getcwd())
    
    # Load goal from TASK.md or task_file if direct string not provided
    if not task:
        target_file = task_file or os.path.join(workspace, "TASK.md")
        if os.path.exists(target_file):
            try:
                with open(target_file, "r", encoding="utf-8") as f:
                    task = f.read().strip()
                sys.stderr.write(f"\033[2m[loop] Loaded goal from {os.path.basename(target_file)}\033[0m\n")
            except OSError as e:
                sys.stderr.write(f"\033[1;31m[error] Failed to read spec file: {e}\033[0m\n")
                return False

    if not task:
        sys.stderr.write("\033[1;31m[error] Usage: /task \"<description>\" or create TASK.md in workspace\033[0m\n")
        return False

    disp_dir = workspace.replace(os.path.expanduser("~"), "~")
    sys.stderr.write(f"\n\033[1;36m[loop]\033[0m Starting autonomous execution in \033[1;33m{disp_dir}\033[0m (max {max_turns} turns)\n")
    sys.stderr.write(f"\033[2m:: Goal: {task[:120]}{'...' if len(task) > 120 else ''}\033[0m\n\n")

    history: list[dict[str, Any]] = [
        {
            "role": "system", 
            "content": (
                f"You are an autonomous developer agent at {workspace}.\n"
                "Execute the goal step-by-step using available workspace tools.\n"
                "Test and verify changes as you progress.\n"
                "When the goal is fully achieved and verified, output 'TASK COMPLETE' on a line by itself."
            )
        },
        {"role": "user", "content": f"### AUTONOMOUS GOAL:\n{task}"}
    ]

    turn = 0
    stagnation_count = 0
    last_ans = ""

    try:
        while turn < max_turns:
            turn += 1
            sys.stderr.write(f"\033[1;33m[loop turn {turn}/{max_turns}]\033[0m\n")

            # Keep context trimmed to prevent context window overflow
            history = core.prune_history(history)

            # Stream turn execution
            ans = core.stream_response(history, prefix="Agent:", show_stats=True, is_agent=True)

            if ans is None:
                sys.stderr.write("\033[1;31m[error] API request failed or operation interrupted.\033[0m\n")
                if enable_logging:
                    log_turn_to_file(workspace, task, turn, "API Error / Interrupted", status="FAILED")
                return False

            # Append assistant response if non-empty
            if ans:
                history.append({"role": "assistant", "content": ans})

            if enable_logging:
                log_turn_to_file(workspace, task, turn, ans or "(Tool execution)", status="IN_PROGRESS")

            # Check for completion (either in text or tool outputs)
            if is_task_complete(ans, history):
                sys.stderr.write(f"\n\033[1;32m✔ [ok] Task completed successfully in {turn} turn(s)!\033[0m\n\n")
                if enable_logging:
                    log_turn_to_file(workspace, task, turn, ans or "Task finished.", status="COMPLETED")
                return True

            # Stagnation & Loop Detection
            if ans == last_ans and ans:
                stagnation_count += 1
                if stagnation_count >= 2:
                    sys.stderr.write("\033[1;33m[loop] Stagnation detected. Injecting course-correction prompt...\033[0m\n")
                    history.append({
                        "role": "user", 
                        "content": "Notice: Previous approach produced duplicate results. Please try an alternative tool or strategy to achieve the goal, or run verification."
                    })
                    stagnation_count = 0
                    continue
            else:
                stagnation_count = 0
                last_ans = ans

            # Standard prompt continuation for next turn
            history.append({
                "role": "user", 
                "content": "Continue executing remaining steps toward the goal. Run verification if needed, and output 'TASK COMPLETE' on its own line when finished."
            })

        # Max turns reached without completion
        sys.stderr.write(f"\n\033[1;33m▲ [warning] Loop limit reached ({max_turns} turns) without explicit completion.\033[0m\n\n")
        if enable_logging:
            log_turn_to_file(workspace, task, turn, "Max turns reached.", status="MAX_TURNS_REACHED")
        return False

    except KeyboardInterrupt:
        sys.stderr.write("\n\033[1;33m[sys] Loop execution interrupted by user.\033[0m\n\n")
        if enable_logging:
            log_turn_to_file(workspace, task, turn, "Interrupted by user.", status="INTERRUPTED")
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Ralph Autonomous Loop Engine")
    parser.add_argument("task", nargs="?", default="", help="Goal description for the autonomous loop")
    parser.add_argument("-n", "--turns", type=int, default=10, help="Maximum turns allowed (default: 10)")
    parser.add_argument("-f", "--file", type=str, default=None, help="Path to spec file (default: TASK.md)")
    parser.add_argument("--no-log", action="store_true", help="Disable audit logging to .agent/task_log.md")

    args = parser.parse_args()
    success = run_loop(args.task, max_turns=args.turns, task_file=args.file, enable_logging=not args.no_log)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
