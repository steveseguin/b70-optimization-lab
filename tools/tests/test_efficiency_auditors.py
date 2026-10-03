"""Local, lightweight regression tests; no network, runtime, or Git mutations."""
import contextlib
import datetime as dt
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


metrics = load("efficiency_metrics", "scripts/efficiency-audit-metrics.py")
scanner = load("closure_scanner", "tools/public-closure-scanner.py")


class MetricsTests(unittest.TestCase):
    def run_main(self, flags=(), shallow=False, fetch_error=False, empty_window=False):
        now = dt.datetime.now(dt.timezone.utc)
        stamp = (now - dt.timedelta(days=2)).isoformat()
        calls = []

        def git(repo, *args):
            nonlocal shallow
            calls.append(args)
            if args[0] == "rev-parse":
                return str(shallow).lower()
            if args[0] == "fetch":
                if fetch_error:
                    raise subprocess.CalledProcessError(1, ["git", *args])
                shallow = False
                return ""
            if args[0] == "ls-files":
                return "experiments/idle/README.md\0"
            if "-1" in args:
                return stamp
            if "--diff-filter=A" in args:
                return ""
            if empty_window:
                return ""
            return f"abcdef\x1f{stamp}\x1fCodex Agent\x1fagent@example.com\x1fTest\x1fCo-Authored-By: Claude <c@example.com>\nco-authored-by: Human <h@example.com>\nCo-Authored-By: Claude <c@example.com>\x1e"

        output, errors = io.StringIO(), io.StringIO()
        with patch.object(metrics, "git", side_effect=git), patch("sys.argv", ["metrics", *flags]), contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            try:
                code = metrics.main()
            except SystemExit as exc:
                code = exc.code
        return code, json.loads(output.getvalue()) if output.getvalue() else None, errors.getvalue(), calls

    def test_shallow_requires_opt_in_without_fetch(self):
        code, data, errors, calls = self.run_main(shallow=True)
        self.assertNotEqual(code, 0)
        self.assertIsNone(data)
        self.assertIn("shallow repository", errors)
        self.assertFalse(any(c[0] == "fetch" for c in calls))

    def test_allow_shallow_warns_and_preserves_author(self):
        code, data, errors, calls = self.run_main(["--allow-shallow"], shallow=True)
        self.assertEqual(code, 0)
        self.assertTrue(data["shallow"])
        self.assertTrue(data["warnings"])
        self.assertIn("warning", errors)
        self.assertEqual(data["commits_by_author"], {"Codex Agent": 1})
        self.assertEqual(data["co_authors"], {"Claude": 1, "Human": 1})
        self.assertAlmostEqual(data["days_since_last_commit"], 2, places=2)
        self.assertAlmostEqual(data["days_since_last_commit_by_lane"]["idle"], 2, places=2)
        self.assertFalse(any(c[0] == "fetch" for c in calls))

    def test_unshallow_only_fetches_when_requested(self):
        code, data, _, calls = self.run_main(["--unshallow"], shallow=True)
        self.assertEqual(code, 0)
        self.assertFalse(data["shallow"])
        self.assertEqual([c for c in calls if c[0] == "fetch"], [("fetch", "--unshallow")])
        code, _, errors, _ = self.run_main(["--unshallow"], shallow=True, fetch_error=True)
        self.assertNotEqual(code, 0)
        self.assertIn("fetch --unshallow failed", errors)

    def test_empty_window_still_reports_age(self):
        code, data, _, _ = self.run_main(empty_window=True)
        self.assertEqual(code, 0)
        self.assertEqual(data["commits_total"], 0)
        self.assertEqual(data["campaigns_total"], 0)
        self.assertAlmostEqual(data["days_since_last_commit"], 2, places=2)
        self.assertAlmostEqual(data["days_since_last_commit_by_lane"]["idle"], 2, places=2)

    def test_recursive_campaigns_notes_duplicates_and_summary_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            files = {
                "experiments/lane/data/flat-prereg.json": {"campaign": "same"},
                "experiments/lane/data/nested/deep/preregistration.json": {"campaign_id": "same", "different": True},
                "experiments/lane/data/nested/deep/summary.json": {"passed": True, "promoted": False},
                "experiments/lane/data/alone/summary.json": {"closure": {"status": "closed-after-gpu-fault"}, "reference": {"passed": True}},
                "experiments/lane/notes/note-prereg.md": "Planned test",
                "experiments/lane/data/note/summary.json": {"promoted": True},
                "experiments/lane/notes/narrative-prereg.md": "Planned test",
                "experiments/lane/notes/narrative.md": "status: rejected",
                "experiments/lane/notes/day1-explicit-prereg.md": "Planned test",
                "experiments/lane/notes/day2-an-entirely-different-title.md": "Preregistration: `day1-explicit-prereg.md`\nstatus: rejected",
                "experiments/lane/data/old-prereg.json": {"campaign": "old"},
                "experiments/lane/data/old/summary.json": {"passed": True},
                "experiments/other/data/alone/summary.json": {"passed": False},
                "experiments/lane/data/untracked/summary.json": {"passed": True},
            }
            for rel, value in files.items():
                p = root / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(json.dumps(value) if isinstance(value, dict) else value)
            tracked = [p for p in files if "untracked" not in p]
            start = dt.datetime(2026, 10, 1, tzinfo=dt.timezone.utc)
            added = {p: start + dt.timedelta(hours=2 if p.endswith("summary.json") else 0) for p in tracked}
            del added["experiments/lane/data/old-prereg.json"]
            with patch.object(metrics, "_ADDED", added):
                rows = metrics.discover_campaigns(root, start - dt.timedelta(days=1), tracked)
            self.assertEqual(len(rows), 6)
            rows = {(r["lane"], r["campaign"]): r for r in rows}
            same = rows["lane", "same"]
            self.assertEqual(len(same["prereg_files"]), 2)
            self.assertEqual(same["outcome"], "accepted")
            self.assertEqual(same["latency_hours"], 2)
            self.assertIsNone(rows["lane", "alone"]["prereg_committed"])
            self.assertIsNone(rows["lane", "alone"]["latency_hours"])
            self.assertEqual(rows["lane", "alone"]["outcome"], "aborted-infra")
            self.assertEqual(rows["other", "alone"]["outcome"], "rejected")
            self.assertEqual(rows["lane", "note"]["outcome"], "accepted")
            self.assertEqual(rows["lane", "narrative"]["outcome"], "rejected")
            self.assertEqual(rows["lane", "day1-explicit"]["outcome"], "rejected")


class ClosureTests(unittest.TestCase):
    def test_release_failures_are_unavailable_not_empty(self):
        for exc in (FileNotFoundError(), subprocess.CalledProcessError(1, ["gh"])):
            cache = {}
            with patch.object(scanner.subprocess, "run", side_effect=exc) as run, contextlib.redirect_stderr(io.StringIO()) as errors:
                self.assertIsNone(scanner.release_assets("v1", cache))
                self.assertIsNone(scanner.release_assets("v1", cache))
            self.assertEqual(run.call_count, 1)
            self.assertIn("unavailable", errors.getvalue())
        with patch.object(scanner.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, stdout="")):
            self.assertEqual(scanner.release_assets("v1", {}), set())

    def test_dynamic_paths_not_truncated_and_equals_is_literal(self):
        self.assertEqual(scanner.repo_paths('f"repro/qwen35-{model}/run.py"'), [])
        self.assertEqual(scanner.repo_paths('repro/foo-*.patch results/run${attempt}.json'), [])
        self.assertEqual(scanner.repo_paths('/workspace/repro/foo.py /opt/scripts/bar.py'), [])
        self.assertEqual(scanner.repo_paths('experiments/lane/E=64.json'), ['experiments/lane/E=64.json'])

    def test_container_context_preserves_host_gaps(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            files = {
                "repro/lane/README.md": "repro/lane/Dockerfile repro/lane/host.sh https://github.com/steveseguin/b70-optimization-lab/releases/download/v1/asset.tgz",
                "repro/lane/Dockerfile": 'FROM base\nENV CCL_KERNEL_PATH=/opt/ccl/lib \\\n    PYTHONPATH=/workspace/src\nRUN python scripts/image-only.py\nRUN python - <<\'PY\'\nprint("/opt/internal")\nPY\nCOPY repro/lane/container.sh /opt/serve.sh\nCOPY scripts/missing-input.py /opt/input.py\nCOPY --from=builder scripts/generated.py /opt/generated.py\nENTRYPOINT ["/opt/serve.sh"]\n',
                "repro/lane/container.sh": "export CCL_KERNEL_PATH=/opt/ccl/lib\npython scripts/in-image.py\n",
                "repro/lane/host.sh": 'docker run -e CCL_KERNEL_PATH=/opt/ccl/lib --workdir /opt/work --mount type=bind,source=/mnt/real-input,target=/opt/dest -v "$SOURCE:/opt/application" image\ncat /opt/host-only/input\ncat /opt/vllm-src-host/input\n',
            }
            for rel, content in files.items():
                p = root / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(content)
            pkg = {"id": "test", "guide": "repro/lane/README.md", "manifest": "packages/test/package.json"}
            with patch.object(scanner, "ROOT", root):
                entries = scanner.container_entrypoints(set(files))
                self.assertEqual(entries, {"repro/lane/container.sh"})
                report = scanner.scan_package(pkg, set(files), {"v1": None}, entries)
            self.assertTrue(report["release_assets_unavailable"])
            self.assertTrue(report["warnings"])
            self.assertNotIn("missing_release_asset", report["findings"])
            missing = {x["path"] for x in report["findings"]["missing_path"]}
            self.assertEqual(missing, {"scripts/missing-input.py"})
            hosts = {x["path"] for x in report["findings"]["host_path_hardcoded"]}
            self.assertEqual(hosts, {"/mnt/real-input", "/opt/host-only/input", "/opt/vllm-src-host/input"})


if __name__ == "__main__":
    unittest.main()
