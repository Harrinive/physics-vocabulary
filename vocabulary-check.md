# Running a check or a rename

**For agents:** Start with [SKILL.md](SKILL.md). Open to run a check or a rename.

## Script

From this folder:

```bash
python3 scripts/check_vocabulary.py --file <path> [--project-registry <registry>]
python3 scripts/check_vocabulary.py --root <folder>
```

Without `--project-registry`, the script looks for `project-vocabulary.json` in the
parents of the file. `--file` takes Markdown or LaTeX; `--root` reads every `.md` and
`.tex` file under a folder. `--registry` names a shared registry and overrides the
project's `shared_registry`.

`--definitions` adds a coverage check for projects whose notes carry a definitions
table: every registered term the file uses needs a row, or the file cites the registry.
The table is a Markdown `## Definitions` section, or a LaTeX `\section{Definitions}` with
the terms in the first column of a `longtable`.

| Exit | Status | Meaning |
|------|--------|---------|
| 0 | `OK` | No banned name; with `--definitions`, every term is covered |
| 0 | `SKIP_MECHANICAL` | The registry is empty, or with `--definitions` no term is used |
| 1 | `FAIL` | A banned name, an invalid registry, or a missing definition |

What the scan does:

- Validates the registries first. A duplicate term or a banned name shared across
  entries fails.
- Treats a space, a hyphen, `~`, and a line break alike inside a phrase.
- Ignores a banned string inside an allowed name, and reports only the longest banned
  phrase at each spot.
- In LaTeX, skips comments and key-like brace groups (labels, references, file paths),
  so it reads what the reader reads.

A hit in ordinary words that do not name the object is a judgment for the reader, not a
reason to change the text.

## Reader

Run once per file after the script passes, read-only, even when no term matched. Give it
the matched registry entries, and this brief:

```markdown
Read-only vocabulary check. Grade each use of a registered object in the text:
- USE_OK: an allowed name, used for the defined object.
- SHORTENED: means a registered object but uses an unlisted part of its name.
- AVOID_NAME: a listed avoid_names string that names this object.
- NONSTANDARD: refers to a registered object by an unlisted alias.

Only allowed_names are approved; without that field, only the term. If no entry
matches, report undefined project terms and inconsistent names. PASS only if no
SHORTENED or AVOID_NAME remains.

Return: PASS or FAIL, the themes, and line references.
```

On FAIL, fix the text or the registry, then rerun the script and the reader.

## Rename

| Step | Action |
|------|--------|
| 1 | Confirm the new name Y and the old name X. Ask if the meaning is unclear. |
| 2 | Choose the registry: the shared one if the name should hold beyond this project, else the project's. Ask unless the author named it or the term already lives in one. |
| 3 | Search the project's notes, manuscripts, and docstrings for X and its related forms. |
| 4 | Change every match. Fix definitions tables and links. Leave code identifiers alone. |
| 5 | In the registry, set `term` to Y and add X to `avoid_names`. Rewrite every touched `standard_meaning` ([SKILL.md](SKILL.md)); register in the same pass any object a meaning needs. |
| 6 | Run the script to confirm that the registry loads and no X remains. |

If the author says the change is for one file only, skip the registry and say that it
now differs.
