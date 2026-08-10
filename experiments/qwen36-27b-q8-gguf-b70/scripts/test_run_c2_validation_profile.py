#!/usr/bin/env python3
"""Offline fail-closed tests for formal c2 ubatch profiles."""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
RUNNER = SCRIPT_DIR / "run-c2-validation.sh"
BASELINE_PROFILE = "goal1-baseline-ub128"
PREFILL_PROFILE = "prefill-ub1024"


class C2ValidationProfileTests(unittest.TestCase):
    def run_runner(
        self,
        *,
        profile: str | None = BASELINE_PROFILE,
        ubatch_size: str | None = "128",
        band: str = "near32k",
    ) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        run_dir = root / "must-not-be-created"
        sentinel_dir = root / "external-command-sentinels"
        sentinel_dir.mkdir()
        stub_dir = root / "bin"
        stub_dir.mkdir()
        for command in ("curl", "xpu-smi"):
            stub = stub_dir / command
            stub.write_text(
                "#!/usr/bin/env bash\n"
                f'printf invoked > "$SENTINEL_DIR/{command}"\n'
                "exit 97\n"
            )
            stub.chmod(0o755)

        environment = {
            "HOME": os.environ.get("HOME", "/tmp"),
            "LANG": "C.UTF-8",
            "PATH": f"{stub_dir}:{os.environ['PATH']}",
            "BAND": band,
            "MODEL": str(root / "deliberately-missing-model.gguf"),
            "RUN_DIR": str(run_dir),
            "SENTINEL_DIR": str(sentinel_dir),
        }
        if profile is not None:
            environment["C2_PROFILE"] = profile
        if ubatch_size is not None:
            environment["UBATCH_SIZE"] = ubatch_size
        completed = subprocess.run(
            ["/usr/bin/bash", str(RUNNER)],
            check=False,
            capture_output=True,
            text=True,
            env=environment,
            timeout=30,
        )
        return completed, run_dir, sentinel_dir

    def assert_reaches_missing_model_gate(
        self,
        completed: subprocess.CompletedProcess[str],
        run_dir: Path,
        sentinel_dir: Path,
    ) -> None:
        self.assertEqual(completed.returncode, 2, completed.stderr)
        self.assertIn("model not found:", completed.stderr)
        self.assertNotIn("C2_PROFILE", completed.stderr)
        self.assertFalse(run_dir.exists())
        self.assertEqual(list(sentinel_dir.iterdir()), [])

    def test_implicit_default_remains_ub128_for_every_band(self) -> None:
        for band in ("short", "middle", "near32k"):
            with self.subTest(band=band):
                completed, run_dir, sentinels = self.run_runner(
                    profile=None,
                    ubatch_size=None,
                    band=band,
                )
                self.assert_reaches_missing_model_gate(completed, run_dir, sentinels)

    def test_explicit_baseline_ub128_reaches_model_gate(self) -> None:
        completed, run_dir, sentinels = self.run_runner()
        self.assert_reaches_missing_model_gate(completed, run_dir, sentinels)

    def test_near32k_prefill_ub1024_reaches_model_gate(self) -> None:
        completed, run_dir, sentinels = self.run_runner(
            profile=PREFILL_PROFILE,
            ubatch_size="1024",
        )
        self.assert_reaches_missing_model_gate(completed, run_dir, sentinels)

    def test_unknown_profiles_fail_before_model_or_external_commands(self) -> None:
        for profile in ("", "baseline-ub128", "prefill-ub2048"):
            with self.subTest(profile=profile):
                completed, run_dir, sentinels = self.run_runner(profile=profile)
                self.assertEqual(completed.returncode, 2, completed.stderr)
                self.assertIn(f"invalid C2_PROFILE={profile}", completed.stderr)
                self.assertNotIn("model not found:", completed.stderr)
                self.assertFalse(run_dir.exists())
                self.assertEqual(list(sentinels.iterdir()), [])

    def test_crossed_profile_ubatch_pairs_fail_before_model(self) -> None:
        for profile, ubatch_size, expected in (
            (BASELINE_PROFILE, "1024", "requires UBATCH_SIZE=128"),
            (PREFILL_PROFILE, "128", "requires UBATCH_SIZE=1024"),
        ):
            with self.subTest(profile=profile, ubatch_size=ubatch_size):
                completed, run_dir, sentinels = self.run_runner(
                    profile=profile,
                    ubatch_size=ubatch_size,
                )
                self.assertEqual(completed.returncode, 2, completed.stderr)
                self.assertIn(expected, completed.stderr)
                self.assertNotIn("model not found:", completed.stderr)
                self.assertFalse(run_dir.exists())
                self.assertEqual(list(sentinels.iterdir()), [])

    def test_empty_or_noninteger_ubatch_fails_before_model(self) -> None:
        for ubatch_size in ("", "1024x", "-1"):
            with self.subTest(ubatch_size=ubatch_size):
                completed, run_dir, sentinels = self.run_runner(ubatch_size=ubatch_size)
                self.assertEqual(completed.returncode, 2, completed.stderr)
                self.assertIn(
                    "UBATCH_SIZE must be a nonnegative integer", completed.stderr
                )
                self.assertNotIn("model not found:", completed.stderr)
                self.assertFalse(run_dir.exists())
                self.assertEqual(list(sentinels.iterdir()), [])

    def test_prefill_profile_is_near32k_only(self) -> None:
        for band in ("short", "middle"):
            with self.subTest(band=band):
                completed, run_dir, sentinels = self.run_runner(
                    profile=PREFILL_PROFILE,
                    ubatch_size="1024",
                    band=band,
                )
                self.assertEqual(completed.returncode, 2, completed.stderr)
                self.assertIn("restricted to BAND=near32k", completed.stderr)
                self.assertNotIn("model not found:", completed.stderr)
                self.assertFalse(run_dir.exists())
                self.assertEqual(list(sentinels.iterdir()), [])

    def test_one_resolved_ubatch_is_bound_through_evidence(self) -> None:
        source = RUNNER.read_text()
        self.assertIn('C2_PROFILE="${C2_PROFILE-goal1-baseline-ub128}"', source)
        preflight = (
            'die "C2_PROFILE=$C2_PROFILE requires '
            'UBATCH_SIZE=$C2_PROFILE_EXPECTED_UBATCH_SIZE"'
        )
        self.assertIn(preflight, source)
        after_preflight = source.split(preflight, 1)[1]
        self.assertNotIn("$UBATCH_SIZE", after_preflight)
        self.assertIn('UBATCH_SIZE="$C2_PROFILE_EXPECTED_UBATCH_SIZE"', after_preflight)

        attestation = source.split("attest_server() {", 1)[1].split("\nPY\n}", 1)[0]
        self.assertIn("\"$C2_PROFILE_EXPECTED_UBATCH_SIZE\" <<'PY'", attestation)
        self.assertIn('"ubatch_size": expected_ubatch_size', attestation)
        self.assertIn('f"-ub {expected_ubatch_size}"', attestation)
        self.assertIn('f"n_ubatch_{expected_ubatch_size}"', attestation)
        self.assertNotIn('"ubatch_size": "128"', attestation)
        self.assertNotIn('"-ub 128"', attestation)
        self.assertNotIn('"c2_profile": c2_profile', attestation)
        self.assertNotIn(
            '"expected_ubatch_size": int(expected_ubatch_size)', attestation
        )

        self.assertIn('echo "c2_profile=$C2_PROFILE"', source)
        self.assertIn(
            'echo "c2_profile_expected_ubatch_size=$C2_PROFILE_EXPECTED_UBATCH_SIZE"',
            source,
        )
        self.assertEqual(
            source.count(
                ".run_identity.server_benchmark_identity.ubatch_size "
                "== $expected_ubatch_size"
            ),
            2,
        )
        self.assertIn('"c2_profile": c2_profile', source)
        self.assertIn('"expected_ubatch_size": expected_ubatch_size', source)
        self.assertIn(
            '"c2_profile_identity_both_phases": all(phase_profile_identity.values())',
            source,
        )
        self.assertIn('"c2_profile": c2_profile,', source)
        self.assertIn('"expected_ubatch_size": int(expected_ubatch_size_raw)', source)


if __name__ == "__main__":
    unittest.main()
