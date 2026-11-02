r"""Tests of ``check_vocabulary.py``: the scan, the registry rules, and the merge.

Run with ``python3 -m pytest`` from this folder.
"""

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

import check_vocabulary as cv

FIELD = {
    "term": "external magnetic field",
    "standard_meaning": "The field applied from outside the sample.",
    "allowed_names": ["external magnetic field", "applied field"],
    "avoid_names": ["bias", "magnetic bias"],
}
RATE = {"term": "decay rate", "standard_meaning": "The rate of population loss."}


def registry(*terms, **top):
    """Return a registry with the given entries."""
    return {"version": 1, "terms": list(terms), **top}


def spans(text, *terms):
    """Return the banned names found in ``text``."""
    return [hit[2] for hit in cv.avoid_hits(text, list(terms))]


class TestScan(unittest.TestCase):
    """What counts as a use of a banned name."""

    def test_finds_a_banned_name(self):
        """A plain use is a hit, whatever its case."""
        self.assertEqual(spans("The Bias is large.", FIELD), ["bias"])

    def test_separators_are_alike(self):
        """A hyphen, a tie, and a line break read as the space of the phrase."""
        for text in ("magnetic-bias", "magnetic~bias", "magnetic\nbias"):
            self.assertEqual(spans(text, FIELD), ["magnetic bias"], text)

    def test_longest_phrase_only(self):
        """A long phrase is one hit, not also one for the word inside it."""
        self.assertEqual(spans("the magnetic bias", FIELD), ["magnetic bias"])

    def test_allowed_name_shields_a_banned_word(self):
        """A banned word inside an allowed name is not a use."""
        entry = dict(FIELD, allowed_names=["external magnetic field", "bias field"])
        self.assertEqual(spans("the bias field", entry), [])

    def test_word_boundary(self):
        """A banned word inside a longer word is not a use."""
        self.assertEqual(spans("biased and unbiased", FIELD), [])

    def test_latex_mask(self):
        """Comments and keys are not read; offsets and lines hold."""
        text = "a % the bias\n\\ref{fig:bias} \\% bias\n"
        masked = cv.mask_latex(text)
        self.assertEqual(len(masked), len(text))
        self.assertEqual(masked.count("\n"), 2)
        self.assertEqual(spans(masked, FIELD), ["bias"])


class TestRegistryRules(unittest.TestCase):
    """What a registry may not contain."""

    def errors(self, *terms):
        """Return the validation errors of a registry."""
        return cv._validate_registry(registry(*terms))

    def test_valid(self):
        """A well-formed registry has no errors."""
        self.assertEqual(self.errors(FIELD, RATE), [])

    def test_duplicate_term(self):
        """A term appears once."""
        self.assertIn("duplicate term", " ".join(self.errors(RATE, RATE)))

    def test_allowed_names_include_term(self):
        """The preferred name is itself allowed."""
        entry = dict(RATE, allowed_names=["rate"])
        self.assertIn("must include term", " ".join(self.errors(entry)))

    def test_avoid_overlaps_allowed(self):
        """A name is not both approved and banned."""
        entry = dict(RATE, allowed_names=["decay rate", "rate"], avoid_names=["rate"])
        self.assertIn("overlaps", " ".join(self.errors(entry)))

    def test_avoid_shared_across_terms(self):
        """A banned name belongs to one object."""
        entry = dict(RATE, avoid_names=["bias"])
        self.assertIn("duplicated across", " ".join(self.errors(FIELD, entry)))

    def test_not_for_rejected(self):
        """The legacy key fails."""
        self.assertIn("not_for", " ".join(self.errors(dict(RATE, not_for=["x"]))))

    def test_meaning_uses_a_banned_name(self):
        """A meaning is closed vocabulary."""
        entry = dict(RATE, standard_meaning="The loss due to the bias.")
        self.assertIn("standard_meaning uses", " ".join(self.errors(FIELD, entry)))

    def test_meaning_rejects_its_own_label(self):
        """An entry may name its own label to reject it."""
        entry = dict(FIELD, standard_meaning="The applied field, never a bias.")
        self.assertEqual(self.errors(entry), [])

    def test_shared_registry_must_be_a_string(self):
        """The top-level key has one form."""
        self.assertIn("must be a string",
                      " ".join(cv._validate_registry(registry(RATE, shared_registry=1))))


class FileCase(unittest.TestCase):
    """A temporary project."""

    def setUp(self):
        """Create the folder."""
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.project = self.root / "project-vocabulary.json"

    def tearDown(self):
        """Remove the folder."""
        self.tmp.cleanup()

    def write(self, path, data):
        """Write a registry as JSON."""
        path.write_text(json.dumps(data), encoding="utf-8")
        return path


class TestMerge(FileCase):
    """A project registry with a shared registry."""

    def test_project_alone(self):
        """No shared registry: only the project's terms."""
        self.write(self.project, registry(RATE))
        merged = cv.load_registries(self.project)
        self.assertEqual([t["term"] for t in merged["terms"]], ["decay rate"])

    def test_no_registry(self):
        """No project registry: no terms."""
        self.assertEqual(cv.load_registries(None)["terms"], [])

    def test_shared_named_by_the_project(self):
        """A relative path starts at the project file, and the source is the file's name."""
        self.write(self.root / "field.json", registry(FIELD))
        self.write(self.project, registry(RATE, shared_registry="field.json"))
        terms = cv.load_registries(self.project)["terms"]
        self.assertEqual({t["_source"] for t in terms}, {"field.json", self.project.name})
        self.assertEqual(len(terms), 2)

    def test_argument_overrides_the_project(self):
        """An explicit shared registry wins over the one the project names."""
        other = self.write(self.root / "other.json", registry(FIELD))
        self.write(self.project, registry(RATE, shared_registry="absent.json"))
        terms = cv.load_registries(self.project, other)["terms"]
        self.assertEqual(len(terms), 2)

    def test_missing_shared_is_reported_and_left_out(self):
        """A machine without the shared file still works."""
        self.write(self.project, registry(RATE, shared_registry="absent.json"))
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            terms = cv.load_registries(self.project)["terms"]
        self.assertEqual(len(terms), 1)
        self.assertIn("shared registry missing", err.getvalue())

    def test_duplicate_across_registries(self):
        """A term sits in one registry only."""
        self.write(self.root / "shared.json", registry(RATE))
        self.write(self.project, registry(RATE, shared_registry="shared.json"))
        with self.assertRaisesRegex(ValueError, "duplicate term"):
            cv.load_registries(self.project)

    def test_project_meaning_may_not_use_a_shared_banned_name(self):
        """The closed vocabulary covers the merge."""
        self.write(self.root / "shared.json", registry(FIELD))
        entry = dict(RATE, standard_meaning="The loss due to the bias.")
        self.write(self.project, registry(entry, shared_registry="shared.json"))
        with self.assertRaisesRegex(ValueError, "standard_meaning uses"):
            cv.load_registries(self.project)


class TestCheckFile(FileCase):
    """The result for one file."""

    def merged(self, *terms):
        """Return merged terms of a project registry."""
        self.write(self.project, registry(*terms))
        return cv.load_registries(self.project)

    def test_scan_only_by_default(self):
        """A used term needs no definitions table unless asked."""
        note = self.root / "a.md"
        note.write_text("The decay rate is small.\n")
        self.assertEqual(cv.check_file(note, self.merged(RATE))[:2], (0, "OK"))

    def test_definitions_on_request(self):
        """With the coverage check, a used term needs a row."""
        note = self.root / "a.md"
        note.write_text("The decay rate is small.\n")
        code, status, failures = cv.check_file(note, self.merged(RATE), require_definitions=True)
        self.assertEqual((code, status), (1, "FAIL"))
        self.assertIn("missing Definitions row", failures[0])

    def test_markdown_row_covers_a_term(self):
        """A row of the Definitions table is enough."""
        note = self.root / "a.md"
        note.write_text("## Definitions\n\n| Term |\n|---|\n| decay rate |\n\nThe decay rate.\n")
        self.assertEqual(cv.check_file(note, self.merged(RATE), require_definitions=True)[0], 0)

    def test_latex_row_covers_a_term(self):
        """The first column of a longtable is read."""
        note = self.root / "a.tex"
        note.write_text("\\section{Definitions}\n\\begin{longtable}{ll}\ndecay rate & x \\\\\n"
                        "\\end{longtable}\n\\section{Text}\nThe decay rate.\n")
        self.assertEqual(cv.check_file(note, self.merged(RATE), require_definitions=True)[0], 0)

    def test_registry_citation_covers_a_term(self):
        """A file that cites the registry needs no rows."""
        note = self.root / "a.md"
        note.write_text("Terms follow project-vocabulary.json.\n\nThe decay rate.\n")
        self.assertEqual(cv.check_file(note, self.merged(RATE), require_definitions=True)[0], 0)

    def test_banned_name_reports_line_and_term(self):
        """A failure names the line and the replacement."""
        note = self.root / "a.md"
        note.write_text("One.\nThe bias.\n")
        code, _, failures = cv.check_file(note, self.merged(FIELD))
        self.assertEqual(code, 1)
        self.assertIn("line 2", failures[0])
        self.assertIn("external magnetic field", failures[0])

    def test_latex_comment_is_not_scanned(self):
        """A LaTeX comment is not a use."""
        note = self.root / "a.tex"
        note.write_text("Text. % not the bias\n")
        self.assertEqual(cv.check_file(note, self.merged(FIELD))[:2], (0, "OK"))


class TestCommandLine(FileCase):
    """The options."""

    def run_main(self, *args):
        """Run the script and return its exit code."""
        out = io.StringIO()
        argv, sys.argv = sys.argv, ["check_vocabulary.py", *map(str, args)]
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
                return cv.main()
        finally:
            sys.argv = argv

    def test_discovers_the_project_registry(self):
        """The registry is found in the parents of the file."""
        self.write(self.project, registry(FIELD))
        sub = self.root / "notes"
        sub.mkdir()
        note = sub / "a.md"
        note.write_text("The bias.\n")
        self.assertEqual(self.run_main("--file", note), 1)

    def test_old_option_names(self):
        """``--note`` and ``--notes-root`` still work."""
        self.write(self.project, registry(FIELD))
        note = self.root / "a.md"
        note.write_text("Clean.\n")
        self.assertEqual(self.run_main("--note", note), 0)
        self.assertEqual(self.run_main("--notes-root", self.root), 0)

    def test_root_reads_tex(self):
        """A folder scan covers LaTeX."""
        self.write(self.project, registry(FIELD))
        (self.root / "a.tex").write_text("The bias.\n")
        self.assertEqual(self.run_main("--root", self.root), 1)

    def test_avoid_only_turns_definitions_off(self):
        """A layer that asks for coverage can still ask for the scan alone."""
        self.write(self.project, registry(RATE))
        note = self.root / "a.md"
        note.write_text("The decay rate.\n")
        self.assertEqual(self.run_main("--file", note, "--definitions"), 1)
        self.assertEqual(self.run_main("--file", note, "--definitions", "--avoid-only"), 0)

    def test_invalid_registry_fails(self):
        """A broken registry stops the check."""
        self.write(self.project, {"version": 2, "terms": []})
        note = self.root / "a.md"
        note.write_text("Text.\n")
        self.assertEqual(self.run_main("--file", note), 1)


if __name__ == "__main__":
    unittest.main()
