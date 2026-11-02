# Physics vocabulary skill

Keeps the names of a physics project consistent. A JSON registry gives each term its
meaning, its approved names, and the wrong labels to avoid. `scripts/check_vocabulary.py`
finds those labels in Markdown and LaTeX, as the reader sees the text, and a read-only
agent finds unlisted shortenings. A rename changes the text and the registry together.
Start with [SKILL.md](SKILL.md).

## Install

Clone it next to its siblings, under `~/.agents/skills/` or the matching folder of
your host:

```bash
git clone https://github.com/Harrinive/physics-vocabulary.git ~/.agents/skills/physics-vocabulary
```

It works alone and needs only `python3`. Installed next to
[physics-paper-editing](https://github.com/Harrinive/physics-paper-editing) and
[physics-paper-editing-section](https://github.com/Harrinive/physics-paper-editing-section),
it runs on every draft of a project that has a `project-vocabulary.json`.

## Supported hosts

The skill follows the [Agent Skills specification](https://agentskills.io/specification)
and is designed for Cursor, OpenAI Codex, and Claude Code. It contains no
host-specific instructions.
