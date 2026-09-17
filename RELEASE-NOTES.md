<div align="center">
**New in v0.9.9.31:** Established a **Dual-Mode Tool Architecture** recognizing that Sub-27B models require deterministic native tools (`SMOL_TOOLS`) for reliable file operations rather than raw scripting; pruned native tools to 6 core functions (preserving `delegate()` strictly for `/py`); added 1-shot **`/hs` (`/hindsight`)** retrospective session memory audits; compressed the entire profile suite into machine-dense directives (~240t–320t); and added `Esc`/`←` back-navigation to the `ai init` selector.
</div>
<br>
<div align="center">
**New in v0.9.9.30:** Added minimal **KV Cache Tracking** (`cch: X%`) across local `llama-server` and cloud backends; streamlined `ipython_mode` (`/py`) to a **Single-Tool Architecture** slashing schema overhead from ~880t down to ~80t; added dynamic **Tools Inspection** in `ai init` (`ipython`, `native json`, `index-map`); fixed trailing SSE usage packet capture; and added an interactive **Project Creator** (`tools/new-project` / `newp`).
</div>
<br>
<h2 align="center">Release Notes</h2>
<div align="center">
**New in v0.9.9.29:** Introduced **Adaptive Context Scaling** with dynamic line ceilings (250 to 4,000 lines) and proportional scratchpad offloading across 8k–128k context windows; added interactive **Context Budget Presets** (`AI_MAX_TOKENS`) in `model select`; consolidated `agent_usage.py` with unified speed tracking (removed `speed_test.py`); hardened `ai-hook.sh` with portable `sed` and safe tilde expansion; and optimized `ai-agent.py` with read-only SQLite URIs and precompiled regexes.
</div>
<br>
<div align="center">
**New in v0.9.9.28:** Updated **CLI structure standard** with copy-safe 4-space indented tool outputs, introduced **`/calm`** mode with an animated sailboat progress indicator, context capacity ocean gauge, elapsed execution timer, and completion marker (`\___/⚓`) with muted tool diffs; dynamic in-memory profile token weight calculation in `ai init` (`~380t` to `~1.2kt`); conversational greeting guards for small models; and automatic startup pruning for orphaned session locks across window manager exits.
</div>
<br>
<div align="center">
**New in v0.9.9.27:** Production-hardened **`/adp`** small-model adapter architecture (sub-27B opt-in), 7-challenge `eval-stack` benchmark suite with turn-efficiency tracking, zero-I/O local spend bypass, and clean `projects/.database/` session isolation.
</div>
<br>
<div align="center">
**New in v0.9.9.25:** Replaced legacy TPM with **Open Knowledge Format (OKF)** persistent memory (`.agent/memory/*.md`). Features Git-native Markdown directives with YAML frontmatter, instant `/mem save` & `/mem list` commands, 0ms post-turn background overhead, and complete `/m` (Map), `/mem` (Memory), toggle independence.
</div>
<br>
<div align="center">
**New in v0.9.9.24:** Added first-class support for **InclusionAI Ling-3.0-tiny** (7.9B MoE with 1.3B active compute). Achieved a perfect **7/7 (100%)** on the expanded `eval-stack` agentic benchmark. Includes the optimized `custom/lingtiny` profile and on-demand self-healing tool parser (`/adp`).
</div>
<br>
<div align="center">
**New in v0.9.9.20:** Added first-class support for **MiniCPM5-2B** powered by the dedicated **DSpark speculative decoding engine** (`draft-dspark`). Includes an optimized sub-27B agent profile (`custom/minicpm`), automated sandbox command self-healing in `agent_adapters`.
</div>
<br>
<div align="center">
**New in v0.9.9.19:** Integrated **Hugging Face `smolagents`** code-first execution into the persistent kernel (`/py`). Models can now batch multi-step tasks across files using native Python loops, cleanly signal completion with `final_answer()`, and execute safely under a 30-second `SIGALRM` runaway loop breaker.
</div>

