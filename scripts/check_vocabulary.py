#!/usr/bin/env python3
"""Mechanical vocabulary check of a text: banned names, and on request a definitions table."""

from __future__ import annotations

import argparse
import functools
import json
import re
import sys
from pathlib import Path

PROJECT_REGISTRY_NAME = "project-vocabulary.json"
SHARED_REGISTRY_KEY = "shared_registry"
EMPTY_PROJECT_REGISTRY: dict = {"version": 1, "terms": []}

DEFINITIONS_HEADING_RE = re.compile(
    r"^##\s+Definitions\b", re.MULTILINE | re.IGNORECASE
)
LATEX_DEFINITIONS_HEADING_RE = re.compile(
    r"^[ \t]*\\section\*?\s*\{\s*Definitions\s*\}",
    re.MULTILINE | re.IGNORECASE,
)
LATEX_SECTION_HEADING_RE = re.compile(
    r"^[ \t]*\\section\*?\s*\{", re.MULTILINE
)
LATEX_LONGTABLE_BEGIN_RE = re.compile(
    r"\\begin\s*\{longtable\}[^\n]*(?:\n|$)", re.IGNORECASE
)
LATEX_LONGTABLE_END_RE = re.compile(
    r"\\end\s*\{longtable\}", re.IGNORECASE
)
LATEX_ENV_RE = re.compile(
    r"\\(?P<kind>begin|end)\s*\{(?P<name>[^{}]+)\}"
)
LATEX_ROW_PREFIX_RE = re.compile(
    r"^(?:\s*\\(?:hline|toprule|midrule|bottomrule|"
    r"endfirsthead|endhead|endfoot|endlastfoot)\b)*\s*"
)
REGISTRY_CITE_RE = re.compile(
    r"[\w-]+-vocabulary\b",
    re.IGNORECASE,
)


def _effective_allowed_names(entry: dict) -> list[str]:
    term = entry["term"]
    names = entry.get("allowed_names")
    if names is None:
        return [term]
    return list(names)


@functools.lru_cache(maxsize=None)
def _word_boundary_pattern(phrase: str, *, path_boundary: bool = True) -> re.Pattern[str]:
    # A space in a registry phrase also matches a hyphen, a LaTeX tie, or a line
    # break, so ``effective-phase-bias change`` is read as ``effective phase bias``.
    words = [re.escape(w) for w in phrase.split()]
    body = r"(?:\s+|\s*-\s*|~)".join(words)
    edge = r"[\w/]" if path_boundary else r"\w"
    return re.compile(rf"(?<!{edge}){body}(?!{edge})", re.IGNORECASE)


def _find_spans(
    text: str, phrase: str, *, path_boundary: bool = True
) -> list[tuple[int, int]]:
    pat = _word_boundary_pattern(phrase, path_boundary=path_boundary)
    return [(m.start(), m.end()) for m in pat.finditer(text)]


def _span_inside(inner: tuple[int, int], outer: tuple[int, int]) -> bool:
    return inner[0] >= outer[0] and inner[1] <= outer[1]


def _allowed_spans(text: str, entries: list[dict]) -> list[tuple[int, int]]:
    """Return spans occupied by any effective allowed name in ``entries``.

    ``/`` is not a boundary here, so an allowed name inside a file path
    (``.../Effective phase bias of a NIL.tex``) still shields its words.
    """
    spans: list[tuple[int, int]] = []
    for entry in entries:
        try:
            names = _effective_allowed_names(entry)
        except KeyError:
            continue
        for name in names:
            if isinstance(name, str) and name:
                spans.extend(_find_spans(text, name, path_boundary=False))
    return spans


SENTENCE_END_RE = re.compile(r"(?<=[.;!?])\s+")
REJECTION_CUE_RE = re.compile(
    r"\b(?:not|never|distinct\s+from|rather\s+than|instead\s+of|unlike|"
    r"as\s+opposed\s+to|avoid(?:s|ed)?)\b",
    re.IGNORECASE,
)
QUOTE_PAIRS = (("'", "'"), ('"', '"'), ("`", "`"), ("``", "''"), ("‘", "’"), ("“", "”"))


def _sentence_around(text: str, start: int, end: int) -> str:
    """Return the sentence of ``text`` that contains the span ``[start, end)``."""
    left = 0
    for m in SENTENCE_END_RE.finditer(text, 0, start):
        left = m.end()
    m = SENTENCE_END_RE.search(text, end)
    right = m.start() if m else len(text)
    return text[left:right]


def _is_quoted(text: str, start: int, end: int) -> bool:
    return any(
        text[max(0, start - len(o)) : start] == o and text[end : end + len(c)] == c
        for o, c in QUOTE_PAIRS
    )


def _is_rejecting_mention(text: str, start: int, end: int) -> bool:
    """True when a banned label is named in order to reject it, not used as a name.

    Examples: ``never 'visits'``, ``This is not Kirchhoff's voltage law``,
    ``distinct from the bare avoided term phase bias``.
    """
    if _is_quoted(text, start, end):
        return True
    sentence = _sentence_around(text, start, end)
    return bool(REJECTION_CUE_RE.search(sentence))


def _iter_term_entries(terms: object) -> list[dict]:
    if not isinstance(terms, list):
        return []
    return [e for e in terms if isinstance(e, dict) and "term" in e]


def _validate_meanings_closed(
    meaning_terms: list[dict],
    avoid_terms: list[dict],
    *,
    label: str,
) -> list[str]:
    """Reject avoid_names that appear in standard_meaning (closed glosses).

    Two uses are not violations:

    * the banned string lies inside an allowed name (``phase bias`` inside
      ``effective phase bias``);
    * the gloss names one of its *own* avoid_names to reject it — the label is
      quoted, or its sentence carries a rejection cue (``not``, ``never``,
      ``distinct from``, ...). A gloss documents what its term replaces; it
      must still not mention another entry's avoid_names.
    """
    errs: list[str] = []
    allowed_catalog = meaning_terms + [
        e for e in avoid_terms if e not in meaning_terms
    ]
    avoid_pairs: list[tuple[str, str]] = []
    for entry in avoid_terms:
        owner = entry.get("term", "")
        for name in entry.get("avoid_names") or []:
            if isinstance(name, str) and name:
                avoid_pairs.append((name, owner))
    for entry in meaning_terms:
        meaning = entry.get("standard_meaning")
        if not isinstance(meaning, str):
            continue
        term = entry.get("term", "")
        # Excused spans shield everything nested in them: bare ``bias`` inside
        # an excused mention of ``phase bias`` is part of that mention.
        excused = _allowed_spans(meaning, allowed_catalog)
        excused.extend(
            (start, end)
            for avoid_name, owner in avoid_pairs
            if owner == term
            for start, end in _find_spans(meaning, avoid_name)
            if _is_rejecting_mention(meaning, start, end)
        )
        for avoid_name, owner in avoid_pairs:
            for start, end in _find_spans(meaning, avoid_name):
                if any(_span_inside((start, end), span) for span in excused):
                    continue
                errs.append(
                    f"{label} term {term!r} standard_meaning uses "
                    f"avoid_names {avoid_name!r} — use {owner!r}"
                )
    return errs


def _validate_registry(data: object, *, label: str = "registry") -> list[str]:
    errs: list[str] = []
    if not isinstance(data, dict):
        return [f"{label} root must be an object"]
    if data.get("version") != 1:
        errs.append(f"{label} version must be 1")
    if not isinstance(data.get(SHARED_REGISTRY_KEY, ""), str):
        errs.append(f"{label} {SHARED_REGISTRY_KEY} must be a string")
    terms = data.get("terms")
    if not isinstance(terms, list):
        return errs + [f"{label} terms must be an array"]
    seen_terms: set[str] = set()
    seen_avoid: dict[str, str] = {}
    for i, entry in enumerate(terms):
        if not isinstance(entry, dict):
            errs.append(f"{label} terms[{i}] must be an object")
            continue
        if "not_for" in entry:
            errs.append(
                f"{label} terms[{i}] uses deprecated key 'not_for'; use avoid_names"
            )
        for key in ("term", "standard_meaning"):
            if key not in entry:
                errs.append(f"{label} terms[{i}] missing {key!r}")
        if "term" in entry:
            t = entry["term"]
            if t in seen_terms:
                errs.append(f"{label} duplicate term: {t!r}")
            seen_terms.add(t)
        allowed = _effective_allowed_names(entry) if "term" in entry else []
        if entry.get("allowed_names") is not None:
            raw = entry["allowed_names"]
            if not isinstance(raw, list) or not raw:
                errs.append(
                    f"{label} terms[{i}].allowed_names must be a non-empty array"
                )
            elif entry.get("term") not in raw:
                errs.append(
                    f"{label} terms[{i}].allowed_names must include term "
                    f"{entry.get('term')!r}"
                )
        avoid = entry.get("avoid_names")
        if avoid is not None:
            if not isinstance(avoid, list) or not avoid:
                errs.append(
                    f"{label} terms[{i}].avoid_names must be a non-empty array "
                    "or omitted"
                )
            else:
                allowed_lower = {a.lower() for a in allowed}
                for name in avoid:
                    if name.lower() in allowed_lower:
                        errs.append(
                            f"{label} terms[{i}].avoid_names {name!r} overlaps "
                            "allowed_names"
                        )
                    key = name.lower()
                    owner = seen_avoid.get(key)
                    if owner and owner != entry.get("term"):
                        errs.append(
                            f"{label} avoid_names {name!r} duplicated across "
                            f"{owner!r} and {entry.get('term')!r}"
                        )
                    seen_avoid[key] = entry.get("term", "")
    if isinstance(terms, list):
        well_formed = _iter_term_entries(terms)
        errs.extend(
            _validate_meanings_closed(
                well_formed, well_formed, label=label
            )
        )
    return errs


def _validate_cross_registries(
    left: dict, right: dict, *, left_label: str, right_label: str
) -> list[str]:
    errs: list[str] = []
    left_terms = {
        e["term"]: left_label
        for e in left.get("terms", [])
        if isinstance(e, dict) and "term" in e
    }
    right_terms = {
        e["term"]: right_label
        for e in right.get("terms", [])
        if isinstance(e, dict) and "term" in e
    }
    for term in sorted(set(left_terms) & set(right_terms)):
        errs.append(
            f"duplicate term {term!r} in {left_label} and {right_label}"
        )

    avoid_owner: dict[str, tuple[str, str]] = {}
    for registry, label in ((left, left_label), (right, right_label)):
        for entry in registry.get("terms", []):
            if not isinstance(entry, dict):
                continue
            term = entry.get("term", "")
            for name in entry.get("avoid_names") or []:
                key = name.lower()
                owner = avoid_owner.get(key)
                if owner and owner[0] != term:
                    errs.append(
                        f"avoid_names {name!r} duplicated across "
                        f"{owner[1]} ({owner[0]!r}) and {label} ({term!r})"
                    )
                avoid_owner[key] = (term, label)
    left_entries = _iter_term_entries(left.get("terms"))
    right_entries = _iter_term_entries(right.get("terms"))
    merged_entries = left_entries + right_entries
    errs.extend(
        _validate_meanings_closed(
            right_entries,
            merged_entries,
            label=right_label,
        )
    )
    return errs


def _load_registry(path: Path, *, label: str) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    errs = _validate_registry(data, label=label)
    if errs:
        raise ValueError("; ".join(errs))
    return data


def _shared_registry_path(project: dict, project_path: Path | None) -> Path | None:
    """Return the shared registry that a project registry names, if any."""
    name = project.get(SHARED_REGISTRY_KEY)
    if not name:
        return None
    path = Path(name).expanduser()
    if path.is_absolute() or project_path is None:
        return path
    return project_path.parent / path


def load_registries(
    project_path: Path | None, shared_path: Path | None = None
) -> dict:
    """Load, validate, and merge a project registry and its shared registry.

    ``shared_path`` overrides the ``shared_registry`` that the project registry
    names. A shared registry that is missing is reported and left out, so a
    project still works on a machine that does not have it. Invalid registries
    raise ``ValueError``.
    """
    project = dict(EMPTY_PROJECT_REGISTRY)
    project_label = PROJECT_REGISTRY_NAME
    if project_path is not None:
        project_label = project_path.name
        project = _load_registry(project_path, label=project_label)
    shared = dict(EMPTY_PROJECT_REGISTRY)
    shared_label = "shared registry"
    shared_path = shared_path or _shared_registry_path(project, project_path)
    if shared_path is not None:
        if shared_path.is_file():
            shared_label = shared_path.name
            shared = _load_registry(shared_path, label=shared_label)
        else:
            print(
                f"shared registry missing: {shared_path} (using project terms only)",
                file=sys.stderr,
            )
    errs = _validate_cross_registries(
        shared, project, left_label=shared_label, right_label=project_label
    )
    if errs:
        raise ValueError("; ".join(errs))
    return _annotated_merge(shared, project, shared_label, project_label)


def _find_project_registry(start: Path) -> Path | None:
    for parent in [start, *start.parents]:
        candidate = parent / PROJECT_REGISTRY_NAME
        if candidate.is_file():
            return candidate
    return None


def _definitions_section(text: str) -> str:
    m = DEFINITIONS_HEADING_RE.search(text)
    if m:
        rest = text[m.end() :]
        nxt = re.search(r"^##\s+", rest, re.MULTILINE)
        return rest[: nxt.start()] if nxt else rest

    m = LATEX_DEFINITIONS_HEADING_RE.search(text)
    if not m:
        return ""
    rest = text[m.end() :]
    nxt = LATEX_SECTION_HEADING_RE.search(rest)
    return rest[: nxt.start()] if nxt else rest


def _is_escaped(text: str, index: int) -> bool:
    backslashes = 0
    index -= 1
    while index >= 0 and text[index] == "\\":
        backslashes += 1
        index -= 1
    return backslashes % 2 == 1


def _update_environment_stack(stack: list[str], match: re.Match[str]) -> None:
    kind = match.group("kind")
    name = match.group("name").strip().lower()
    if kind == "begin":
        stack.append(name)
    elif stack and stack[-1] == name:
        stack.pop()


def _normalize_latex_definition_term(first: str) -> str:
    first = LATEX_ROW_PREFIX_RE.sub("", first).strip()
    first = first.replace(r"\&", "&")
    first = first.replace("---", "—").replace("--", "–")
    return re.sub(r"\s+", " ", first)


def _latex_longtable_first_cells(table_body: str) -> list[str]:
    """Read first cells while respecting nested LaTeX alignment environments."""
    cells: list[str] = []
    first: list[str] = []
    found_separator = False
    environments: list[str] = []
    i = 0
    while i < len(table_body):
        if table_body[i] == "%" and not _is_escaped(table_body, i):
            newline = table_body.find("\n", i)
            if newline == -1:
                break
            if not found_separator:
                first.append("\n")
            i = newline + 1
            continue

        environment = LATEX_ENV_RE.match(table_body, i)
        if environment:
            if not found_separator:
                first.append(environment.group(0))
            _update_environment_stack(environments, environment)
            i = environment.end()
            continue

        if table_body.startswith("\\\\", i) and not environments:
            cell = _normalize_latex_definition_term("".join(first))
            if found_separator and cell and cell.lower() != "term":
                cells.append(cell)
            first = []
            found_separator = False
            i += 2
            continue

        if (
            table_body[i] == "&"
            and not _is_escaped(table_body, i)
            and not environments
        ):
            found_separator = True
            i += 1
            continue

        if not found_separator:
            first.append(table_body[i])
        i += 1
    return cells


def _latex_definition_terms(definitions: str) -> list[str]:
    """Return first-column text from longtables in a LaTeX Definitions section."""
    terms: list[str] = []
    offset = 0
    while True:
        begin = LATEX_LONGTABLE_BEGIN_RE.search(definitions, offset)
        if not begin:
            break
        end = LATEX_LONGTABLE_END_RE.search(definitions, begin.end())
        if not end:
            break
        body = definitions[begin.end() : end.start()]
        terms.extend(_latex_longtable_first_cells(body))
        offset = end.end()
    return terms


def _term_in_definitions(definitions: str, term: str) -> bool:
    if not definitions:
        return False
    for line in definitions.splitlines():
        if not line.strip().startswith("|"):
            continue
        if re.match(r"^\|\s*[-:]+", line):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not cells:
            continue
        first = cells[0].strip("*").strip()
        if term.lower() in first.lower() or first.lower() in term.lower():
            return True
    for first in _latex_definition_terms(definitions):
        if term.lower() in first.lower() or first.lower() in term.lower():
            return True
    return False


def _line_number(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def _mask_latex_comments(text: str) -> str:
    """Blank every LaTeX comment, keeping offsets and line numbers.

    A comment is not read by the reader of the compiled text; in a manuscript
    it often names a rejected label to record a ruling (``not 'X'``), which is
    not a use of that label.
    """
    out = list(text)
    i = 0
    while i < len(text):
        if text[i] == "%" and not _is_escaped(text, i):
            end = text.find("\n", i)
            end = len(text) if end < 0 else end
            out[i:end] = " " * (end - i)
            i = end
        i += 1
    return "".join(out)


# a brace group without spaces that holds ':' or '/': a label, a reference, a
# citation key, or a file path (``{fig:cat-code-ideal-tree}``, ``{figs/a.pdf}``)
LATEX_KEY_GROUP_RE = re.compile(r"\{([^{}\s]*[:/][^{}\s]*)\}")


def mask_latex(text: str) -> str:
    """Blank what the reader of compiled LaTeX does not read as words.

    Comments and key-like brace groups (labels, references, file paths) are
    replaced by spaces of the same length, so offsets and line numbers hold.
    """
    text = _mask_latex_comments(text)
    return LATEX_KEY_GROUP_RE.sub(
        lambda m: "{" + " " * len(m.group(1)) + "}", text
    )


def avoid_hits(text: str, terms: list[dict]) -> list[tuple[int, int, str, str, str]]:
    """Uses of an ``avoid_names`` string in ``text``.

    A hit inside an allowed name is not a use (``phase bias`` inside
    ``effective phase bias``), and at each spot only the longest banned phrase
    is reported: ``phase bias`` is one hit, not also one for the bare ``bias``.

    Returns ``(start, end, avoid_name, term, source)`` tuples in text order.
    """
    allowed_spans = _allowed_spans(text, _iter_term_entries(terms))
    hits: list[tuple[int, int, str, str, str]] = []
    for entry in _iter_term_entries(terms):
        for avoid_name in entry.get("avoid_names") or []:
            for start, end in _find_spans(text, avoid_name):
                if any(_span_inside((start, end), span) for span in allowed_spans):
                    continue
                hits.append(
                    (start, end, avoid_name, entry["term"],
                     entry.get("_source", "registry"))
                )
    return [
        h for h in sorted(hits)
        if not any(
            (s, e) != (h[0], h[1]) and _span_inside((h[0], h[1]), (s, e))
            for s, e, *_ in hits
        )
    ]


def check_file(
    note_path: Path, registry: dict, *, require_definitions: bool = False
) -> tuple[int, str, list[str]]:
    """Run the mechanical check on one file.

    The avoid_names scan always runs. ``require_definitions`` adds the coverage check:
    every registered term the file uses needs a row in its Definitions table or
    a citation of the registry. Most papers have no such table.
    """
    text = note_path.read_text(encoding="utf-8")
    # the avoid_names scan reads only what the reader reads
    scan = mask_latex(text) if note_path.suffix == ".tex" else text
    definitions = _definitions_section(text)
    has_registry_cite = bool(
        REGISTRY_CITE_RE.search(definitions)
        or REGISTRY_CITE_RE.search(text[:2000])
    )

    terms = registry.get("terms", [])
    if not terms:
        return 0, "SKIP_MECHANICAL (registry empty)", []

    failures: list[str] = []
    matched: list[tuple[str, str, list[int], str]] = []
    for start, end, avoid_name, term, source in avoid_hits(scan, terms):
        failures.append(
            f'{note_path}: AVOID_NAME: {avoid_name!r} line '
            f'{_line_number(text, start)} — use {term!r} [{source}]'
        )

    if not require_definitions:
        return (1, "FAIL", failures) if failures else (0, "OK", [])

    for entry in terms:
        term = entry["term"]
        source = entry.get("_source", "registry")
        allowed = sorted(_effective_allowed_names(entry), key=len, reverse=True)

        positions: list[int] = []
        hit_name = ""
        for name in allowed:
            pos = [s for s, _ in _find_spans(text, name)]
            if pos:
                positions = pos
                hit_name = name
                break
        if positions:
            matched.append((term, hit_name, positions, source))

    if failures:
        return 1, "FAIL", failures

    if not matched:
        return 0, "SKIP_MECHANICAL (no registry terms in note)", []

    for term, hit_name, positions, source in matched:
        in_defs = _term_in_definitions(definitions, term)
        if not in_defs and not has_registry_cite:
            lines = ", ".join(str(_line_number(text, p)) for p in positions[:5])
            suffix = " ..." if len(positions) > 5 else ""
            failures.append(
                f"{note_path}: term {term!r} (matched {hit_name!r}) "
                f"lines {lines}{suffix} — missing Definitions row or registry cite "
                f"[{source}]"
            )

    if failures:
        return 1, "FAIL", failures
    return 0, "OK", []


def _annotated_merge(
    shared: dict, project: dict, shared_label: str, project_label: str
) -> dict:
    terms: list[dict] = []
    for registry, label in ((shared, shared_label), (project, project_label)):
        for entry in registry.get("terms", []):
            if isinstance(entry, dict):
                tagged = dict(entry)
                tagged["_source"] = label
                terms.append(tagged)
    return {"version": 1, "terms": terms}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--file", "--note", dest="file", type=Path,
        help="Single Markdown or LaTeX file to check",
    )
    parser.add_argument(
        "--root", "--notes-root", dest="root", type=Path,
        help="Check all .md and .tex files under a directory",
    )
    parser.add_argument(
        "--registry",
        type=Path,
        help=f"Shared registry; overrides the {SHARED_REGISTRY_KEY} of the project registry",
    )
    parser.add_argument(
        "--project-registry",
        type=Path,
        help=f"Path to project {PROJECT_REGISTRY_NAME} (default: discover from file path)",
    )
    parser.add_argument(
        "--definitions",
        action="store_true",
        help="Also require a Definitions row or registry citation for every term used",
    )
    parser.add_argument(
        "--avoid-only", action="store_true", help="Run only the avoid_names scan (the default)"
    )
    args = parser.parse_args()

    if not args.file and not args.root:
        parser.error("provide --file or --root")
    definitions = args.definitions and not args.avoid_only

    files: list[Path] = []
    if args.file:
        files.append(args.file.resolve())
    if args.root:
        root = args.root.resolve()
        files.extend(sorted(root.rglob("*.md")))
        if not definitions:
            files.extend(sorted(root.rglob("*.tex")))

    project_path: Path | None = None
    if args.project_registry:
        project_path = args.project_registry.resolve()
        if not project_path.is_file():
            print(
                f"project registry missing: {project_path} (using empty terms)",
                file=sys.stderr,
            )
            project_path = None
    else:
        for path in files:
            project_path = _find_project_registry(path.parent)
            if project_path:
                break
        if project_path is None:
            print(
                f"no {PROJECT_REGISTRY_NAME} discovered (using empty project terms)",
                file=sys.stderr,
            )

    try:
        merged = load_registries(
            project_path, args.registry.resolve() if args.registry else None
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"registry error: {exc}", file=sys.stderr)
        return 1
    print(f"registry: {project_path or '(no project registry)'}, {len(merged['terms'])} terms")

    any_fail = False
    for path in files:
        if not path.is_file():
            print(f"skip missing: {path}", file=sys.stderr)
            continue
        code, status, failures = check_file(
            path, merged, require_definitions=definitions
        )
        print(f"{path}: {status}")
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        if code != 0:
            any_fail = True

    return 1 if any_fail else 0


if __name__ == "__main__":
    sys.exit(main())
