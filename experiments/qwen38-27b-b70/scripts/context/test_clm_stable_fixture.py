"""CPU-only fixture safety checks. No containers, host timestamp edits or model."""
import asyncio
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch


class FakePlainAgent:
    def __init__(self, logs_dir):
        self.logs_dir = logs_dir

    async def setup(self, environment):
        environment.order.append("base setup")


spec = importlib.util.spec_from_file_location(
    "stable_fixture_under_test", Path(__file__).with_name("clm_stable_fixture.py")
)
module = importlib.util.module_from_spec(spec)
with patch.dict(sys.modules, {"clm_baselines": types.SimpleNamespace(PlainAgent=FakePlainAgent)}):
    spec.loader.exec_module(module)


class FixtureTests(unittest.TestCase):
    def agent(self, logs_dir):
        with patch.dict("os.environ", {"SANDBOX_ROOT_MTIME": "1792687500"}):
            return module.StableFixtureAgent(logs_dir)

    def environment(self, return_code=0, stdout=None):
        env = types.SimpleNamespace(order=[], commands=[])

        async def execute(**kwargs):
            env.order.append("fixture setup")
            env.commands.append(kwargs)
            return types.SimpleNamespace(return_code=return_code, stderr="fixture error", stdout=stdout)

        env.exec = execute
        return env

    def test_missing_or_invalid_epoch_refuses_construction(self):
        for value in [None, "", "-1", "1.5", "nan", "1; touch /tmp/x", "4102444801"]:
            with self.subTest(value=value), patch.dict("os.environ", {}, clear=True):
                if value is not None:
                    module.os.environ["SANDBOX_ROOT_MTIME"] = value
                with self.assertRaises(ValueError):
                    module.StableFixtureAgent(Path("unused"))

    def test_command_changes_only_sandbox_root_mtime_and_preserves_atime(self):
        calls = []
        info = types.SimpleNamespace(st_atime_ns=123, st_mtime_ns=456)

        def stat(path):
            self.assertEqual(path, "/")
            return types.SimpleNamespace(st_atime_ns=info.st_atime_ns, st_mtime_ns=info.st_mtime_ns)

        def utime(path, *, ns):
            calls.append((path, ns))
            info.st_atime_ns, info.st_mtime_ns = ns

        command = module.fixture_command(1792687500)
        self.assertTrue(command.startswith("python3 - <<'PY'\n"))
        body = command.split("\n", 1)[1].rsplit("\nPY", 1)[0]
        out = io.StringIO()
        with patch.dict(sys.modules, {"os": types.SimpleNamespace(stat=stat, utime=utime)}), contextlib.redirect_stdout(out):
            exec(body, {})
        self.assertEqual(calls, [("/", (123, 1792687500 * 1_000_000_000))])
        self.assertEqual(json.loads(out.getvalue())["previous_mtime_ns"], 456)

    def test_setup_failure_prevents_receipt(self):
        with tempfile.TemporaryDirectory() as d:
            env = self.environment(return_code=1)
            with self.assertRaises(RuntimeError):
                asyncio.run(self.agent(Path(d)).setup(env))
            self.assertFalse((Path(d) / "stable-fixture.json").exists())

    def test_bad_receipts_fail_closed(self):
        for stdout in ["not json", "{}", "null", '{"path":"/app","mtime_ns":1792687500000000000}',
                       '{"path":"/","mtime_ns":0}']:
            with self.subTest(stdout=stdout), tempfile.TemporaryDirectory() as d:
                with self.assertRaises(RuntimeError):
                    asyncio.run(self.agent(Path(d)).setup(self.environment(stdout=stdout)))
                self.assertFalse((Path(d) / "stable-fixture.json").exists())

    def test_success_after_base_setup_records_verified_sandbox_value(self):
        receipt = {"path": "/", "mtime_ns": 1792687500000000000, "previous_mtime_ns": 42}
        with tempfile.TemporaryDirectory() as d:
            env = self.environment(stdout=json.dumps(receipt))
            asyncio.run(self.agent(Path(d)).setup(env))
            self.assertEqual(env.order, ["base setup", "fixture setup"])
            self.assertEqual(len(env.commands), 1)
            self.assertEqual(env.commands[0]["timeout_sec"], 10)
            saved = json.loads((Path(d) / "stable-fixture.json").read_text())
            self.assertEqual(saved["mtime_ns"], receipt["mtime_ns"])


if __name__ == "__main__":
    unittest.main()
