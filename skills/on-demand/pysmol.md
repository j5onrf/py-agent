# [SKILL] PySmol ---> pysmol, smol, smolagents, codeagent, python-loop, batch-code, in-memory-python, code-first

## Mode: Smolagents-Style CodeAgent (In-Memory Python Orchestrator)

Solve multi-step, multi-file, and data tasks not by ping-ponging individual tool calls, but by writing composable Python scripts executed in the in-memory IPython kernel (`exec_python`).

### 1. Code-First Execution Rules
1. **Batching Over Ping-Pong:**
   - Never make 5 separate tool calls to check 5 files.
   - Write standard Python loops (`for`, `while`, list comprehensions) to inspect directories, search strings, parse JSON, or process data in **one turn**.
2. **Stateful In-Memory Kernel:**
   - Variables, imports, and helper functions defined in one cell **remain alive in memory** across subsequent turns.
   - Store large intermediate datasets in variables rather than dumping raw lines to stdout.
3. **Completion Hook (`final_answer`):**
   - `final_answer()` is a global built-in function—never import it.
   - Call `final_answer(result)` to cleanly signal completion and return the definitive final response.

### 2. In-Kernel SDK Functions
* `read_file(path)` ──► Read text content from workspace.
* `write_file(path, content, overwrite=False)` ──► Write or overwrite a file.
* `edit_file(path, old_str, new_str)` ──► Surgically replace text in a file.
* `list_dir(path=".")` ──► List directory contents as a Python `list[str]`.
* `search_code(pattern, path=".")` ──► Fast regex/text search across workspace files.
* `run_command(cmd)` ──► Execute shell commands and return combined stdout/stderr.
* `final_answer(value)` ──► Signal completion and return the definitive final response.
* `preview(obj)` ──► Safely inspect large DataFrames or lists without overflowing context.
* `delegate(goal)` ──► Spawn an isolated child sub-agent to research a sub-task.
* `memory.search(query)` / `memory.get_facts()` ──► Query workspace fact memory.
* `graph.trace(symbol)` / `graph.snippet(symbol)` ──► Query codebase AST knowledge graph.

### 3. Composition Example
```python
# Scan, inspect, and replace in a single execution turn:
targets = [f for f in list_dir("modules") if f.endswith(".py")]
modified = []
for fname in targets:
    path = f"modules/{fname}"
    content = read_file(path)
    if "OLD_KEY" in content:
        edit_file(path, "OLD_KEY", "NEW_KEY")
        modified.append(fname)

final_answer({"status": "complete", "modified_files": modified, "count": len(modified)})
