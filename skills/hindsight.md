---
name: hindsight
description: "Session retrospective and lesson compiler. Audits conversation history to extract durable engineering rules, tool quirks, and architectural decisions into memory (hindsight, lesson, learn, retrospective, postmortem, memory review, remember)."
triggers:
  - hindsight
  - lesson
  - learn
  - retrospective
  - postmortem
  - memory review
  - remember
---
# HINDSIGHT: RETROSPECTIVE & LESSON COMPILER

Review this session's conversation history, extract durable engineering rules and workflow fixes, and persist them to memory.

## Evaluation Filter (What to Save):
- **Durable Lessons (SAVE):** Root cause fixes, tool quirks, specific build/run commands settled with the user (e.g. "Use ./scripts/app-ctl, not systemctl"), or architectural constraints.
- **Ephemeral Noise (DISCARD):** Simple typos, routine file listings, one-off temporary scripts.

## Action Directive:
For each genuine durable lesson identified:
- Call `save_memory(title="<short-topic-slug>", content="<Concise, actionable rule (1-2 sentences)>")`.
- Do NOT construct raw file paths with colons or slashes; `save_memory` handles the file creation and YAML frontmatter automatically.

## Clean Exit:
If no durable rules or corrections occurred, conclude with:
`✓ Hindsight: No durable lessons required; session was nominal.`
