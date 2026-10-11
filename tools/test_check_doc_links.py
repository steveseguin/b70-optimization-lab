"""Offline regressions for the repository-wide documentation link audit."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).with_name("check-doc-links.py")
SPEC = importlib.util.spec_from_file_location("check_doc_links", SCRIPT)
CHECK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECK)


class DocLinksTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path

    def run_check(self, *args):
        return subprocess.run([sys.executable, "-B", str(SCRIPT), *args],
                              cwd=self.root, text=True, capture_output=True)

    def git(self, *args):
        subprocess.run(["git", "-C", str(self.root), *args], check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def test_code_examples_are_not_links_but_surrounding_prose_is(self):
        doc = self.write("note.md", """```python
hidden += up[layer, position](silu(down[layer, position](hidden)))
```
~~~text
[example](fenced-missing.md)
~~~
`[example](inline-missing.md)` and `` `[example](nested-missing.md)` ``.
[`real label`](actual-missing.md)
""")
        self.assertEqual([item["link"] for item in CHECK.check_file(str(doc), str(self.root))],
                         ["actual-missing.md"])

    def test_root_relative_encoded_and_angle_destinations(self):
        self.write("with space.md", "target")
        doc = self.write("notes/note.md", "[one](/with%20space.md#heading)\n"
                         '[two](<../with space.md> "title")\n')
        self.assertEqual(CHECK.check_file(str(doc), str(self.root)), [])

    def test_host_paths_and_templates_are_reported_as_unverified(self):
        self.write("home/example/note.md", "Even this must not validate a host path.")
        doc = self.write("note.md", "[host](/home/example/note.md:9)\n"
                         "[file](file:///tmp/note.md)\n[example](…)\n"
                         "[template](models/${id}.html)\n[web](https://example.com/)\n")
        unverified = []
        self.assertEqual(CHECK.check_file(str(doc), str(self.root), unverified), [])
        self.assertEqual([item["reason"] for item in unverified],
                         ["absolute-host-path", "absolute-host-path", "template", "template"])
        result = self.run_check("--json", "report.json", "note.md")
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads((self.root / "report.json").read_text())
        self.assertEqual(report["unverified_total"], 4)
        self.assertIn("unverified", result.stdout)

    def test_html_handles_single_quotes_and_ignores_comments_and_script_text(self):
        doc = self.write("page.html", "<!-- <a href='comment-missing.md'> -->\n"
                         "<script>const example = \"href='script-missing.md'\";</script>\n"
                         "<a href='actual-missing.md'>link</a>\n"
                         "<img src='//example.com/image.png'>")
        self.assertEqual([item["link"] for item in CHECK.check_file(str(doc), str(self.root))],
                         ["actual-missing.md"])

    def test_all_tracked_includes_staged_notes_and_html_but_not_untracked_files(self):
        self.git("init", "-q", "-b", "main")
        self.write("README.md", "[ok](existing.txt)")
        self.write("existing.txt", "target")
        self.write("experiments/new note.md", "[broken](missing.txt)")
        self.write("models/page.html", '<a href="missing.txt">broken</a>')
        self.write("experiments/scratch.md", "[untracked](scratch-missing.txt)")
        self.git("add", "README.md", "existing.txt", "experiments/new note.md", "models/page.html")
        default = self.run_check()
        self.assertEqual(default.returncode, 0, default.stdout + default.stderr)
        result = self.run_check("--all-tracked", "--json", "report.json")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        report = json.loads((self.root / "report.json").read_text())
        self.assertEqual(report["documents_checked"], 3)
        self.assertEqual(set(report["findings"]), {"experiments/new note.md", "models/page.html"})
        self.assertEqual(report["broken_total"], 2)

    def test_missing_tracked_document_fails_instead_of_disappearing(self):
        self.git("init", "-q", "-b", "main")
        doc = self.write("experiments/note.md", "saved")
        self.git("add", "experiments/note.md")
        doc.unlink()
        result = self.run_check("--all-tracked", "--json", "report.json")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        report = json.loads((self.root / "report.json").read_text())
        self.assertIn("experiments/note.md", report["read_errors"])

    def test_existing_baseline_still_reports_without_failing(self):
        self.write("README.md", "[old](missing.md)")
        self.write("data/doc-link-baseline.json", json.dumps({"known_broken": [
            {"document": "README.md", "link": "missing.md"}]}))
        result = self.run_check("--json", "report.json")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads((self.root / "report.json").read_text())
        self.assertEqual(report["broken_total"], 0)
        self.assertEqual(report["known_broken_total"], 1)

    def pinned_baseline(self):
        document = self.write("README.md", "[old](missing.md)")
        source = self.write("evidence/source.txt", "Original evidence\n")
        entry = {"document": "README.md", "link": "missing.md",
                 "document_sha256": hashlib.sha256(document.read_bytes()).hexdigest(),
                 "resolved_source": "evidence/source.txt",
                 "resolved_source_sha256": hashlib.sha256(source.read_bytes()).hexdigest()}
        self.write("data/doc-link-baseline.json", json.dumps({"known_broken": [entry]}))
        return entry

    def test_pinned_baseline_accepts_matching_document_and_source(self):
        self.pinned_baseline()
        result = self.run_check("--json", "report.json")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads((self.root / "report.json").read_text())
        self.assertEqual(report["known_broken_total"], 1)
        self.assertEqual(report["baseline_errors"], [])

    def test_pinned_baseline_rejects_changed_or_removed_evidence(self):
        for change, message in (("document", "document_sha256 mismatch"),
                                ("source", "resolved_source_sha256 mismatch"),
                                ("missing-source", "resolved_source does not exist")):
            with self.subTest(change=change):
                self.pinned_baseline()
                if change == "document":
                    # Even repairing the old link must not silently rewrite a frozen document.
                    self.write("README.md", "[repaired](evidence/source.txt)")
                elif change == "source":
                    self.write("evidence/source.txt", "Changed evidence\n")
                else:
                    (self.root / "evidence/source.txt").unlink()
                result = self.run_check("--json", "report.json")
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                report = json.loads((self.root / "report.json").read_text())
                self.assertEqual(report["broken_total"], 0)
                self.assertTrue(any(message in error for error in report["baseline_errors"]))

    def test_unhashed_resolution_still_requires_an_existing_file(self):
        self.write("README.md", "[old](missing.md)")
        self.write("data/doc-link-baseline.json", json.dumps({"known_broken": [
            {"document": "README.md", "link": "missing.md", "resolved_source": "lost.txt"}]}))
        result = self.run_check()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("resolved_source does not exist", result.stdout)

    def test_baseline_rejects_malformed_or_unbound_hashes_and_external_sources(self):
        cases = (({"document_sha256": None}, (), "document_sha256 must be"),
                 ({}, ("resolved_source",), "resolved_source must be"),
                 ({"resolved_source": str(self.root / "evidence/source.txt")}, (),
                  "resolved_source must be"),
                 ({"resolved_source": "../outside.txt"}, (), "escapes the repository"))
        for changes, removed, message in cases:
            with self.subTest(changes=changes, removed=removed):
                entry = self.pinned_baseline()
                entry.update(changes)
                for key in removed:
                    entry.pop(key)
                self.write("data/doc-link-baseline.json", json.dumps({"known_broken": [entry]}))
                result = self.run_check()
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn(message, result.stdout)

    def test_all_tracked_rejects_explicit_paths(self):
        result = self.run_check("--all-tracked", "README.md")
        self.assertEqual(result.returncode, 2)
        self.assertIn("cannot be combined", result.stderr)

    def test_all_tracked_refuses_a_silent_partial_scan_from_a_subdirectory(self):
        self.git("init", "-q", "-b", "main")
        nested = self.root / "experiments"
        nested.mkdir()
        result = subprocess.run([sys.executable, "-B", str(SCRIPT), "--all-tracked"],
                                cwd=nested, text=True, capture_output=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("repository root", result.stderr)


if __name__ == "__main__":
    unittest.main()
