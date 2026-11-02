# Maintaining physics-vocabulary

Read this file before editing `SKILL.md`, the schema, or the scripts.

## Contract

- `SKILL.md` holds what an agent must decide. [vocabulary-check.md](vocabulary-check.md)
  holds how to run a check or a rename.
- The skill ships no terms. A field's terms live in a shared registry outside it.
- `scripts/check_vocabulary.py` is the only scan: `avoid_hits` is used by `check_file`
  and imported by the gate of `physics-paper-editing-section`, and `load_registries`
  is the only way registries are merged. Layers over this skill call it and do not
  copy it.
- The rules of a registry stay in code, not as lists in prose.

## Registry rules that the code enforces

- No duplicate `term` in a registry or across the project and shared registries.
- `allowed_names`, when present, includes `term`.
- `avoid_names` is omitted when empty, and does not overlap `allowed_names`.
- A `standard_meaning` contains no `avoid_names` string, except (a) inside an allowed
  name, or (b) the entry's own label named to reject it: quoted, or in a sentence with
  a rejection cue (`not`, `never`, `distinct from`, `rather than`, `instead of`,
  `unlike`, `avoid`). Rejecting mentions are excused in meanings only, not in a text.
- The legacy key `not_for` is rejected.

## Before finishing an edit

From this folder:

```bash
python3 scripts/validate_skill_layout.py
python3 -m pytest scripts
```

Keep the skill free of a host's tool names and of examples from one project.
