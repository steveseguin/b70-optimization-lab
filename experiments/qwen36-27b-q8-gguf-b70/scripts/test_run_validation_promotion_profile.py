#!/usr/bin/env python3
"""Offline fail-closed tests for run-validation promotion profiles."""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
RUNNER = SCRIPT_DIR / "run-validation.sh"
RUNTIME_MANIFEST = SCRIPT_DIR.parent / "runtime-manifest.json"
DEFAULT_PROFILE = "goal1-baseline-ub128"
CANDIDATE_PROFILE = "prefill-ub1024"


class PromotionProfileTests(unittest.TestCase):
    def run_runner(
        self,
        *,
        run_scope: str = "promotion512",
        profile: str | None = DEFAULT_PROFILE,
        ubatch_size: str = "128",
    ) -> tuple[subprocess.CompletedProcess[str], Path]:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        run_dir = root / "must-not-be-created"
        environment = {
            "HOME": os.environ.get("HOME", "/tmp"),
            "LANG": "C.UTF-8",
            "PATH": os.environ["PATH"],
            "RUN_SCOPE": run_scope,
            "FULL512_BAND": "short" if run_scope == "promotion512" else "realistic",
            "UBATCH_SIZE": ubatch_size,
            "MODEL": str(root / "deliberately-missing-model.gguf"),
            "RUNTIME_MANIFEST": str(RUNTIME_MANIFEST),
            "RUN_DIR": str(run_dir),
        }
        if profile is not None:
            environment["PROMOTION_PROFILE"] = profile
        completed = subprocess.run(
            ["/usr/bin/bash", str(RUNNER)],
            check=False,
            capture_output=True,
            text=True,
            env=environment,
            timeout=30,
        )
        return completed, run_dir

    def assert_reaches_missing_model_gate(
        self, completed: subprocess.CompletedProcess[str], run_dir: Path
    ) -> None:
        self.assertEqual(completed.returncode, 2, completed.stderr)
        self.assertIn("model not found:", completed.stderr)
        self.assertNotIn("PROMOTION_PROFILE", completed.stderr)
        self.assertFalse(
            run_dir.exists(), "runner advanced past the missing-model gate"
        )

    def test_implicit_default_profile_with_ub128_reaches_model_gate(self) -> None:
        completed, run_dir = self.run_runner(profile=None, ubatch_size="128")
        self.assert_reaches_missing_model_gate(completed, run_dir)

    def test_explicit_default_profile_with_ub128_reaches_model_gate(self) -> None:
        completed, run_dir = self.run_runner(profile=DEFAULT_PROFILE, ubatch_size="128")
        self.assert_reaches_missing_model_gate(completed, run_dir)

    def test_candidate_profile_with_ub1024_reaches_model_gate(self) -> None:
        completed, run_dir = self.run_runner(
            profile=CANDIDATE_PROFILE, ubatch_size="1024"
        )
        self.assert_reaches_missing_model_gate(completed, run_dir)

    def test_crossed_profile_ubatch_pairs_fail_before_model_gate(self) -> None:
        for profile, ubatch_size, expected in (
            (DEFAULT_PROFILE, "1024", "requires UBATCH_SIZE=128"),
            (CANDIDATE_PROFILE, "128", "requires UBATCH_SIZE=1024"),
        ):
            with self.subTest(profile=profile, ubatch_size=ubatch_size):
                completed, run_dir = self.run_runner(
                    profile=profile, ubatch_size=ubatch_size
                )
                self.assertEqual(completed.returncode, 2, completed.stderr)
                self.assertIn(expected, completed.stderr)
                self.assertNotIn("model not found:", completed.stderr)
                self.assertFalse(run_dir.exists())

    def test_unknown_profile_fails_before_model_gate(self) -> None:
        for profile in ("", "unregistered-ubatch"):
            with self.subTest(profile=profile):
                completed, run_dir = self.run_runner(profile=profile, ubatch_size="128")
                self.assertEqual(completed.returncode, 2, completed.stderr)
                self.assertIn(f"invalid PROMOTION_PROFILE={profile}", completed.stderr)
                self.assertNotIn("model not found:", completed.stderr)
                self.assertFalse(run_dir.exists())

    def test_candidate_profile_is_rejected_outside_promotion_scope(self) -> None:
        completed, run_dir = self.run_runner(
            run_scope="smoke", profile=CANDIDATE_PROFILE, ubatch_size="1024"
        )
        self.assertEqual(completed.returncode, 2, completed.stderr)
        self.assertIn("is only allowed with RUN_SCOPE=promotion512", completed.stderr)
        self.assertNotIn("model not found:", completed.stderr)
        self.assertFalse(run_dir.exists())

    def test_embedded_attestation_uses_the_single_resolved_ubatch(self) -> None:
        source = RUNNER.read_text()
        self.assertIn(
            'PROMOTION_PROFILE="${PROMOTION_PROFILE-goal1-baseline-ub128}"',
            source,
        )
        self.assertIn('0 1 1024 "$PROMOTION_EXPECTED_UBATCH_SIZE" 99 8 50', source)
        invocation, embedded = source.split(
            'python3 - "$RUN_DIR/server.stdout.log" "$RUN_DIR/server.identity.log" '
            '"$RUN_DIR/server-config-check.json"',
            1,
        )
        del invocation
        embedded = embedded.split("\nPY\n", 1)[0]
        self.assertIn("\"$PROMOTION_EXPECTED_UBATCH_SIZE\" <<'PY'", embedded)
        self.assertIn('"ubatch_size": str(promotion_expected_ubatch)', embedded)
        self.assertIn('f"-ub {promotion_expected_ubatch}"', embedded)
        self.assertNotIn('"ubatch_size": "128"', embedded)
        self.assertNotIn('"-ub 128"', embedded)

    def test_profile_is_bound_into_labels_and_detached_evidence(self) -> None:
        source = RUNNER.read_text()
        self.assertIn(
            'LABEL="${LABEL}-${PROMOTION_PROFILE}-ub${PROMOTION_EXPECTED_UBATCH_SIZE}"',
            source,
        )
        self.assertIn('echo "promotion_profile=$PROMOTION_PROFILE"', source)
        self.assertIn(
            'echo "promotion_expected_ubatch_size=$PROMOTION_EXPECTED_UBATCH_SIZE"',
            source,
        )
        self.assertIn("promotion_profile:$promotion_profile", source)
        self.assertIn(
            "promotion_expected_ubatch_size:$promotion_expected_ubatch_size",
            source,
        )


if __name__ == "__main__":
    unittest.main()
