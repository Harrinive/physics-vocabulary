#!/usr/bin/env python3
"""Validate the physics-vocabulary skill layout and its registry template."""

from __future__ import annotations

import json
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent

REQUIRED_FILES = (
    "SKILL.md",
    "README.md",
    "LICENSE",
    "MAINTAINERS.md",
    "vocabulary-check.md",
    "vocabulary.schema.json",
    "project-vocabulary.template.json",
    "scripts/check_vocabulary.py",
)
REQUIRED_IN_SKILL = (
    "project-vocabulary.json",
    "shared_registry",
    "vocabulary-check.md",
    "Writing `standard_meaning`",
    "allowed_names",
    "avoid_names",
)


def _errors() -> list[str]:
    errs = [f"{name} missing" for name in REQUIRED_FILES if not (SKILL_ROOT / name).is_file()]
    if errs:
        return errs

    text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    errs.extend(
        f"SKILL.md missing required phrase: {phrase!r}"
        for phrase in REQUIRED_IN_SKILL
        if phrase not in text
    )
    if "not_for" in text:
        errs.append("SKILL.md must not reference deprecated not_for; use avoid_names")

    sys.path.insert(0, str(SKILL_ROOT / "scripts"))
    try:
        from check_vocabulary import _validate_registry  # noqa: PLC0415
    finally:
        sys.path.pop(0)
    template = json.loads(
        (SKILL_ROOT / "project-vocabulary.template.json").read_text(encoding="utf-8")
    )
    errs.extend(_validate_registry(template, label="template"))
    return errs


def main() -> int:
    errs = _errors()
    if errs:
        print("validate_skill_layout.py: FAILED", file=sys.stderr)
        for e in errs:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print("validate_skill_layout.py: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
