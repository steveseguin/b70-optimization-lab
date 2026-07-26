#!/usr/bin/env python3
"""CPU-only regression tests for the Laguna XCCL probe launcher."""

from __future__ import annotations

import os
import shlex
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
WRAPPER = TOOLS / "run_xccl_collective_probe.sh"
PROBE = TOOLS / "xccl_collective_probe.py"
LADDER = TOOLS / "run_laguna_post_reboot_ladder.sh"
PINNED_PYTHON_LINE = "readonly python=/home/steve/.venvs/deepseek-v4-xpu/bin/python"


class XcclProbeLauncherCpuTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.tools = self.root / "tools"
        self.tools.mkdir()

        self.fake_python = self.tools / "fake-python"
        self.fake_python.write_text(
            """#!/usr/bin/env bash
set -uo pipefail
rank=${RANK:?}
mode=${FAKE_PROBE_MODE:-pass}

emit() {
  printf '[rank %s] %s t=123.45\\n' "$rank" "$1"
}

if [[ "$mode" == import-failure && "$rank" == 2 ]]; then
  echo "injected import failure" >&2
  exit 7
fi

emit import-done
emit "device-set fake-xpu-$rank"
emit pg-initialised
emit tensor-allocated

if [[ "$mode" == pre-collective-failure ]]; then
  exit 5
fi

emit all_reduce-start
if [[ "$mode" == collective-failure ]]; then
  exit 6
fi

emit "all_reduce-done sum=10.0"
if [[ "$mode" != missing-verification || "$rank" != 2 ]]; then
  emit "verify OK expected=10.0"
fi
emit teardown-done

if [[ "$mode" == nonzero-rank && "$rank" == 2 ]]; then
  exit 9
fi
"""
        )
        self.fake_python.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)

        wrapper_text = WRAPPER.read_text()
        self.assertEqual(wrapper_text.count(PINNED_PYTHON_LINE), 1)
        wrapper_text = wrapper_text.replace(
            PINNED_PYTHON_LINE,
            f"readonly python={shlex.quote(str(self.fake_python))}",
        )
        self.wrapper = self.tools / WRAPPER.name
        self.wrapper.write_text(wrapper_text)
        self.wrapper.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
        (self.tools / PROBE.name).write_text("# fake probe source identity\n")
        self.run_number = 0

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def run_wrapper(
        self,
        *extra_args: str,
        cwd: Path | None = None,
    ) -> tuple[subprocess.CompletedProcess[str], Path]:
        self.run_number += 1
        scratch = self.root / f"scratch-{self.run_number}"
        env = os.environ.copy()
        env["XCCL_PROBE_SCRATCH"] = str(scratch)
        completed = subprocess.run(
            [str(self.wrapper), "cpu-test", *extra_args],
            cwd=cwd or self.root,
            env=env,
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
        return completed, scratch

    def test_tracked_wrapper_invokes_its_sibling_probe(self) -> None:
        text = WRAPPER.read_text()
        self.assertIn(
            'readonly probe_source="$script_dir/xccl_collective_probe.py"',
            text,
        )
        self.assertIn('"$python" "$probe_source"', text)
        self.assertNotIn('"$scratch/xccl_probe.py"', text)
        self.assertTrue(PROBE.is_file())

    def test_ladder_preserves_diagnostics_without_prescribing_reboot(self) -> None:
        text = LADDER.read_text()
        self.assertIn('>"$probe_log" 2>&1', text)
        self.assertIn("^PROBE_RESULT=PASS clean_teardowns=4/4 ", text)
        self.assertIn("do not infer a recovery action", text)
        self.assertNotIn("collective stack is wedged, reboot required", text)

    def test_four_complete_fake_ranks_pass_from_unrelated_cwd(self) -> None:
        completed, _ = self.run_wrapper(cwd=Path("/"))
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn(
            "PROBE_RESULT=PASS clean_teardowns=4/4",
            completed.stdout,
        )
        self.assertEqual(completed.stdout.count(" PASS exit=0 "), 4)

    def test_missing_sibling_is_a_harness_failure_before_launch(self) -> None:
        (self.tools / PROBE.name).unlink()
        completed, scratch = self.run_wrapper()
        self.assertEqual(completed.returncode, 2)
        self.assertIn("probe source is not a readable regular file", completed.stderr)
        self.assertIn("PROBE_RESULT=HARNESS_FAILURE", completed.stderr)
        self.assertFalse(scratch.exists())

    def test_import_failure_is_not_called_a_collective_failure(self) -> None:
        completed, _ = self.run_wrapper("FAKE_PROBE_MODE=import-failure")
        self.assertEqual(completed.returncode, 1)
        self.assertIn(
            "PROBE_RESULT=HARNESS_OR_IMPORT_FAILURE clean_teardowns=3/4",
            completed.stdout,
        )
        self.assertNotIn("PROBE_RESULT=COLLECTIVE_STAGE_FAILURE", completed.stdout)

    def test_tensor_completion_without_collective_start_is_not_overclaimed(
        self,
    ) -> None:
        completed, _ = self.run_wrapper("FAKE_PROBE_MODE=pre-collective-failure")
        self.assertEqual(completed.returncode, 1)
        self.assertIn(
            "PROBE_RESULT=PRE_COLLECTIVE_FAILURE clean_teardowns=0/4",
            completed.stdout,
        )
        self.assertEqual(
            completed.stdout.count("furthest=tensor-allocated"),
            4,
        )

    def test_collective_stage_failure_requires_all_ranks_to_mark_start(self) -> None:
        completed, _ = self.run_wrapper("FAKE_PROBE_MODE=collective-failure")
        self.assertEqual(completed.returncode, 1)
        self.assertIn(
            "PROBE_RESULT=COLLECTIVE_STAGE_FAILURE clean_teardowns=0/4",
            completed.stdout,
        )
        self.assertEqual(
            completed.stdout.count("furthest=all_reduce-start"),
            4,
        )

    def test_zero_exit_without_verification_fails(self) -> None:
        completed, _ = self.run_wrapper("FAKE_PROBE_MODE=missing-verification")
        self.assertEqual(completed.returncode, 1)
        self.assertIn(
            "PROBE_RESULT=VERIFICATION_FAILURE clean_teardowns=4/4",
            completed.stdout,
        )
        self.assertIn("rank2: FAIL exit=0 furthest=teardown-done", completed.stdout)

    def test_nonzero_rank_fails_even_with_complete_markers(self) -> None:
        completed, _ = self.run_wrapper("FAKE_PROBE_MODE=nonzero-rank")
        self.assertEqual(completed.returncode, 1)
        self.assertIn(
            "PROBE_RESULT=PROCESS_EXIT_FAILURE clean_teardowns=4/4",
            completed.stdout,
        )
        self.assertIn("rank2: FAIL exit=9 furthest=teardown-done", completed.stdout)

    def test_reserved_rank_override_fails_before_output_creation(self) -> None:
        completed, scratch = self.run_wrapper("RANK=3")
        self.assertEqual(completed.returncode, 2)
        self.assertIn("environment override is reserved", completed.stderr)
        self.assertFalse(scratch.exists())

    def test_existing_output_is_preserved_and_refused(self) -> None:
        completed, scratch = self.run_wrapper()
        self.assertEqual(completed.returncode, 0)
        output = scratch / "probe-cpu-test"
        sentinel = output / "sentinel"
        sentinel.write_text("preserve me\n")

        env = os.environ.copy()
        env["XCCL_PROBE_SCRATCH"] = str(scratch)
        repeated = subprocess.run(
            [str(self.wrapper), "cpu-test"],
            cwd=self.root,
            env=env,
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
        self.assertEqual(repeated.returncode, 2)
        self.assertIn("probe output already exists", repeated.stderr)
        self.assertEqual(sentinel.read_text(), "preserve me\n")


if __name__ == "__main__":
    unittest.main()
