#!/usr/bin/env python3
"""Offline source checks for the PENDING realistic embedded-MTP wrapper."""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("run-embedded-mtp-vdr2-realistic.sh")


class RealisticWrapperStaticTests(unittest.TestCase):
    def test_pending_live_path_stops_before_external_commands(self) -> None:
        completed = subprocess.run(
            ["/bin/bash", str(SCRIPT)],
            cwd=Path("/"),
            env={"PATH": "/definitely-empty", "LC_ALL": "C"},
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(completed.stdout, "")
        self.assertIn("PENDING", completed.stderr)

    def test_source_is_pending_and_four_lifetimes_are_ordered(self) -> None:
        source = SCRIPT.read_text()
        self.assertIn('LIVE_ENABLE_STATE="PENDING"', source)
        self.assertIn(
            'EXPECTED_CAPTURE_SHA256="40b962bff418ca1481763228a5630f51274492629f21ca3e89401e198a6b73b2"',
            source,
        )
        self.assertIn(
            'EXPECTED_REALISTIC_GATES_SHA256="c6e23541d2a06d5b88c61a3e08fe5528305a1eef1041cf189d748cc678662bcb"',
            source,
        )
        calls = [
            'run_lifetime scored-control control scored "$PORT_SCORED_CONTROL"',
            'run_lifetime scored-mtp3 mtp3 scored "$PORT_SCORED_MTP3"',
            'run_lifetime forensic-control control forensic "$PORT_FORENSIC_CONTROL"',
            'run_lifetime forensic-mtp3 mtp3 forensic "$PORT_FORENSIC_MTP3"',
        ]
        positions = [source.index(call) for call in calls]
        self.assertEqual(positions, sorted(positions))
        self.assertEqual(source.count("run_lifetime scored-"), 2)
        self.assertEqual(source.count("run_lifetime forensic-"), 2)

    def test_missing_or_wrong_ack_stops_before_external_commands(self) -> None:
        activated = SCRIPT.read_text().replace(
            'LIVE_ENABLE_STATE="PENDING"',
            'LIVE_ENABLE_STATE="REVIEWED_AND_PINNED"',
            1,
        )
        with tempfile.TemporaryDirectory() as temporary:
            probe = Path(temporary) / "runner.sh"
            probe.write_text(activated)
            for ack in (None, "WRONG_ACK"):
                env = {"PATH": "/definitely-empty", "LC_ALL": "C"}
                if ack is not None:
                    env["QWEN36_EMBEDDED_MTP_REALISTIC_LIVE_ACK"] = ack
                completed = subprocess.run(
                    ["/bin/bash", str(probe)],
                    cwd=Path("/"),
                    env=env,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(completed.returncode, 2)
                self.assertEqual(completed.stdout, "")
                self.assertIn("requires the exact acknowledgement", completed.stderr)

    def test_once_only_contract_and_fail_closed_joins_are_present(self) -> None:
        source = SCRIPT.read_text()
        function = source[source.index("run_lifetime() {") : source.index("# Preregistered fresh-lifetime order")]
        self.assertLess(function.index('"$CAPTURE" prepare'), function.index("metrics-before.prom"))
        self.assertIn('"$CAPTURE" run', function)
        self.assertIn('"$CAPTURE" forensic', function)
        self.assertIn('"max_tokens": 512', SCRIPT.with_name("capture-openai-completions-once.py").read_text())
        self.assertNotIn("--ignore-eos", function)
        self.assertNotIn("--spec-draft-model", source)
        for required in (
            "--forensic-server-identity",
            "--forensic-server-gate",
            "--forensic-server-post-gate",
            "--expected-control-sha256",
            "--expected-control-forensic-sha256",
            "--control-forensic-cleanup",
            "--candidate-forensic-cleanup",
            "localmaxxing_submission_ready == false",
        ):
            self.assertIn(required, source)


if __name__ == "__main__":
    unittest.main()
