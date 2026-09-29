> **Status:** `v0.1-alpha` (Experimental)  
> Built for local Arch Linux environments with `py-agent` and `llama-server`. Expect manual setup and breaking upstream changes.

# DeepSeek Harness (DSH)

Web UI surface for `py-agent` workspaces with automated file operations, thought streams, and terminal execution.

## Prerequisites

1. `dsh` installed globally.
2. A running model server on `http://localhost:8080` (e.g. `llama-server`) or configured provider.

## Setup

1. Create the DSH profile:
```bash
dsh --profile pyagent --from-default-profile web
```

2. Configure `~/.dsh/profiles/pyagent/cordis.patch.yml`:
```yaml
- id: permission
  config:
    defaultPreset: workspace-write
    presets:
      read-only:
        sandbox: read-only
        approval: ask
      workspace-write:
        sandbox: workspace-write
        approval: ask
      danger-full-access:
        sandbox: danger-full-access
        approval: never

- id: system-prompt
  config:
    personaPrefix: >-
      ROLE: Py-Agent Autonomous Software Engineer.

      DIRECTIVES:
      - GREETINGS: For casual greetings ("hi", "hello"), reply in 1 concise sentence without calling tools.
      - TOOL EXECUTION: Emit tool calls directly. Never output introductory commentary or conversational filler.
      - FILE OPERATIONS: Write files directly to the workspace using available tools. Never output raw code blocks in chat when asked to implement code.
      - CLOSED-LOOP EXECUTION: Complete the full engineering loop: inspect -> write/edit -> verify. Never halt after only writing code without running tests.
      - ANTI-LOOP: If a command returns an error, analyze stderr and change strategy immediately.
      - PATHS: Always use relative workspace paths.

      HALT:
      When tests pass or the requested objective is fully verified, stop immediately with:
      ✓ Task complete: <10-word summary>
```

3. Make launcher executable:
```bash
chmod +x ~/.config/py-agent/plugins/dsh/run-dsh.sh
```

## Launch

1. Start your model server (e.g. `llama-server`).
2. Initialize or enter a workspace:
```bash
ai init <workspace_path>
```
3. Inside the session, type:
```text
/dsh
```

DSH will launch and open `http://127.0.0.1:3080` bound directly to your active project directory.

## Controls

* **Auto-Write:** Sessions default to `workspace-write`.
* **Read-Only Mode:** Click the permission badge at the top of the browser to toggle between `read-only` and `workspace-write` on the fly.
* **Exit:** Pressing `Ctrl+C` in the terminal terminates child workers and frees port 3080 immediately.

