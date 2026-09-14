# Security Policy

## Security Model & Zero-Trust Principles

`Local-Ai Agent` is designed to run locally on user hardware with zero-daemon overhead. Because the agent interacts with local shell execution, workspace files, and system tools, we maintain a **Zero-Trust Security Boundary**:

1. **Confirmation Gates (`/g`):** Potentially destructive operations (file modifications, shell command execution) default to explicit user authorization prompts unless explicitly bypassed by the user.
2. **Workspace Containment:** File tool operations are constrained to the active workspace directory unless explicit out-of-bounds permission is granted.
3. **Local Privacy:** No telemetry, conversation history, or personal API keys are uploaded to centralized analytics servers.

---

## Supported Versions

We actively provide security updates for the following versions:

| Version | Supported |
| :--- | :--- |
| `v0.9.x` (Beta) | :white_check_mark: |
| `< 0.9.0` | :x: |

---

## Reporting a Vulnerability

If you discover a security vulnerability, path traversal flaw, or command injection issue in `py-agent`, **please do not open a public GitHub issue.**

Please report the vulnerability privately via email:

- **Email Contact:** <a href="mailto:&#106;&#53;&#111;&#110;&#114;&#102;&#64;&#103;&#109;&#97;&#105;&#108;&#46;&#99;&#111;&#109;">&#106;&#53;&#111;&#110;&#114;&#102;&#64;&#103;&#109;&#97;&#105;&#108;&#46;&#99;&#111;&#109;</a> (`j5onrf [at] gmail [dot] com`)
- **Subject Requirement:** Please prefix the subject line with **`[github]`** so our automated security triage agent processes it immediately (e.g., `[github] [security] Vulnerability Report`).

Alternatively, submit a private advisory via [GitHub Security Advisories](https://github.com/j5onrf/local-ai/security/advisories/new).

---

## Response Timeline

- **Acknowledgement:** Within **48 hours**.
- **Patch Release:** Target within **7 to 14 days**.
- **Credit:** Recognized in release notes upon publication.
