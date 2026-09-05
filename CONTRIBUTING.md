# Contributing to Py-Agent

Thank you for your interest in contributing to **Py-Agent**! We welcome contributions of all kinds: bug fixes, new features, new agent skills/profiles, documentation improvements, and local model benchmark reports.

---

## Core Design Principles

When submitting code or features, please keep our core philosophy in mind:

1. **Lightweight:** 0% idle CPU/RAM when not actively running. Standard Python library execution where possible.
2. **Local-First & Private:** Local inference (`llama-server`) and offline fallbacks are always first-class citizens.
3. **Zero-Trust Safety:** Never bypass path-boundary checks or execution confirmation gates.
4. **Token Efficiency:** Prompts, context loaders, and tool outputs must be concise and avoid unnecessary context bloat.

---

## 🛠️ Local Development Setup

### 1. Fork & Clone
```bash
git clone https://github.com/YOUR_USERNAME/local-ai.git
cd local-ai
```

### 2. Install Development Dependencies
On Arch Linux:
```bash
sudo pacman -S python-rich python-requests
yay -S python-sqlite-vec python-textual python-uvloop
```

### 3. Run the Diagnostic Test Suite
Before making any changes, verify that your environment passes all health checks:
```bash
./tools/test-agent
```

---

## 💡 Ways to Contribute

### 1. Adding New Skills (`skills/`)
You can contribute new specialized agent skills:
* Place skills in `skills/<category>/<skill_name>.md`.
* Follow the YAML frontmatter standard with clear system instructions and role constraints.

### 2. Improving Tools (`tools/`)
Tools in `tools/agentic/` or `tools/subsec/` should:
* Be standalone, executable scripts.
* Handle missing dependencies gracefully with helpful error messages.

### 3. Local Model Benchmarks & Presets
Share prompt optimizations or `setup/*.sh` launch scripts for newly released quantized GGUF models.

---

## 🔄 Pull Request Guidelines

1. **Branch Naming:** Use clear branch names:
   * `feat/your-feature-name`
   * `fix/bug-description`
   * `docs/improvement`
2. **Run Tests:** Ensure `./tools/test-agent` passes with no broken paths or failed imports.
3. **Commit Messages:** Follow conventional commit style:
   * `feat: add new NOOA kernel preview method`
   * `fix: prevent race condition in tpm memory compiler`
   * `docs: update roadmap for v1.0.0`
4. **Open a PR:** Describe the changes clearly and link any relevant issues.

---

## 📄 License
By contributing to **Py-Agent**, you agree that your contributions will be licensed under the project's [MODIFIED MIT LICENSE](LICENSE).
