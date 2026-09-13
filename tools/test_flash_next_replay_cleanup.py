"""Replay benchmark failures must still request the owned server's shutdown."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = sorted(ROOT.glob("repro/qwen38-flash-next-fp8-tp4-mtp1-*/wait-and-run-client.sh"))


class ReplayCleanupTest(unittest.TestCase):
    def test_failed_and_successful_suite_both_request_stop_and_preserve_status(self):
        self.assertEqual(len(SCRIPTS), 5)
        for source in SCRIPTS:
            for rc in (0, 7):
                with self.subTest(recipe=source.parent.name, rc=rc), tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    bin_dir = root / "bin"
                    bin_dir.mkdir()
                    for name, code in (("curl", 0), ("sleep", 0), ("python", rc)):
                        path = bin_dir / name
                        path.write_text(f"#!/bin/sh\nexit {code}\n")
                        path.chmod(0o755)
                    run_dir = root / "qwen38-flash-next-fp8-tp4-ep4-fullgraphdet-mtp1-4352-ple-only-r1-attempt999999"
                    run_dir.mkdir()
                    script = root / "repro/packet/wait-and-run-client.sh"
                    script.parent.mkdir(parents=True)
                    # Isolate hardcoded state-file paths as well as the process and result paths.
                    script.write_text(source.read_text().replace("/tmp/q38-", f"{tmp}/q38-"))
                    env = dict(os.environ, PATH=f"{bin_dir}:{os.environ['PATH']}",
                               REPRO_VENV_ROOT=tmp, REPRO_RESULT_PARENT=tmp)
                    result = subprocess.run(["bash", str(script), "999999", "19900"],
                                            env=env, capture_output=True, text=True, timeout=5)
                    self.assertEqual(result.returncode, rc, result.stderr)
                    self.assertIn("STOP", (root / "q38-mtp1-ple-only-a999999.stop").read_text())


if __name__ == "__main__":
    unittest.main()
