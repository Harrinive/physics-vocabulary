---
name: physics-vocabulary
description: >-
  Keeps the names of a physics project consistent with a JSON registry: each term
  has one meaning, its approved names, and the wrong labels to avoid. Checks a text
  with a script and a reader agent, and renames a term across notes, manuscripts,
  and docstrings together with the registry. Use when checking terminology,
  standardizing names, or when an author says "don't use X, use Y". Code
  identifiers are out of scope.
---

# Physics vocabulary

**Goal:** one object, one name, across a whole project. Reserved names are used for
defined objects, nothing is shortened without approval, and catalogued wrong labels
do not return.

| When | Read |
|------|------|
| **Always** | This file |
| **Running a check or a rename** | [vocabulary-check.md](vocabulary-check.md) |
| **Editing this skill** | [MAINTAINERS.md](MAINTAINERS.md) |

First reply when this skill applies: state the job (check or rename), the target
text or term, and the registry in use.

## The registry

A project keeps `project-vocabulary.json` at its root. Start from
[project-vocabulary.template.json](project-vocabulary.template.json); the format is
[vocabulary.schema.json](vocabulary.schema.json).

| Field | Required | Holds |
|-------|----------|-------|
| `term` | yes | The preferred name |
| `standard_meaning` | yes | What object the name denotes |
| `allowed_names` | no | Approved names, including `term`; by default only `term` |
| `avoid_names` | no | Wrong labels for this object; omit when none is catalogued |

A project may add to a shared registry that holds a field's or a group's common
terms: set the top-level `shared_registry` to its path. The two are merged, and a
term may not appear in both. On a machine without the shared file, the project
registry works alone.

## Using names

- New text uses the `term` or an allowed name. It never uses an `avoid_names` string
  for that object.
- A shortening not listed in `allowed_names` is not approved, even when it is clear.
  If it is wanted, add it.
- "Don't use X, use Y" from the author is a rename: X goes into `avoid_names`, and the
  text and the registry change together.
- The script matches literal phrases and does not inflect them. List both singular
  and plural when both matter.
- A registered word can also be ordinary English, or a banned string can be ordinary
  words that do not name the object. A hit is then a judgment, not a violation.
- A project registry records a choice of names, not a law of the field. A name the
  field uses differently needs a meaning that says so.

## Writing `standard_meaning`

A meaning is read as research prose, so the naming rules hold inside it.

| May use | Must not use |
|---------|--------------|
| Registered names, of this entry or another | Any `avoid_names` string, except its own, named to reject it |
| Words that need no definition | An unregistered name of this project |
| Symbols and ordinary English | An informal alias of a registered object |

If a meaning needs an object without an entry, register that object in the same pass.
State what the name means, not how it was chosen or what it replaced.

## Check

Run after a text is written or substantially rewritten. It has two parts, because each
catches what the other cannot.

1. **Script.** It finds every `avoid_names` string in the text as the reader sees it.
2. **Reader.** A read-only agent finds unlisted shortenings and aliases of registered
   objects.

The physics editing skills run the script on every draft and give the reader's job to
their terminology reviewer.

## Rename

The default scope is the whole project: notes, manuscripts, and docstrings. Update
every match and the registry in one pass. Code identifiers are never renamed: that
breaks imports, and it is a separate decision.

## Anti-patterns

1. **Registry drift:** the text changes and the registry does not.
2. **Arbitrary shortening:** an unlisted part of a registered name stands for it.
3. **Open meaning:** a `standard_meaning` uses a banned label or an unregistered name.
4. **Check skipped:** the script passes and the reader is not run.
5. **Identifier rename:** a rename reaches variables, functions, or dictionary keys.
6. **Duplicate term:** the same `term` sits in the project and the shared registry.

## Related skills

- **physics-paper-principles:** how to choose and introduce a name
  ([names-and-symbols.md](../physics-paper-principles/names-and-symbols.md))
- **physics-paper-editing**, **physics-paper-editing-section:** run the script on
  every draft when this skill is installed; without it the scan is skipped

## Out of scope

- Choosing a name: this skill keeps a name consistent once it is chosen
- Naming in code
