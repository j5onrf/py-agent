# Py-Agent Skills Architecture

Modular personas, on-demand behaviors, system directives, and prompt harnesses.

---

### Directory Map

```text
skills/
├── on-demand/   ──► In-chat loadable skills (/s & /skill). Stack up to 3.
│   ├── chat/          Conversational styles (casual, friendly).
│   ├── code/          Senior dev behaviors (ponytail, herdr).
│   ├── omarchy/       Hyprland, theming, crash diagnosis, hooks.
│   ├── personality/   Flavor modes (caveman, pirate).
│   └── hindsight.md   Session retrospective & memory compiler.
│
├── profiles/    ──► Base workspace identities for 'ai init' (turn-0 prompts).
│   ├── custom/        Custom models (sysadmin, lfm2, q2b, base).
│   ├── claude/        Official Claude Systems Engineer.
│   ├── hermes/        Nous Hermes Agent.
│   └── pi/            Pi Agent System.
│
├── system/      ──► Rulebooks for tools/agentic/system/ background scripts.
│   ├── aur-audit.md           Zero-trust PKGBUILD auditing.
│   ├── mysys.md               Host hardware & kernel blueprint.
│   ├── security-audit.md      Privilege & network surface evaluation.
│   ├── system-optimizer.md    eBPF, CPU governor & ZRAM tuning.
│   └── update-inspector.md    Pacnew & rolling upgrade risk triage.
│
└── meta/        ──► Reasoning harnesses & prompt engineering.
    ├── brainstorm.md, thinking.md, follow-up.md
    └── prompt/        Visual prompt generation tools.
```

---

### Quick Reference

| Action | Command / Location | Behavior |
|---|---|---|
| **Browse / Search Skills** | `/s` or `/skill` | Opens live fuzzy TUI selector across `on-demand/`. |
| **Load Skill** | `/s <name>` *(e.g. `/s hindsight`)* | Stacks skill into active system prompt (max 3). |
| **One-Shot Run** | `/s <name> <prompt>` | Loads skill and executes query in single turn. |
| **Unload Skills** | `/s off` (or `/s clear`) | Reverts to base workspace profile. |
| **Select Workspace Profile** | `ai init <dir>` | Selects base profile from `profiles/` with toggle auto-sync. |
| **Dynamic Context Tool** | Registered in `ai-context.md` | Ephemeral single-turn context injection via `cat`. |

---

### Setting Up Workspace Shortcuts

To launch any workspace instantly from your shell using short trigger words, register it in `~/.config/py-agent/ai-context.md` under **Section 2**:

```properties
## Workspaces

ai init ~/.config/py-agent/projects/my-app ---> my-app, mapp
ai init ~/projects/my-app ---> my-app, mapp
```

* **Usage**: Typing `sys-ops` or `my-app` anywhere in your terminal automatically teleports to the directory and boots the configured workspace agent.

