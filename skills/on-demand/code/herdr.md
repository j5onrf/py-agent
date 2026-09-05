# [SKILL] herdr ---> herdr, split, multiplexer, pane, tab, layout
- Role: Active terminal multiplexer coordinator.

## 1. Environment Detection
- If `HERDR_ENV=1` is present in your active environment, you are running inside a Herdr-managed terminal pane and have direct access to the local Herdr socket.
- Under this environment, you can use your `run_command` tool to control the terminal layout, inspect other panes, and coordinate parallel jobs.

## 2. Layout & Execution Commands
- **Split Pane Horizontally (Right):** `run_command` -> `herdr pane split --direction right`
- **Split Pane Vertically (Down):** `run_command` -> `herdr pane split --direction down`
- **Create New Tab:** `run_command` -> `herdr tab create --label "<name>"`
- **Execute Command in Specific Pane:** `run_command` -> `herdr pane run <pane-id> "<command>"`
- **Read Neighboring Pane Output:** `run_command` -> `herdr pane read <pane-id> --source recent-unwrapped`

## 3. Symmetrical Multi-Pane Coordination
- To split a terminal pane and execute a command inside it, you must follow this exact two-step sequence:
  1. First, call `herdr pane split ...` to create the new pane.
  2. The command will return a JSON payload containing the new pane's ID (e.g., `{"result": {"pane": {"pane_id": "w1:p2"}}}`).
  3. Next, use the returned ID to call `herdr pane run <pane-id> "<command>"` to execute the target command inside that specific new pane.
