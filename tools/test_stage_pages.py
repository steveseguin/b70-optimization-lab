"""Static Pages staging preserves public bytes and refuses unsafe inputs."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location("stage_pages", Path(__file__).with_name("stage-pages.py"))
stage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage)


class PagesStaging(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "source"
        self.root.mkdir()
        self.tracked = {}

    def put(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        self.tracked[name] = "100644"

    def plan(self):
        planner = stage.Planner(self.root, self.tracked)
        return planner, planner.plan()

    def test_closure_preserves_assets_and_raw_markdown_but_not_experiment_tree(self):
        self.put("index.html", '<link href="site.css"><a href="models/">Models</a>'
                 '<button data-copy-markdown="repro/README.md"></button><script>fetch("packages/catalog.json")</script>')
        self.put("models/index.html", '<img src="../plot.svg?version=1"><img srcset="../small.png 1x, ../large.png 2x">')
        self.put("site.css", '@import "extra.css"; body {background:url("bg.png")}')
        self.put("extra.css", "body {color:black}")
        for name in ("plot.svg", "small.png", "large.png", "bg.png", "icon.png"):
            self.put(name, name)
        self.put("site.webmanifest", json.dumps({"icons": [{"src": "/icon.png"}]}))
        self.put("repro/README.md", "[Proof](../experiments/one/proof.json)\n[History](missing.md)\n")
        self.put("experiments/one/proof.json", '{"answer":42}')
        self.put("experiments/one/unlinked.bin", "do not copy")
        self.put("packages/catalog.json", json.dumps({"packages": [{"id": "demo", "guide": "repro/README.md"},
                 {"id": "fallback", "manifest": "packages/fallback/package.json"}]}))
        self.put("models/demo.html", "Demo")
        self.put("models/fallback.html", "Fallback")
        self.put("packages/fallback/package.json", "{}")
        self.put("packages/fallback/README.md", "Fallback guide")
        planner, report = self.plan()
        self.assertEqual(report["errors"], [])
        self.assertEqual(len(report["warnings"]), 1)
        self.assertNotIn("experiments/one/unlinked.bin", report["files"])
        self.assertIn("packages/fallback/README.md", report["files"])
        destination = self.root.parent / "output"
        stage.copy_plan(planner, destination)
        for rel in report["files"]:
            self.assertEqual((destination / rel).read_bytes(), (self.root / rel).read_bytes())
        self.assertTrue((destination / ".nojekyll").exists())

    def test_missing_html_asset_fails_even_if_markdown_warns(self):
        self.put("index.html", '<img src="missing.png"><a href="guide.md">Guide</a>')
        self.put("guide.md", "[Missing history](old.md)")
        planner, report = self.plan()
        self.assertEqual(len(report["errors"]), 1)
        self.assertEqual(len(report["warnings"]), 1)
        with self.assertRaises(ValueError):
            stage.copy_plan(planner, self.root.parent / "output")

    def test_symlink_file_parent_and_traversal_are_refused(self):
        self.put("index.html", '<a href="link.txt">x</a><a href="linked/secret.txt">x</a><a href="../escape">x</a>')
        outside = self.root.parent / "outside"
        outside.mkdir()
        (outside / "secret.txt").write_text("not public")
        (self.root / "link.txt").symlink_to(outside / "secret.txt")
        (self.root / "linked").symlink_to(outside, target_is_directory=True)
        self.tracked.update({"link.txt": "120000", "linked/secret.txt": "100644"})
        _, report = self.plan()
        self.assertEqual(len(report["errors"]), 3)
        self.assertEqual(set(report["files"]), {"index.html"})

    def test_reference_markdown_and_cycles(self):
        self.put("index.html", '<a href="a.md">Guide</a>')
        self.put("a.md", '[b][proof]\n[proof]: <b.md>\n```\n[not a link](missing.bin)\n```')
        self.put("b.md", '[a](a.md)')
        _, report = self.plan()
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["warnings"], [])
        self.assertEqual(report["file_count"], 3)

    def test_external_links_ignored_same_origin_and_untracked_checked(self):
        self.put("index.html", '<a href="https://example.org/nope">x</a>'
                 '<img src="https://neural.download/image.png"><a href="untracked.txt">x</a>')
        self.put("image.png", "image")
        (self.root / "untracked.txt").write_text("private")
        _, report = self.plan()
        self.assertEqual(len(report["errors"]), 1)
        self.assertIn("image.png", report["files"])

    def test_output_must_be_empty_and_outside_source(self):
        self.put("index.html", "Hello")
        planner, _ = self.plan()
        with self.assertRaises(ValueError):
            stage.copy_plan(planner, self.root / "out")
        destination = self.root.parent / "output"
        destination.mkdir()
        (destination / "keep").write_text("existing work")
        with self.assertRaises(ValueError):
            stage.copy_plan(planner, destination)

    def test_symlink_destination_parent_is_refused(self):
        self.put("index.html", "Hello")
        planner, _ = self.plan()
        link = self.root.parent / "link"
        link.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(ValueError):
            stage.copy_plan(planner, link / "out")

    def test_changed_source_cannot_be_copied_as_a_symlink(self):
        self.put("index.html", "Hello")
        planner, _ = self.plan()
        (self.root / "index.html").unlink()
        (self.root / "index.html").symlink_to("/etc/passwd")
        destination = self.root.parent / "out"
        with self.assertRaises(ValueError):
            stage.copy_plan(planner, destination)
        self.assertFalse(destination.exists())

    def test_manifest_dependencies_evidence_and_commands_expand_without_reading_evidence_json(self):
        self.put("index.html", '<a href="packages/catalog.json">Catalog</a>')
        self.put("packages/catalog.json", json.dumps({"packages": [{"id": "demo", "manifest": "packages/demo/package.json",
                 "guide": "repro/demo/README.md", "dependencies": ["data/receipt.json"]}]}))
        self.put("models/demo.html", "Model")
        self.put("repro/demo/README.md", "Guide")
        self.put("packages/demo/package.json", json.dumps({"evidence": ["experiments/demo/summary.json"],
                 "commands": {"health": "scripts/health.py"}, "dependencies": ["tools/helper.py"]}))
        self.put("families/demo.json", json.dumps({"evidence": ["data/family.json"], "guide": "docs/demo"}))
        self.put("data/receipt.json", "not parsed: evidence is preserved as bytes")
        self.put("experiments/demo/summary.json", "{}")
        self.put("data/family.json", "{}")
        self.put("scripts/health.py", "print('healthy')")
        self.put("tools/helper.py", "print('helper')")
        self.put("docs/demo/README.md", "Directory guide")
        self.put("docs/demo/unlinked.bin", "Not included")
        _, report = self.plan()
        self.assertEqual(report["errors"], [])
        for rel in ("packages/demo/package.json", "data/receipt.json", "experiments/demo/summary.json",
                    "scripts/health.py", "tools/helper.py", "data/family.json", "docs/demo/README.md"):
            self.assertIn(rel, report["files"])
        self.assertNotIn("docs/demo/unlinked.bin", report["files"])

    def test_missing_manifest_dependency_is_a_required_error(self):
        self.put("index.html", "Site")
        self.put("families/demo.json", json.dumps({"evidence": ["data/missing.json"]}))
        _, report = self.plan()
        self.assertEqual(len(report["errors"]), 1)
        self.assertEqual(report["errors"][0]["url"], "data/missing.json")


if __name__ == "__main__":
    unittest.main()
